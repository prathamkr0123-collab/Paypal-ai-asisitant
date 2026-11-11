import uuid

_sessions = {}


def new_session_id():
    return uuid.uuid4().hex


def get_session(session_id):
    return _sessions.setdefault(session_id, {
        'cart': [],               # [{'product_id': 'p1', 'qty': 1}]
        'last_product': None,     # what this / it means
        'history': [],            # recent chat messages
        'turn': 0,                # counts chat messages (used by the confirm gate)
        'orders': [],             # all orders of this user
        'order_seq': 0,           # makes ORD-1, ORD-2, ...
        'pending_order': None,    # last PayPal order made for this session
        'vault_id': None,         # saved PayPal account
        'setup_token_id': None,   # PayPal link in progress
        'pending_confirm': None,  # waiting for the user to say yes
    })
