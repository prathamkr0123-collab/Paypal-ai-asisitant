from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import cart, chat, payment, products, system
from app.utils import config

app = FastAPI(
    title='PayPilot AI',
    description='Chat to shop, chat to pay. AI shopping assistant with PayPal sandbox checkout.',
    version='1.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGIN.split(','),
    allow_methods=['*'],
    allow_headers=['*'],
)

# Controllers (API routes)
app.include_router(system.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(chat.router)
app.include_router(payment.router)

# Views: the website, served by the same app (monolith). Mounted last so API routes win.
STATIC_DIR = Path(__file__).resolve().parent / 'static'
app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='site')
