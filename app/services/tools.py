"""The tools the AI can call. The AI only CHOOSES a tool. This code does the work
and enforces the safety rules (confirm before any payment or refund)."""
import json

from langchain_core.tools import tool

from app.services import orders as ords
from app.services import paypal
from app.services.cart import add_item, cart_view
from app.services.catalog import resolve_product_id, search_and_remember
from app.services.help import HELP_TEXT
from app.utils.products import BY_ID, public


def j(data):
    return json.dumps(data)


def make_tools(session, ui):
    '''Build the tools for ONE user, so they can see this user session.'''

    def resolve_ids(product_ids):
        '''Check ids. No ids means this / it, the last product shown.'''
        ids = []
        for pid in product_ids or []:
            if pid not in BY_ID:
                return [], 'Unknown product id ' + pid
            ids.append(pid)
        if not ids:
            pid = resolve_product_id(session)
            if not pid:
                return [], 'No product selected. Ask which product they mean.'
            ids = [pid]
        return ids, None

    def create_from(product_ids, separate):
        '''Make orders from the given products, else the cart, else this / it.'''
        if product_ids:
            ids, err = resolve_ids(product_ids)
            if err:
                return [], err
            lines = ords.lines_from_ids(ids)
        elif session['cart']:
            lines = ords.lines_from_cart(session)
        else:
            ids, err = resolve_ids(None)
            if err:
                return [], err
            lines = ords.lines_from_ids(ids)
        created = ords.place_orders(session, lines, separate)
        taken = {line['product_id'] for line in lines}
        session['cart'] = [c for c in session['cart'] if c['product_id'] not in taken]
        return created, None

    @tool
    def search_products(query: str) -> str:
        '''Search the store catalog by keyword, for example headphones. Use for any browse, find or show request.'''
        results = search_and_remember(session, query)
        ui['products'] = results
        return j({'products': results})

    @tool
    def add_to_cart(product_ids: list[str] | None = None, quantity: int = 1) -> str:
        '''Add one or more products to the cart. Pass all ids when the user selects several products. If the user says this or it, leave product_ids empty.'''
        ids, err = resolve_ids(product_ids)
        if err:
            return j({'error': err})
        for pid in ids:
            add_item(session, pid, max(1, quantity))
        return j({'added': [public(BY_ID[p]) for p in ids], 'cart': cart_view(session)})

    @tool
    def remove_from_cart(product_ids: list[str] | None = None) -> str:
        '''Remove products from the cart. Leave product_ids empty for this or it.'''
        ids, err = resolve_ids(product_ids)
        if err:
            return j({'error': err})
        session['cart'] = [c for c in session['cart'] if c['product_id'] not in ids]
        return j({'cart': cart_view(session)})

    @tool
    def view_cart() -> str:
        '''Show the cart contents and total.'''
        return j({'cart': cart_view(session)})

    @tool
    def place_order(product_ids: list[str] | None = None, separate: bool = False) -> str:
        '''Create an order WITHOUT paying yet. With no product_ids it uses the whole cart, or this/it if the cart is empty. Set separate=true only when the user wants one order per product.'''
        created, err = create_from(product_ids, separate)
        if err:
            return j({'error': err})
        ui['touched'] = created
        return j({'created': created})

    @tool
    def list_orders(status: str = '') -> str:
        '''List the user orders. status can be pending, paid, cancelled or refunded. Leave it empty for all orders.'''
        rows = [o for o in session['orders'] if not status or o['status'] == status.lower()]
        ui['touched'] = rows
        return j({'orders': rows})

    @tool
    def get_order(order_id: str) -> str:
        '''Show the details of one order, for example ORD-2.'''
        found, missing = ords.get_orders(session, [order_id])
        if missing:
            return j({'error': 'Unknown order ' + order_id})
        ui['touched'] = found
        return j({'order': found[0]})

    @tool
    async def checkout(product_ids: list[str] | None = None, order_ids: list[str] | None = None, separate: bool = False) -> str:
        '''Pay for orders. Call this when the user says pay, checkout, buy this, or similar. Pay existing orders with order_ids, or buy products directly with product_ids (several allowed). With neither, a non-empty cart becomes an order, otherwise ALL pending orders are paid. If the user says this or it, leave both empty.'''
        if order_ids:
            targets, missing = ords.get_orders(session, order_ids)
            if missing:
                return j({'error': 'Unknown order(s): ' + ', '.join(missing)})
        elif product_ids or session['cart']:
            targets, err = create_from(product_ids, separate)
            if err:
                return j({'error': err})
        elif ords.pending_orders(session):
            targets = ords.pending_orders(session)
        else:
            targets, err = create_from(None, separate)
            if err:
                return j({'error': err})

        if not targets:
            return j({'error': 'No orders to pay.'})
        bad = [o['id'] + ' is ' + o['status'] for o in targets if o['status'] != 'pending']
        if bad:
            return j({'error': 'Cannot pay: ' + ', '.join(bad)})

        ids = [o['id'] for o in targets]
        total = ords.orders_total(targets)
        items = ords.paypal_items(targets)
        ui['touched'] = targets

        # Path A: no saved PayPal. Make a PayPal order; the buyer approves it in the PayPal window.
        if not session['vault_id']:
            try:
                pp = await paypal.create_order(items)
            except paypal.PayPalError as e:
                return j({'error': 'Could not create PayPal order: ' + str(e)})
            for o in targets:
                o['paypal_order_id'] = pp['order_id']
            pp['order_ids'] = ids
            session['pending_order'] = pp
            ui['order'] = pp
            return j({'status': 'approval_needed', 'orders': ids, 'total': total,
                      'note': 'Tell the user to approve the payment in the PayPal window.'})

        # Path B: saved PayPal. Pay inside the chat, but only after a yes in the NEXT message.
        if ords.needs_confirm(session, 'pay', ids, total):
            ui['confirm'] = {'action': 'pay', 'orders': ids, 'total': total}
            return j({'status': 'needs_confirmation', 'orders': ids, 'total': total,
                      'note': 'Ask the user to reply yes to pay. When they do, call checkout again with order_ids set to these orders.'})

        try:
            pp = await paypal.create_order(items, vault_id=session['vault_id'])
            if pp['status'] != 'COMPLETED':
                cap = await paypal.capture_order(pp['order_id'])
                pp['status'] = cap.get('status')
                pp['capture_id'] = paypal.capture_id(cap)
        except paypal.PayPalError as e:
            return j({'error': 'Payment failed: ' + str(e)})
        if pp['status'] != 'COMPLETED':
            return j({'error': 'Payment not completed (status ' + str(pp['status']) + ').'})
        for o in targets:
            o['status'] = 'paid'
            o['paypal_order_id'] = pp['order_id']
            o['capture_id'] = pp['capture_id']
        ui['payment'] = {'status': 'COMPLETED', 'orders': ids, 'total': total,
                         'capture_id': pp['capture_id']}
        return j({'status': 'paid', 'orders': ids, 'total': total})

    @tool
    async def cancel_order(order_ids: list[str]) -> str:
        '''Cancel one or more orders, for example ORD-1. An unpaid order is just cancelled. A paid order is refunded to the buyer PayPal after the user confirms.'''
        found, missing = ords.get_orders(session, order_ids)
        if missing:
            return j({'error': 'Unknown order(s): ' + ', '.join(missing)})
        result = {'cancelled': [], 'refunded': [], 'skipped': []}
        paid = []
        for o in found:
            if o['status'] == 'pending':
                o['status'] = 'cancelled'
                result['cancelled'].append(o['id'])
            elif o['status'] == 'paid':
                paid.append(o)
            else:
                result['skipped'].append(o['id'] + ' is already ' + o['status'])

        if paid:
            ids = [o['id'] for o in paid]
            total = ords.orders_total(paid)
            if ords.needs_confirm(session, 'refund', ids, total):
                ui['confirm'] = {'action': 'refund', 'orders': ids, 'total': total}
                result['status'] = 'needs_confirmation'
                result['note'] = 'Ask the user to reply yes to refund these paid orders. When they do, call cancel_order again with the same order_ids. Never refund without that yes.'
            else:
                for o in paid:
                    try:
                        await paypal.refund_capture(o['capture_id'], o['total'])
                    except paypal.PayPalError as e:
                        result['skipped'].append(o['id'] + ': refund failed: ' + str(e))
                        continue
                    o['status'] = 'refunded'
                    result['refunded'].append(o['id'])
        ui['touched'] = found
        return j(result)

    @tool
    def order_help(question: str) -> str:
        '''Use for any question about how orders, order types, payment, cancelling or refunds work.'''
        return HELP_TEXT

    return [search_products, add_to_cart, remove_from_cart, view_cart, place_order,
            list_orders, get_order, checkout, cancel_order, order_help]
