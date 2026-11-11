from fastapi import APIRouter

from app.models.schemas import ChatIn
from app.services.agent import run_agent
from app.services.cart import cart_view
from app.utils import store

router = APIRouter()


@router.post('/chat')
async def chat(body: ChatIn):
    session_id = body.session_id or store.new_session_id()
    session = store.get_session(session_id)
    result = await run_agent(session, body.message)
    return {
        'session_id': session_id,
        'cart': cart_view(session),
        'orders': session['orders'],
        'vault_linked': bool(session['vault_id']),
        **result,
    }
