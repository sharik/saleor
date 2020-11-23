import logging

from saleor.celeryconf import app
from saleor.payment import gateway
from saleor.payment.models import Payment


log = logging.getLogger()


@app.task
def verify_payment(payment_pk: int):
    payment = Payment.objects.get(pk=payment_pk)

    last_transaction = payment.get_last_transaction(include_failed=False)
    if last_transaction:
        txn = gateway.verify_payment(payment=payment, transaction=last_transaction)
    else:
        log.warning('Transaction not found for payment #{}'.format(str(payment_pk)))
