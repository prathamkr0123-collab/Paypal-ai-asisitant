from fastapi import APIRouter, HTTPException

from app.models.schemas import CaptureIn, CreateOrderIn, SessionIn
from app.services import orders as ords
from app.services import paypal
from app.utils import config, store
from app.utils.products import BY_ID

router = APIRouter()


@router.get('/orders/{session_id}')
async def list_orders(session_id: str):
    return {'orders': store.get_session(session_id)['orders']}


@router.post('/create-order')
async def create_order(body: CreateOrderIn):
    '''PayPal order made directly (no AI). Handy for tests and Postman.'''
    session = store.get_session(body.session_id)
    if body.order_ids:
        targets, missing = ords.get_orders(session, body.order_ids)
        if missing:
            raise HTTPException(404, 'Unknown order(s): ' + ', '.join(missing))
    else:
        if not body.product_ids or any(p not in BY_ID for p in body.product_ids):
            raise HTTPException(400, 'Send valid product_ids or order_ids')
        lines = ords.lines_from_ids(body.product_ids)
        targets = ords.place_orders(session, lines, body.separate)
    if not targets or any(o['status'] != 'pending' for o in targets):
        raise HTTPException(400, 'Only pending orders can be paid')
    try:
        pp = await paypal.create_order(ords.paypal_items(targets))
    except paypal.PayPalError as e:
        raise HTTPException(502, str(e))
    for o in targets:
        o['paypal_order_id'] = pp['order_id']
    pp['order_ids'] = [o['id'] for o in targets]
    session['pending_order'] = pp
    return pp


@router.post('/capture-order')
async def capture_order(body: CaptureIn):
    '''Called by the website after the buyer approves in the PayPal window.'''
    session = store.get_session(body.session_id)
    targets = [o for o in session['orders']
               if o['paypal_order_id'] == body.order_id and o['status'] == 'pending']
    if not targets:
        raise HTTPException(409, 'No pending orders match this PayPal order (maybe cancelled).')
    try:
        data = await paypal.capture_order(body.order_id)
    except paypal.PayPalError as e:
        raise HTTPException(502, str(e))
    status = data.get('status')
    if status != 'COMPLETED':
        return {'status': status, 'message': 'Payment status: ' + str(status)}
    cap = paypal.capture_id(data)
    for o in targets:
        o['status'] = 'paid'
        o['capture_id'] = cap
    session['pending_order'] = None
    return {'status': status, 'capture_id': cap, 'orders': [o['id'] for o in targets],
            'total': ords.orders_total(targets), 'message': 'Payment successful!'}


# ---- Saved PayPal account (Vault): link once, then pay from chat ----

@router.get('/vault/status/{session_id}')
async def vault_status(session_id: str):
    return {'linked': bool(store.get_session(session_id)['vault_id'])}


@router.post('/vault/start')
async def vault_start(body: SessionIn):
    session = store.get_session(body.session_id)
    try:
        res = await paypal.create_setup_token(
            config.FRONTEND_URL + '/?vault=success',
            config.FRONTEND_URL + '/?vault=cancel',
        )
    except paypal.PayPalError as e:
        raise HTTPException(502, str(e))
    session['setup_token_id'] = res['setup_token_id']
    return res


@router.post('/vault/complete')
async def vault_complete(body: SessionIn):
    session = store.get_session(body.session_id)
    if not session['setup_token_id']:
        raise HTTPException(400, 'No link in progress. Start linking first.')
    try:
        res = await paypal.create_payment_token(session['setup_token_id'])
    except paypal.PayPalError as e:
        raise HTTPException(502, str(e))
    session['vault_id'] = res['vault_id']
    session['setup_token_id'] = None
    return {'linked': True, 'email': res['email']}


@router.post('/vault/unlink')
async def vault_unlink(body: SessionIn):
    session = store.get_session(body.session_id)
    session['vault_id'] = None
    session['pending_confirm'] = None
    return {'linked': False}
