from typing import Optional
from uuid import uuid4

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import JSONField

from saleor.core.models import ModelWithMetadata
from saleor.product.models import ProductVariant


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
