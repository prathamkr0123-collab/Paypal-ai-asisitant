import json
from pathlib import Path

# parents[0] = utils, [1] = app, [2] = backend
FILE = Path(__file__).resolve().parents[2] / 'products.json'

PRODUCTS = json.loads(FILE.read_text(encoding='utf-8'))
BY_ID = {p['id']: p for p in PRODUCTS}


def public(p):
    keys = ('id', 'name', 'price', 'emoji', 'description', 'category')
    return {k: p[k] for k in keys}
