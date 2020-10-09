from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class BitsUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    external_id = models.CharField(max_length=256, unique=True)
    response = JSONField(encoder=DjangoJSONEncoder)

    class Meta:
        ordering = ("pk",)
