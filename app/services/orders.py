from datetime import datetime, timezone
from decimal import Decimal

from app.utils.products import BY_ID


def money(value):
    return f'{value:.2f}'


def normalize_id(raw):
    key = str(raw).strip().upper().replace(' ', '-')
    return 'ORD-' + key if key.isdigit() else key


def _line(product_id, qty):
    p = BY_ID[product_id]
    return {'product_id': product_id, 'name': p['name'], 'emoji': p['emoji'],
            'price': p['price'], 'qty': qty}


def lines_from_ids(product_ids):
    qty = {}
    for pid in product_ids:
        qty[pid] = qty.get(pid, 0) + 1
    return [_line(pid, q) for pid, q in qty.items()]


def lines_from_cart(session):
    return [_line(c['product_id'], c['qty']) for c in session['cart']]


def new_order(session, lines, order_type):
    total = Decimal('0')
    for line in lines:
        total += Decimal(line['price']) * line['qty']
    session['order_seq'] += 1
    order = {
        'id': 'ORD-' + str(session['order_seq']),
        'type': order_type,
        'items': lines,
        'total': money(total),
        'status': 'pending',
        'paypal_order_id': None,
        'capture_id': None,
        'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    session['orders'].append(order)
    return order


def place_orders(session, lines, separate=False):
    '''separate=True makes one single order per product, otherwise one order.'''
    groups = [[line] for line in lines] if separate else [lines]
    return [new_order(session, g, 'single' if len(g) == 1 else 'multi') for g in groups]


def get_orders(session, ids):
    by_id = {o['id']: o for o in session['orders']}
    found, missing = [], []
    for raw in ids or []:
        key = normalize_id(raw)
        if key in by_id:
            found.append(by_id[key])
        else:
            missing.append(str(raw))
    return found, missing


def pending_orders(session):
    return [o for o in session['orders'] if o['status'] == 'pending']


def orders_total(orders):
    total = Decimal('0')
    for o in orders:
        total += Decimal(o['total'])
    return money(total)


def paypal_items(orders):
    return [{'name': i['name'], 'price': i['price'], 'qty': i['qty']}
            for o in orders for i in o['items']]


def needs_confirm(session, action, ids, total):
    '''True means ask the user first.

    The action only runs when the SAME request comes back in the VERY NEXT
    user message (a yes). Anything else, or waiting longer, asks again.
    '''
    key = {'action': action, 'ids': sorted(ids), 'total': total}
    pend = session['pending_confirm']
    if pend and pend['key'] == key and session['turn'] == pend['turn'] + 1:
        session['pending_confirm'] = None
        return False
    session['pending_confirm'] = {'key': key, 'turn': session['turn']}
    return True
