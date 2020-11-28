from django import template
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist

from saleor.product.templatetags.product_images import get_product_image_thumbnail

from ..models import OrderLine

register = template.Library()


def make_url_absolute(path):
    domain = Site.objects.get_current().domain
    scheme = 'https' if settings.SESSION_COOKIE_SECURE else 'http'
    return '{scheme}://{domain}{path}'.format(domain=domain, path=path,
                                              scheme=scheme)


@register.simple_tag()
def display_translated_order_line_name(order_line: OrderLine):
    product_name = order_line.translated_product_name or order_line.product_name
    variant_name = order_line.translated_variant_name or order_line.variant_name
    return f"{product_name} ({variant_name})" if variant_name else product_name


@register.simple_tag()
def display_translated_product_name(order_line: OrderLine):
    product_name = order_line.translated_product_name or order_line.product_name
    return f"{product_name}"


@register.simple_tag()
def order_line_thumbnail(order_line: OrderLine, size=255, absolute=True):
    try:
        product_image = order_line.variant.get_first_image()
    except ObjectDoesNotExist:
        product_image = None

    if absolute:
        return make_url_absolute(get_product_image_thumbnail(product_image, size, method='thumbnail'))
    return get_product_image_thumbnail(product_image, size, method='thumbnail')

