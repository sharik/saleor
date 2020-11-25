import logging
import datetime

from django.core.management.base import BaseCommand

from saleor.order import OrderStatus, events
from saleor.order.emails import send_fulfillment_confirmation
from saleor.order.models import Order

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Notify fulfilled orders. " \
           "Check hourly. Send fulfilled notification after 48 hour order creation"

    def handle(self, *args, **options):
        from_ = datetime.datetime.utcnow() - datetime.timedelta(days=2)
        to_ = from_ + datetime.timedelta(hours=1)

        orders = Order.objects.filter(
            status=OrderStatus.FULFILLED,
            created__range=[from_, to_]
        )

        for order in orders:
            counter = 0
            for fulfillment in order.fulfillments.all():
                send_fulfillment_confirmation.delay(order.pk, fulfillment.pk)
                counter += 1

            if counter == 0:
                self.stdout.write(self.style.WARNING('No fulfillment found for order #{}'.format(order.pk)))
            elif counter > 1:
                self.stdout.write(self.style.WARNING('Multiple fulfillment found for order #{}'.format(order.pk)))

            events.email_sent_event(
                order=order, user=None, email_type=events.OrderEventsEmails.FULFILLMENT
            )

            if any((line for line in order if line.variant.is_digital())):
                events.email_sent_event(
                    order=order, user=None,
                    email_type=events.OrderEventsEmails.DIGITAL_LINKS
                )

