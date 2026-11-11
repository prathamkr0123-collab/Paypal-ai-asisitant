// Talks to the backend. Same origin, so no base URL is needed.
async function req(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  let data = {};
  try { data = await res.json(); } catch (e) { /* empty body */ }
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : '';
    throw new Error(detail || 'Request failed (' + res.status + ')');
  }
  return data;
}

const post = (path, body) => req(path, { method: 'POST', body: JSON.stringify(body) });

export const api = {
  config: () => req('/config'),
  chat: (sessionId, message) => post('/chat', { session_id: sessionId, message }),
  cart: (sid) => req('/cart/' + encodeURIComponent(sid)),
  addToCart: (sid, productId, quantity = 1) => post('/cart/add', { session_id: sid, product_id: productId, quantity }),
  orders: (sid) => req('/orders/' + encodeURIComponent(sid)),
  captureOrder: (sid, orderId) => post('/capture-order', { session_id: sid, order_id: orderId }),
  vaultStatus: (sid) => req('/vault/status/' + encodeURIComponent(sid)),
  vaultStart: (sid) => post('/vault/start', { session_id: sid }),
  vaultComplete: (sid) => post('/vault/complete', { session_id: sid }),
  vaultUnlink: (sid) => post('/vault/unlink', { session_id: sid }),
};
