from django import template
from django.core.exceptions import ObjectDoesNotExist

from saleor.product.templatetags.product_images import get_product_image_thumbnail

from ..models import OrderLine

register = template.Library()


@register.simple_tag()
def display_translated_order_line_name(order_line: OrderLine):
    product_name = order_line.translated_product_name or order_line.product_name
    variant_name = order_line.translated_variant_name or order_line.variant_name
    return f"{product_name} ({variant_name})" if variant_name else product_name


@register.simple_tag()
def order_line_thumbnail(order_line: OrderLine, size=255):
    try:
        product_image = order_line.variant.get_first_image()
    except ObjectDoesNotExist:
        product_image = None

    return get_product_image_thumbnail(product_image, size, method='thumbnail')
