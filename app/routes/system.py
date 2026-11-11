from fastapi import APIRouter

from app.utils import config
from app.utils.llm import test

router = APIRouter()


@router.get('/health')
def health():
    return {'status': 'success', 'message': 'PayPilot AI is healthy'}


@router.get('/config')
def public_config():
    '''Values the website needs. The PayPal client id is public by design. The secret never leaves the server.'''
    return {
        'app': 'PayPilot AI',
        'paypal_client_id': config.PAYPAL_CLIENT_ID,
        'currency': config.PAYPAL_CURRENCY,
    }


@router.get('/test')
def test_llm():
    return {'response': test()}
