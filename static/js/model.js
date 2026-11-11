// The Model: all app state lives here. No DOM code in this file.
export const state = {
  sessionId: null,
  config: { paypal_client_id: '', currency: 'USD' },
  messages: [],            // chat transcript shown on screen
  cart: { items: [], total: '0.00', count: 0 },
  orders: [],
  vaultLinked: false,
  selProducts: new Set(),  // product ids ticked in the chat cards
  selOrders: new Set(),    // order ids ticked in the Orders panel
  busy: false,
};

const KEY = 'paypilot.session';

export function loadSession() {
  let id = null;
  try { id = localStorage.getItem(KEY); } catch (e) { /* storage blocked */ }
  if (!id) {
    id = (window.crypto && crypto.randomUUID)
      ? crypto.randomUUID().replace(/-/g, '')
      : Date.now().toString(16) + Math.random().toString(16).slice(2);
    try { localStorage.setItem(KEY, id); } catch (e) { /* ignore */ }
  }
  state.sessionId = id;
  return id;
}

let nextId = 1;
export function addMessage(msg) {
  const m = { id: nextId++, ...msg };
  state.messages.push(m);
  return m;
}

export function toggle(set, id) {
  if (set.has(id)) set.delete(id); else set.add(id);
}

// Take what the server returned and update the state
export function applyServerState(data) {
  if (data.cart) state.cart = data.cart;
  if (data.orders) {
    state.orders = data.orders;
    const live = new Set(state.orders.map((o) => o.id));
    for (const id of [...state.selOrders]) if (!live.has(id)) state.selOrders.delete(id);
  }
  if (typeof data.vault_linked === 'boolean') state.vaultLinked = data.vault_linked;
}
