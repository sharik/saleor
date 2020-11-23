from json import JSONDecodeError
from typing import TYPE_CHECKING, List, Any

import graphene
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from requests import RequestException

from saleor import settings
from saleor.core.utils import build_absolute_uri
from saleor.order.models import OrderLine, Order
from saleor.payment import TransactionKind
from saleor.payment.interface import GatewayConfig, GatewayResponse, PaymentData
from saleor.payment.models import Payment
from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from ..api import BitsAPI
# important to import. register in task system
from ..tasks import verify_payment

GATEWAY_NAME = "Bits"
PLUGIN_ID = "bits.payments"


def collect_metadata(payment):
    metadata = []

    objects_with_metadata = {payment.checkout}
    for line in payment.checkout.lines.all():
        objects_with_metadata.add(line.variant)
        objects_with_metadata.add(line.variant.product)
        objects_with_metadata.add(line.variant.product.product_type)

    for obj in objects_with_metadata:
        for k, v in obj.metadata.items():
            metadata.append({'key': k, 'value': v, 'object_type': obj._meta.model_name})

    return metadata


def collect_metadata_for_line(line):
    metadata = {}

    objects_with_metadata = set()
    objects_with_metadata.add(line.variant.product.product_type)
    objects_with_metadata.add(line.variant.product)
    objects_with_metadata.add(line.variant)

    for obj in objects_with_metadata:
        for k, v in obj.metadata.items():
            metadata[k] = v

    return metadata


def collect_links_for_order_line(order_line: "OrderLine"):
    try:
        digital_file_obj = order_line.bits_digital_content
    except ObjectDoesNotExist:
        return ()
    url = reverse("bits:bits-digital-file", kwargs={"token": str(digital_file_obj.token)})
    return (build_absolute_uri(url), )


def collect_extra(payment):
    obj = payment.order or payment.checkout

    extra = {'orderId': graphene.Node.to_global_id("Order", payment.order.pk) if payment.order else None,
             'orderLines': []}

    for line in obj.lines.all():
        extra['orderLines'].append({
            'id': graphene.Node.to_global_id('ProductVariant', line.variant.pk),
            'name': line.variant.name,
            'productName': line.variant.product.name,
            'links': collect_links_for_order_line(line),
            'quantity': line.quantity,
            'metadata': collect_metadata_for_line(line)
        })

    return extra


def require_active_plugin(fn):
    def wrapped(self, *args, **kwargs):
        previous = kwargs.get("previous_value", None)
        if not self.active:
            return previous
        return fn(self, *args, **kwargs)

    return wrapped


def handle_exception(transaction_kind: "TransactionKind"):
    def _wrap(fn):
        def wrapped(self, payment_information: "PaymentData", *args, **kwargs):
            kind = transaction_kind
            data = None

            try:
                return fn(self, payment_information, *args, **kwargs)
            except RequestException as e:
                is_success = False
                exception_message = None
                try:
                    data = e.response.json()
                    if data.get('code', None) == 302:
                        # payment cancelled
                        kind = TransactionKind.VOID
                        exception_message = data.get('message', str(e))
                        is_success = True
                    else:
                        # payment validation error like action not allowed
                        try:
                            exception_message = data.get('detail', {}).get('message')
                            if not exception_message:
                                exception_message = data.get('message')
                        except (AttributeError, IndexError, ValueError, TypeError):
                            pass
                except (TypeError, JSONDecodeError, ValueError):
                    if e.response.content:
                        exception_message = e.response.content.decode('utf-8')
                    else:
                        exception_message = 'An error occurred while making a {} request to {}'.format(
                            e.response.request.method, e.response.request.url)
                except AttributeError:
                    exception_message = str(e)

                return GatewayResponse(
                    is_success=is_success,
                    action_required=False,
                    transaction_id=payment_information.token,
                    amount=payment_information.amount,
                    currency=payment_information.currency,
                    error=exception_message if isinstance(exception_message,
                                                          str) else str(e),
                    kind=str(kind),
                    raw_response=data,
                    customer_id=payment_information.customer_id,
                )

        return wrapped

    return _wrap


class BitsGatewayPlugin(BasePlugin):
    PLUGIN_ID = PLUGIN_ID
    PLUGIN_NAME = GATEWAY_NAME
    DEFAULT_ACTIVE = True
    DEFAULT_CONFIGURATION = [
        {"name": "Bits API key", "value": None},
        {"name": "Bits API URL", "value": 'https://api.getbits.app'},
        {"name": "Supported currencies", "value": settings.DEFAULT_CURRENCY}
    ]
    CONFIG_STRUCTURE = {
        "Bits API key": {
            "type": ConfigurationTypeField.SECRET,
            "help_text": "Provider Bits API key.",
            "label": "Bits API key",
        },
        "Bits API URL": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Base bits api URL.",
            "label": "Bits API URL",
        },
        "Supported currencies": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Determines currencies supported by gateway."
                         " Please enter currency codes separated by a comma.",
            "label": "Supported currencies",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = GatewayConfig(
            gateway_name=GATEWAY_NAME,
            auto_capture=False,
            supported_currencies=configuration["Supported currencies"],
            connection_params={
                'base_url': configuration['Bits API URL'],
                'api_key': configuration['Bits API key']
            },
            store_customer=False,
        )

    def _get_gateway_config(self):
        return self.config

    @handle_exception(TransactionKind.AUTH)
    @require_active_plugin
    def authorize_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        kind = TransactionKind.AUTH
        amount = payment_information.amount
        payment = Payment.objects.get(pk=payment_information.payment_id)

        api = BitsAPI.from_payment_data(payment_information)
        data = api.create_order_payment(amount=float(amount),
                                        payment_id=payment_information.payment_id,
                                        extra=collect_extra(payment))

        raw_response = {'response': data}
        if data.get('require_action'):
            raw_response['action_required_data'] = {
                'client_secret': data['require_action_secret']}

        return GatewayResponse(
            transaction_id=data.get('id'),
            action_required=data.get('require_action'),
            kind=kind,
            amount=payment_information.amount,
            currency=payment_information.currency,
            error=None,
            is_success=True,
            raw_response=raw_response,
            action_required_data=raw_response.get('action_required_data')
        )

    @handle_exception(TransactionKind.CAPTURE)
    @require_active_plugin
    def capture_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        payment = Payment.objects.get(pk=payment_information.payment_id)

        kind = TransactionKind.CAPTURE
        api = BitsAPI.from_payment_data(payment_information)
        data = api.capture_order_payment(payment_information.token,
                                         order_id=payment_information.order_id,
                                         extra=collect_extra(payment))

        return GatewayResponse(
            transaction_id=data.get('id'),
            action_required=False,
            kind=kind,
            amount=payment_information.amount,
            currency=payment_information.currency,
            error=None,
            is_success=True
        )

    @require_active_plugin
    def confirm_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return self.capture_payment(payment_information, previous_value)

    @handle_exception(TransactionKind.REFUND)
    @require_active_plugin
    def refund_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        payment = Payment.objects.get(pk=payment_information.payment_id)

        kind = TransactionKind.REFUND
        api = BitsAPI.from_payment_data(payment_information)
        data = api.refund_order_payment(payment_information.token, extra=collect_extra(payment))
        raw_response = {'response': data}

        return GatewayResponse(
            transaction_id=payment_information.token,
            action_required=False,
            kind=kind,
            amount=payment_information.amount,
            currency=payment_information.currency,
            raw_response=raw_response,
            error=None,
            is_success=True
        )

    @handle_exception(TransactionKind.VOID)
    @require_active_plugin
    def void_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        payment = Payment.objects.get(pk=payment_information.payment_id)

        kind = TransactionKind.VOID
        api = BitsAPI.from_payment_data(payment_information)
        data = api.cancel_order_payment(payment_information.token, extra=collect_extra(payment))
        raw_response = {'response': data}

        return GatewayResponse(
            transaction_id=payment_information.token,
            action_required=False,
            kind=kind,
            amount=payment_information.amount,
            currency=payment_information.currency,
            raw_response=raw_response,
            error=None,
            is_success=True
        )

    @require_active_plugin
    def process_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return self.authorize_payment(payment_information, self._get_gateway_config())

    @handle_exception(TransactionKind.AUTH)
    @require_active_plugin
    def verify_payment(self, payment_information: "PaymentData",
                       previous_value) -> "GatewayResponse":
        payment = Payment.objects.get(pk=payment_information.payment_id)

        kind = TransactionKind.AUTH
        api = BitsAPI.from_payment_data(payment_information)
        data = api.verify_order_payment(payment_information.token, extra=collect_extra(payment))

        raw_response = {'response': data}
        if data.get('require_action'):
            raw_response['action_required_data'] = {
                'client_secret': data['require_action_secret']}

        return GatewayResponse(
            transaction_id=data.get('id'),
            action_required=data.get('require_action'),
            kind=kind,
            amount=payment_information.amount,
            currency=payment_information.currency,
            error=None,
            is_success=True,
            raw_response=raw_response,
            action_required_data=raw_response.get('action_required_data'),
            transaction_already_processed=True
        )

    @require_active_plugin
    def get_payment_config(self, previous_value):
        return []

    @require_active_plugin
    def get_supported_currencies(self, previous_value):
        return ['USD', "GBP", 'EUR']

    @require_active_plugin
    def order_fulfilled(self, order: "Order", previous_value: Any):
        payment = order.get_last_payment()
        if payment:
            verify_payment.delay(payment.pk)

        return previous_value


