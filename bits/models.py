import datetime
import json
from typing import Optional, TYPE_CHECKING
from uuid import uuid4

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import JSONField
from django.utils.timezone import is_naive, utc

from bits.const import CAPTURE_DATE_FIELD_NAME
from saleor.core.models import ModelWithMetadata
from saleor.product.models import ProductVariant


if TYPE_CHECKING:
    from saleor.payment.models import Payment



class BitsUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    external_id = models.CharField(max_length=256, unique=True)
    response = JSONField(encoder=DjangoJSONEncoder)

    class Meta:
        ordering = ("pk",)


class BitsDigitalContent(ModelWithMetadata):
    FILE = "file"
    TYPE_CHOICES = ((FILE, "digital_product"),)
    content_type = models.CharField(max_length=128, default=FILE, choices=TYPE_CHOICES)
    product_variant = models.ForeignKey(
        ProductVariant, related_name="bits_digital_contents", on_delete=models.CASCADE
    )
    content_file = models.FileField(upload_to="bits_digital_content", blank=True)

    line = models.OneToOneField(
        "order.OrderLine",
        related_name="bits_digital_content",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )

    token = models.UUIDField(editable=False, unique=True)

    def save(
            self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.token:
            self.token = str(uuid4()).replace("-", "")
        super().save(force_insert, force_update, using, update_fields)


def update_payment_capture_date(payment: "Payment", capture_date: str):
    """
    Save date when payment should be captured
    """
    if isinstance(capture_date, str):
        capture_date = datetime.datetime.fromisoformat(capture_date)

    extra_data = {
        CAPTURE_DATE_FIELD_NAME: capture_date.isoformat()
    }
    payment.extra_data = json.dumps(extra_data)
    payment.save(update_fields=["extra_data"])


def get_payment_capture_date(payment: "Payment") -> Optional[datetime.datetime]:
    """
    Get date when payment should be captured
    """
    capture_date = None
    if payment.extra_data:
        extra_data = json.loads(payment.extra_data)

        capture_date = extra_data.get(CAPTURE_DATE_FIELD_NAME, None)
        if isinstance(capture_date, str):
            capture_date = datetime.datetime.fromisoformat(capture_date).replace(tzinfo=utc)
        else:
            capture_date = None

    return capture_date

