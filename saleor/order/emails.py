import logging
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from templated_email import send_templated_mail, InlineImage

from ..account.models import StaffNotificationRecipient, User
from ..celeryconf import app
from ..core.emails import get_email_context
from ..core.utils.url import prepare_url
from ..seo.schema.email import get_order_confirmation_markup
from . import events
from .models import Fulfillment, Order

if TYPE_CHECKING:
    from decimal import Decimal

    from ..account.models import User  # noqa: F401


log = logging.getLogger('saleor.order.emails')

CONFIRM_ORDER_TEMPLATE = "order/confirm_order"
CONFIRM_ORDER_DIGITAL_TEMPLATE = "order/confirm_order_digital"
PREPARING_ORDER_DIGITAL_TEMPLATE = "order/preparing_order_digital"

STAFF_CONFIRM_ORDER_TEMPLATE = "order/staff_confirm_order"
CONFIRM_FULFILLMENT_TEMPLATE = "order/confirm_fulfillment"
CONFIRM_FULFILLMENT_DIGITAL_TEMPLATE = "order/confirm_fulfillment_digital"

UPDATE_FULFILLMENT_TEMPLATE = "order/update_fulfillment"
CONFIRM_PAYMENT_TEMPLATE = "order/payment/confirm_payment"
ORDER_CANCEl_TEMPLATE = "order/order_cancel"
ORDER_REFUND_TEMPLATE = "order/order_refund"

ENABLE_FULLFILLMENT_EMAIL = False


def order_is_digital(order: "Order") -> bool:
    return any((line.is_digital for line in order.lines.all()))


def collect_staff_order_notification_data(
    order_pk: int, template: str, redirect_url: str
) -> dict:
    data = collect_data_for_email(order_pk, template, redirect_url)
    staff_notifications = StaffNotificationRecipient.objects.filter(
        active=True, user__is_active=True, user__is_staff=True
    )
    staff = User.objects.staff()
    recipient_emails = [
        notification.get_email() for notification in staff_notifications
    ]
    staff_emails = [user.email for user in staff]

    data["recipient_list"] = list(set(recipient_emails + staff_emails))
    return data


def collect_data_for_email(
    order_pk: int, template: str, redirect_url: str = ""
) -> dict:
    """Collect the required data for sending emails."""
    order = Order.objects.prefetch_related("lines__variant__product__images").get(
        pk=order_pk
    )
    recipient_email = order.get_customer_email()
    send_kwargs, email_context = get_email_context()

    email_context["order_details_url"] = (
        prepare_order_details_url(order, redirect_url) if redirect_url else ""
    )
    email_context["order"] = order

    # Order confirmation template requires additional information
    if template in [CONFIRM_ORDER_TEMPLATE, STAFF_CONFIRM_ORDER_TEMPLATE, CONFIRM_ORDER_DIGITAL_TEMPLATE, ORDER_CANCEl_TEMPLATE]:
        email_markup = get_order_confirmation_markup(order)
        email_context["schema_markup"] = email_markup

    return {
        "recipient_list": [recipient_email],
        "template_name": template,
        "context": email_context,
        **send_kwargs,
    }


def prepare_order_details_url(order: Order, redirect_url: str) -> str:
    params = urlencode({"token": order.token})
    return prepare_url(params, redirect_url)


def collect_data_for_fulfillment_email(order_pk, template, fulfillment_pk):
    fulfillment = Fulfillment.objects.get(pk=fulfillment_pk)
    email_data = collect_data_for_email(order_pk, template)
    lines = fulfillment.lines.all()
    physical_lines = [line for line in lines if not line.order_line.is_digital]
    digital_lines = [line for line in lines if line.order_line.is_digital]
    digital_attachments = [(line.order_line.bits_digital_content.content_file.name, line.order_line.bits_digital_content.content_file.read(), None) for line in lines if line.order_line.is_digital]
    context = email_data["context"]
    context.update(
        {
            "fulfillment": fulfillment,
            "physical_lines": physical_lines,
            "digital_lines": digital_lines,
        }
    )
    email_data['attachments'] = digital_attachments
    return email_data


@app.task
def send_order_confirmation(order_pk, redirect_url, user_pk=None):
    """Send order confirmation email."""
    if not settings.EMAIL_ORDER_CONFIRMATION_ENABLED:
        log.warning('Order confirmation email disabled')
        return

    order = Order.objects.prefetch_related("lines").get(
        pk=order_pk
    )

    if order_is_digital(order):
        template = CONFIRM_ORDER_DIGITAL_TEMPLATE
    else:
        template = CONFIRM_ORDER_TEMPLATE

    email_data = collect_data_for_email(order_pk, template, redirect_url)
    send_templated_mail(**email_data)
    events.email_sent_event(
        order=email_data["context"]["order"],
        user=None,
        user_pk=user_pk,
        email_type=events.OrderEventsEmails.ORDER_CONFIRMATION,
    )


@app.task
def send_order_preparing(order_pk, redirect_url, user_pk=None):
    """Send order preparing email."""
    if not settings.EMAIL_ORDER_PREPARING_ENABLED:
        log.warning('Order preparing email disabled')
        return

    email_data = collect_data_for_email(order_pk, CONFIRM_ORDER_TEMPLATE, redirect_url)
    email_data['template_name'] = PREPARING_ORDER_DIGITAL_TEMPLATE
    send_templated_mail(**email_data)
    events.email_sent_event(
        order=email_data["context"]["order"],
        user=None,
        user_pk=user_pk,
        email_type=events.OrderEventsEmails.ORDER_PREPARING,
    )


@app.task
def send_staff_order_confirmation(order_pk, redirect_url):
    """Send order confirmation email."""
    if not settings.EMAIL_ORDER_STAFF_CONFIRMATION_ENABLED:
        log.warning('Order staff confirmation email disabled')
        return

    staff_email_data = collect_staff_order_notification_data(
        order_pk, STAFF_CONFIRM_ORDER_TEMPLATE, redirect_url
    )
    if staff_email_data["recipient_list"]:
        send_templated_mail(**staff_email_data)


@app.task
def send_fulfillment_confirmation(order_pk, fulfillment_pk):
    if not settings.EMAIL_ORDER_FULFILLMENT_CONFIRMATION_ENABLED:
        log.warning('Order fulfillment confirmation email disabled')
        return

    order = Order.objects.prefetch_related("lines").get(
        pk=order_pk
    )

    if order_is_digital(order):
        template = CONFIRM_FULFILLMENT_DIGITAL_TEMPLATE
    else:
        template = CONFIRM_FULFILLMENT_TEMPLATE

    email_data = collect_data_for_fulfillment_email(
        order_pk, template, fulfillment_pk
    )
    send_templated_mail(**email_data)


def send_fulfillment_confirmation_to_customer(order, fulfillment, user):
    transaction.on_commit(
        lambda: send_fulfillment_confirmation.apply_async((order.pk, fulfillment.pk),
                                                          countdown=5)
    )

    events.email_sent_event(
        order=order, user=user, email_type=events.OrderEventsEmails.FULFILLMENT
    )

    # If digital lines were sent in the fulfillment email,
    # trigger the event
    if any((line for line in order if line.variant.is_digital())):
        events.email_sent_event(
            order=order, user=user, email_type=events.OrderEventsEmails.DIGITAL_LINKS
        )


@app.task
def send_fulfillment_update(order_pk, fulfillment_pk):
    if not settings.EMAIL_ORDER_FULFILLMENT_UPDATE_ENABLED:
        log.warning('Order fulfillment update email disabled')
        return

    email_data = collect_data_for_fulfillment_email(
        order_pk, UPDATE_FULFILLMENT_TEMPLATE, fulfillment_pk
    )
    send_templated_mail(**email_data)


@app.task
def send_payment_confirmation(order_pk):
    """Send the payment confirmation email."""
    if not settings.EMAIL_ORDER_PAYMENT_CONFIRMATION_ENABLED:
        log.warning('Order payment confirmation email disabled')
        return

    email_data = collect_data_for_email(order_pk, CONFIRM_PAYMENT_TEMPLATE)
    send_templated_mail(**email_data)


def send_order_canceled_confirmation(order: "Order", user: Optional["User"]):
    send_order_canceled.delay(order.pk)
    events.email_sent_event(
        order=order, user=user, email_type=events.OrderEventsEmails.ORDER_CANCEL
    )


@app.task
def send_order_canceled(order_pk: int):
    """Send order cancel email."""
    if not settings.EMAIL_ORDER_CANCELED_ENABLED:
        log.warning('Order canceled email disabled')
        return

    email_data = collect_data_for_email(order_pk, ORDER_CANCEl_TEMPLATE)
    send_templated_mail(**email_data)


def send_order_refunded_confirmation(
    order: "Order", user: Optional["User"], amount: "Decimal", currency: str
):
    send_order_refunded.delay(order.pk, amount, currency)
    events.email_sent_event(
        order=order, user=user, email_type=events.OrderEventsEmails.ORDER_REFUND
    )


@app.task
def send_order_refunded(order_pk: int, amount: "Decimal", currency: str):
    """Send order refund email."""
    if not settings.EMAIL_ORDER_PAYMENT_REFUNDED_ENABLED:
        log.warning('Order payment refunded email disabled')
        return

    email_data = collect_data_for_email(order_pk, ORDER_REFUND_TEMPLATE)
    context = email_data["context"]
    context.update({"amount": amount, "currency": currency})
    send_templated_mail(**email_data)
