import logging

from django.core.management.base import BaseCommand

from saleor.graphql.order.mutations.orders import try_payment_action
from saleor.order.actions import order_captured, order_voided
from saleor.payment import TransactionKind, gateway, ChargeStatus
from saleor.payment.models import Payment

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Verify not finished payments"

    def handle(self, *args, **options):
        payments = Payment.objects.filter(is_active=True,
                                          to_confirm=True,
                                          order__is_null=False,
                                          # created__gt=
                                          status_in=[ChargeStatus.NOT_CHARGED, ChargeStatus.PENDING])

        for payment in payments:
            amount = payment.get_charge_amount()
            order = payment.order

            transaction = try_payment_action(
                order, None, payment, gateway.capture, payment, amount
            )
            if transaction.kind == TransactionKind.CAPTURE:
                order_captured(order, None, amount, payment)
