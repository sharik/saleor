from json import JSONDecodeError
from typing import TYPE_CHECKING, List

from requests import RequestException

from saleor.payment import TransactionKind
from saleor.payment.interface import GatewayConfig, GatewayResponse, PaymentData
from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from ..api import BitsAPI

GATEWAY_NAME = "Bits"
PLUGIN_ID = "bits.payments"


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
                    error=exception_message if isinstance(exception_message, str) else str(e),
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
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = GatewayConfig(
            gateway_name=GATEWAY_NAME,
            auto_capture=False,
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

        api = BitsAPI.from_payment_data(payment_information)
        data = api.create_order_payment(amount=float(amount),
                                        payment_id=payment_information.payment_id)

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
            raw_response=raw_response
        )

    @handle_exception(TransactionKind.CAPTURE)
    @require_active_plugin
    def capture_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        kind = TransactionKind.CAPTURE
        api = BitsAPI.from_payment_data(payment_information)
        data = api.capture_order_payment(payment_information.token,
                                         order_id=payment_information.order_id)

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

    @require_active_plugin
    def refund_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        raise NotImplementedError

    @handle_exception(TransactionKind.VOID)
    @require_active_plugin
    def void_payment(
            self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        kind = TransactionKind.VOID
        api = BitsAPI.from_payment_data(payment_information)
        data = api.cancel_order_payment(payment_information.token)

        return GatewayResponse(
            transaction_id=payment_information.token,
            action_required=False,
            kind=kind,
            amount=payment_information.amount,
            currency=payment_information.currency,
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
        kind = TransactionKind.AUTH
        api = BitsAPI.from_payment_data(payment_information)
        data = api.verify_order_payment(payment_information.token)

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
            raw_response=raw_response
        )

    @require_active_plugin
    def get_payment_config(self, previous_value):
        return []
