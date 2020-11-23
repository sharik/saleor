from django.conf.urls import url

from .views import bits_digital_file

urlpatterns = [
    url(
        r"(?P<token>[0-9A-Za-z_\-]+)/$",
        bits_digital_file,
        name="bits-digital-file",
    )
]
