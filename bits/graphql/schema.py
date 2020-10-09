import graphene

from .mutations import BitsTokenExchange


class BitsMutations(graphene.ObjectType):
    token_exchange = BitsTokenExchange.Field()
