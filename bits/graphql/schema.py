import graphene

from .mutations import BitsTokenExchange, BitsDigitalContentUpdate


class BitsMutations(graphene.ObjectType):
    token_exchange = BitsTokenExchange.Field()

    order_line_update_digital_content = BitsDigitalContentUpdate.Field()
