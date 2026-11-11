from app.utils.products import PRODUCTS, BY_ID, public

# Words that carry no meaning for search
STOPWORDS = {
    'show', 'me', 'find', 'some', 'the', 'any', 'want', 'need', 'for', 'please',
    'search', 'looking', 'buy', 'get', 'and', 'with', 'have', 'you', 'what',
    'do', 'does', 'something', 'your', 'everything', 'all', 'products',
    'product', 'catalog', 'store', 'items', 'available', 'gear', 'stuff',
}


def search(query):
    words = [w for w in query.lower().replace(',', ' ').split()
             if len(w) >= 3 and w not in STOPWORDS]
    if not words:
        return PRODUCTS[:4]  # nothing specific asked: show a few products

    scored = []
    for p in PRODUCTS:
        text = ' '.join([p['name'], p['category'], p['description'], ' '.join(p['tags'])]).lower()
        tokens = {t.strip('.,-').rstrip('s') for t in text.replace('-', ' ').split()}
        score = sum(1 for w in words if w.rstrip('s') in tokens)
        if score:
            scored.append((score, p))

    scored.sort(key=lambda x: -x[0])  # best match first
    return [p for _, p in scored][:4]


def search_and_remember(session, query):
    results = search(query)
    if results:
        session['last_product'] = results[0]['id']  # this = top result
    return [public(p) for p in results]


def resolve_product_id(session, product_id=''):
    """'this' or 'it' arrives as an empty product_id, so fall back to last_product."""
    pid = product_id or session['last_product']
    return pid if pid in BY_ID else None
