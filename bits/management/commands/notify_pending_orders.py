import logging
import datetime

from django.core.management.base import BaseCommand

from saleor.order import OrderStatus
from saleor.order.emails import send_order_preparing
from saleor.order.models import Order

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Notify pernding orders. " \
           "Check hourly. Send pending notification after 24 hour order creation"

    def handle(self, *args, **options):
        from_ = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        to_ = from_ + datetime.timedelta(hours=1)

        orders = Order.objects.exclude(status=OrderStatus.CANCELED).filter(
            created__range=[from_, to_]
        )

        for order in orders:
            send_order_preparing.delay(order.pk, None)
