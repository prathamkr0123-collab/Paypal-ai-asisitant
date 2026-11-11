from fastapi import APIRouter, HTTPException

from app.models.schemas import AddIn
from app.services.cart import add_item, cart_view
from app.utils import store
from app.utils.products import BY_ID

router = APIRouter()


@router.post('/cart/add')
async def cart_add(body: AddIn):
    if body.product_id not in BY_ID:
        raise HTTPException(404, 'Unknown product')
    session = store.get_session(body.session_id)
    add_item(session, body.product_id, max(1, body.quantity))
    return cart_view(session)


@router.get('/cart/{session_id}')
async def get_cart(session_id: str):
    return cart_view(store.get_session(session_id))
