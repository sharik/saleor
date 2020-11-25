import logging
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from saleor.graphql.order.mutations.orders import try_payment_action
from saleor.order.actions import order_captured, order_voided
from saleor.payment import TransactionKind, gateway, ChargeStatus
from saleor.payment.models import Payment

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Verify not finished payments"

    def handle(self, *args, **options):
        """
        How payment datetime filter calculates
        # started             2020-11-24 16:30:00
        # will be canceled    2020-12-01 16:30:00 (+7 days)
        # capture             2020-12-01 10:30:00 (+6 days 20 hours)
        """

        to_ = now() - datetime.timedelta(days=6, hours=20)

        payments = Payment.objects.filter(is_active=True,
                                          order__isnull=False,
                                          created__lt=to_,
                                          charge_status__in=[ChargeStatus.NOT_CHARGED, ])

        for payment in payments:
            try:
                amount = payment.get_charge_amount()
                order = payment.order

                transaction = try_payment_action(
                    order, None, payment, gateway.capture, payment, amount
                )
                if transaction.kind == TransactionKind.CAPTURE:
                    order_captured(order, None, amount, payment)
            except:
                log.exception('Unhandled payment #{}'.format(payment.pk))
                continue

