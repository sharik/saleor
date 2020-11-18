import logging

from draftjs_exporter.constants import ENTITY_TYPES
from draftjs_exporter.dom import DOM
from draftjs_exporter.html import HTML
from draftjs_exporter.types import Props, Element

log = logging.getLogger()


def link(props: Props) -> Element:
    return DOM.create_element("a", {"href": props["url"]}, props["children"])


def image(props: Props) -> Element:
    return DOM.create_element(
        "img",
        {
            "src": props.get("src"),
            "width": props.get("width"),
            "height": props.get("height"),
            "alt": props.get("alt"),
        },
    )


def entity_fallback(props: Props) -> Element:
    type_ = props["entity"]["type"]
    key = props["entity"]["entity_range"]["key"]
    logging.warning(f'Missing config for "{type_}", key "{key}".')
    return DOM.create_element(
        "span", {"class": "missing-entity"}, props["children"]
    )


config = {
    'entity_decorators': {
        ENTITY_TYPES.IMAGE: image,
        ENTITY_TYPES.LINK: link,
        # Lambdas work too.
        ENTITY_TYPES.HORIZONTAL_RULE: lambda props: DOM.create_element(
            "hr"
        ),
        # Discard those entities.
        ENTITY_TYPES.EMBED: None,
        # Provide a fallback component (advanced).
        ENTITY_TYPES.FALLBACK: entity_fallback,

    },
    'engine': DOM.LXML
}

html = HTML(config)
