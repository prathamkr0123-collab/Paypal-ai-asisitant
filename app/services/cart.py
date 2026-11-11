from decimal import Decimal

from app.utils.products import BY_ID, public


def add_item(session, product_id, qty=1):
    for line in session['cart']:
        if line['product_id'] == product_id:
            line['qty'] += qty
            break
    else:
        session['cart'].append({'product_id': product_id, 'qty': qty})
    session['last_product'] = product_id


def cart_view(session):
    items, total, count = [], Decimal('0'), 0
    for line in session['cart']:
        p = BY_ID[line['product_id']]
        sub = Decimal(p['price']) * line['qty']
        total += sub
        count += line['qty']
        items.append({**public(p), 'qty': line['qty'], 'subtotal': f'{sub:.2f}'})
    return {'items': items, 'total': f'{total:.2f}', 'count': count}
