"""PayPal sandbox: Orders v2 (create, capture), Payments v2 (refund), Vault v3 (saved account)."""
import time
import uuid
from decimal import Decimal

import httpx

from app.utils import config

BASE_URL = 'https://api-m.sandbox.paypal.com'
_token = {'value': None, 'expires_at': 0.0}


class PayPalError(Exception):
    pass


async def get_access_token():
    if _token['value'] and time.time() < _token['expires_at'] - 60:
        return _token['value']
    if not config.PAYPAL_CLIENT_ID or not config.PAYPAL_CLIENT_SECRET:
        raise PayPalError('PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are not set')
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            BASE_URL + '/v1/oauth2/token',
            auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
            data={'grant_type': 'client_credentials'},
        )
    if r.status_code != 200:
        raise PayPalError('PayPal auth failed: ' + r.text)
    data = r.json()
    _token['value'] = data['access_token']
    _token['expires_at'] = time.time() + int(data.get('expires_in', 300))
    return _token['value']


async def request(method, path, body=None):
    token = await get_access_token()
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
        'PayPal-Request-Id': uuid.uuid4().hex,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.request(method, BASE_URL + path, headers=headers, json=body)
    if r.status_code >= 400:
        raise PayPalError('PayPal ' + str(r.status_code) + ': ' + r.text)
    return r.json()


def capture_id(data):
    try:
        return data['purchase_units'][0]['payments']['captures'][0]['id']
    except (KeyError, IndexError, TypeError):
        return None


def find_link(data):
    for link in data.get('links', []):
        if link['rel'] in ('approve', 'payer-action'):
            return link['href']
    return None


async def create_order(items, vault_id=None):
    cur = config.PAYPAL_CURRENCY
    total = Decimal('0')
    pp_items = []
    for it in items:
        price = Decimal(it['price'])
        total += price * it['qty']
        pp_items.append({
            'name': it['name'][:127],
            'quantity': str(it['qty']),
            'unit_amount': {'currency_code': cur, 'value': f'{price:.2f}'},
        })
    amount = {
        'currency_code': cur,
        'value': f'{total:.2f}',
        'breakdown': {'item_total': {'currency_code': cur, 'value': f'{total:.2f}'}},
    }
    body = {
        'intent': 'CAPTURE',
        'purchase_units': [{'description': 'PayPilot AI order', 'items': pp_items, 'amount': amount}],
    }
    if vault_id:
        body['payment_source'] = {'paypal': {'vault_id': vault_id}}
    data = await request('POST', '/v2/checkout/orders', body)
    return {
        'order_id': data['id'],
        'status': data['status'],
        'approve_url': find_link(data),
        'capture_id': capture_id(data),
        'total': f'{total:.2f}',
        'currency': cur,
    }


async def capture_order(order_id):
    return await request('POST', '/v2/checkout/orders/' + order_id + '/capture', {})


async def refund_capture(capture, amount=None):
    body = {}
    if amount:
        body = {'amount': {'value': amount, 'currency_code': config.PAYPAL_CURRENCY}}
    data = await request('POST', '/v2/payments/captures/' + capture + '/refund', body)
    return data.get('status')


# Saved PayPal account (Vault v3): link once, then pay from chat
async def create_setup_token(return_url, cancel_url):
    body = {'payment_source': {'paypal': {
        'usage_type': 'MERCHANT',
        'customer_type': 'CONSUMER',
        'experience_context': {'return_url': return_url, 'cancel_url': cancel_url},
    }}}
    data = await request('POST', '/v3/vault/setup-tokens', body)
    return {'setup_token_id': data['id'], 'approve_url': find_link(data)}


async def create_payment_token(setup_token_id):
    body = {'payment_source': {'token': {'id': setup_token_id, 'type': 'SETUP_TOKEN'}}}
    data = await request('POST', '/v3/vault/payment-tokens', body)
    email = data.get('payment_source', {}).get('paypal', {}).get('email_address')
    return {'vault_id': data['id'], 'email': email}
