from typing import TYPE_CHECKING

import requests

from bits.models import BitsUser
from saleor.payment import PaymentError
from saleor.payment.models import Payment
from saleor.plugins.manager import get_plugins_manager

if TYPE_CHECKING:
    # flake8: noqa
    from saleor.payment.interface import PaymentData


def build_url(base_url, *segments):
    return '{}/{}'.format(base_url, '/'.join(segments))


class BitsAPI(object):
    def __init__(self, access_token=None, external_id=None, base_url=None,
                 api_key=None):
        assert access_token or external_id
        self.access_token = access_token
        self.external_id = external_id

        self.API_URL = base_url
        self.API_KEY = api_key

        if not self.API_URL or not self.API_KEY:
            self.API_URL, self.API_KEY = self.get_api_config()

    @classmethod
    def from_payment_data(cls, payment_information: "PaymentData"):
        payment = Payment.objects.get(pk=payment_information.payment_id)
        if payment.checkout:
            user = payment.checkout.user
        elif payment.order:
            user = payment.order.user
        else:
            raise NotImplementedError

        try:
            bits_user = BitsUser.objects.filter(user=user).get()
        except BitsUser.DoesNotExist:
            raise PaymentError('Not authorized to make Bits API request')
        return cls(external_id=bits_user.external_id)

    def get_api_config(self):
        from bits.plugin import PLUGIN_ID
        plugin_manager = get_plugins_manager()
        plugin = plugin_manager.get_plugin(PLUGIN_ID)
        config = plugin._get_gateway_config()

        return config.connection_params['base_url'], config.connection_params['api_key']

    def _prepare_headers(self):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if self.access_token:
            headers['Authorization'] = self.access_token
        elif self.external_id:
            headers['Authorization'] = self.API_KEY
            headers['Impersonate-Id'] = self.external_id

        return headers

    def _do_post(self, url, data):
        response = requests.post(url, json=data, headers=self._prepare_headers())
        response.raise_for_status()

        return response.json()

    def _do_delete(self, url):
        response = requests.delete(url, headers=self._prepare_headers())
        response.raise_for_status()

        return

    def _do_get(self, url, **kwargs):
        response = requests.get(url, headers=self._prepare_headers())
        response.raise_for_status()

        return response.json()

    def create_order_payment(self, amount: float, payment_id: str, **kwargs):
        segments = (
            'api',
            'v1',
            'orders'
        )
        url = build_url(self.API_URL, *segments)

        payload = {
            'type': 'storeOrder',
            'amount': amount,
            'paymentId': payment_id,
        }
        payload.update(kwargs)

        return self._do_post(url, payload)

    def capture_order_payment(self, external_id, order_id=None, **kwargs):
        segments = (
            'api',
            'v1',
            'orders',
            external_id,
            'capture'
        )

        url = build_url(self.API_URL, *segments)

        payload = {'orderId': order_id}
        payload.update(kwargs)

        return self._do_post(url, data=payload)

    def cancel_order_payment(self, payment_id):
        segments = (
            'api',
            'v1',
            'orders',
            payment_id
        )

        url = build_url(self.API_URL, *segments)
        return self._do_delete(url)

    def verify_order_payment(self, payment_id):
        segments = (
            'api',
            'v1',
            'orders',
            payment_id,
            'verify'
        )

        url = build_url(self.API_URL, *segments)
        return self._do_post(url, data={})

    def get_order_payment(self, payment_id):
        segments = (
            'api',
            'v1',
            'orders',
            payment_id
        )

        url = build_url(self.API_URL, *segments)
        return self._do_get(url)

    def refund_order_payment(self):
        raise NotImplementedError

    def get_user(self):
        segments = (
            'api',
            'v1',
            'me'
        )

        url = build_url(self.API_URL, *segments)

        return self._do_get(url)
