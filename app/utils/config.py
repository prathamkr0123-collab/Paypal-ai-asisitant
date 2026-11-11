import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env (on Render the values come from the dashboard instead)
ENV_PATH = Path(__file__).resolve().parents[2] / '.env'
load_dotenv(ENV_PATH)

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')
PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET')
PAYPAL_CURRENCY = os.getenv('PAYPAL_CURRENCY', 'USD')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:8000').rstrip('/')
FRONTEND_ORIGIN = os.getenv('FRONTEND_ORIGIN', '*')
