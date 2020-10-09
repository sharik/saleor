import graphene
from django.contrib.auth.backends import UserModel
from graphql_jwt.shortcuts import get_token

from saleor.account import models
from saleor.graphql.account.mutations.base import BaseCustomerCreate, UserCreateInput
from saleor.graphql.core.types.common import AccountError

from ..api import BitsAPI
from ..models import BitsUser


class BitsTokenExchange(BaseCustomerCreate):
    token = graphene.String()

    class Arguments:
        token = graphene.String(required=True)

    class Meta:
        description = 'Exchange bits token to saleor token. Register user if necessary.'
        exclude = ["password"]
        model = models.User
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def success_response(cls, instance):
        """Return a success response."""
        response = super().success_response(instance)
        if not response.errors:
            response.token = get_token(instance)
        return response

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        access_token = data.get('token')
        api = BitsAPI(access_token=access_token)
        user_data = api.get_user()
        try:
            user = UserModel._default_manager.get_by_natural_key(user_data['email'])
            data['id'] = graphene.Node.to_global_id("User", user.id)
            data['input'] = {
                'first_name': user_data['firstName'],
                'last_name': user_data['lastName'],
                'email': user_data['email'],
                'is_active': True,
                'note': '',
                'default_billing_address': {
                    'street_address_1': user_data['address1'],
                    'street_address_2': user_data['address2'],
                    'city': user_data['city'],
                    'postal_code': user_data['postCode'],
                    'country': 'GB',
                    # 'isDefaultBillingAddress': True
                    # 'phone': user_data['phoneNumber'],
                },
                'default_shipping_address': {
                    'street_address_1': user_data['address1'],
                    'street_address_2': user_data['address2'],
                    'city': user_data['city'],
                    'postal_code': user_data['postCode'],
                    'country': 'GB',
                    # 'isDefaultShippingAddress': True
                    # 'phone': user_data['phoneNumber'],
                },
            }
        except UserModel.DoesNotExist:
            user = None
            data['input'] = {
                'first_name': user_data['firstName'],
                'last_name': user_data['lastName'],
                'email': user_data['email'],
                'is_active': True,
                'note': '',
                'default_billing_address': {
                    'street_address_1': user_data['address1'],
                    'street_address_2': user_data['address2'],
                    'city': user_data['city'],
                    'postal_code': user_data['postCode'],
                    'country': 'GB',
                    # 'isDefaultBillingAddress': True
                    # 'phone': user_data['phoneNumber'],
                },
                'default_shipping_address': {
                    'street_address_1': user_data['address1'],
                    'street_address_2': user_data['address2'],
                    'city': user_data['city'],
                    'postal_code': user_data['postCode'],
                    'country': 'GB',
                    # 'isDefaultShippingAddress': True
                    # 'phone': user_data['phoneNumber'],
                },
            }

        try:
            return super().perform_mutation(_root, info, **data)
        finally:
            try:
                user = UserModel._default_manager.get_by_natural_key(user_data['email'])
                is_updated = BitsUser.objects.filter(user=user).update(external_id=user_data['membershipNumber'],
                                                                       response=user_data)
                if not is_updated:
                    BitsUser.objects.create(user=user,
                                            external_id=user_data['membershipNumber'],
                                            response=user_data)
            except UserModel.DoesNotExist:
                pass

    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None, **kwargs):
        return super().clean_input(info, instance, data, input_cls=input_cls or UserCreateInput, **kwargs)

    @classmethod
    def get_instance(cls, info, **data):
        """Retrieve an instance from the supplied global id.

        The expected graphene type can be lazy (str).
        """
        object_id = data.get("id")
        if object_id:
            model_type = cls.get_type_for_model()
            instance = cls.get_node_or_error(info, object_id, only_type=model_type)
        else:
            instance = cls._meta.model()
            instance.set_password(None)
        return instance

# @classmethod
    # def mutate(cls, root, info, **data):
    #     access_token = data.get('token')
    #     user_data = get_user_bits_info(access_token)
    #
    #     return super().mutate(root, info, **data)

    # @classmethod
    # def get_instance(cls, info, **data):
    #     object_id = data.get("id")
    #     if object_id:
    #         model_type = cls.get_type_for_model()
    #         instance = cls.get_node_or_error(info, object_id, only_type=model_type)
    #     else:
    #         instance = cls._meta.model()
    #     return instance



