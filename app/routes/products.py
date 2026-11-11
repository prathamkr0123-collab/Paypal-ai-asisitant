from fastapi import APIRouter

from app.utils.products import PRODUCTS

router = APIRouter()


@router.get('/products')
async def list_products():
    return PRODUCTS
