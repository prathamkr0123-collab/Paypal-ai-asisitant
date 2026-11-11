// The Controller: listens to clicks and typing, calls the API, updates the Model, asks the View to draw.
import { api } from './api.js';
import { state, loadSession, addMessage, toggle, applyServerState } from './model.js';
import * as view from './view.js';

const $ = (id) => document.getElementById(id);
const draw = (scroll = false) => view.render(state, { scroll });

/* ---------- chat ---------- */
async function sendMessage(text) {
  text = (text || '').trim();
  if (!text || state.busy) return;
  addMessage({ role: 'user', text });
  state.busy = true;
  draw(true);
  try {
    const data = await api.chat(state.sessionId, text);
    applyServerState(data);
    const msg = {
      role: 'bot',
      text: data.reply || '…',
      products: data.products,
      confirm: data.confirm,
      payment: data.payment,
    };
    if (data.order) msg.approval = data.order;
    const saved = addMessage(msg);
    if (data.order) openPayModal(saved.approval);
    if (data.payment) view.toast('Payment complete', 'ok');
  } catch (e) {
    addMessage({ role: 'bot', text: 'Sorry, something went wrong: ' + e.message, error: true });
  } finally {
    state.busy = false;
    draw(true);
  }
}

/* ---------- cart / products (direct, no AI needed) ---------- */
async function refresh() {
  try {
    const [cart, orders, vault] = await Promise.all([
      api.cart(state.sessionId),
      api.orders(state.sessionId),
      api.vaultStatus(state.sessionId),
    ]);
    applyServerState({ cart, orders: orders.orders, vault_linked: vault.linked });
  } catch (e) {
    view.toast(e.message, 'error');
  }
}

async function addProducts(ids) {
  if (!ids.length) return;
  try {
    for (const id of ids) await api.addToCart(state.sessionId, id, 1);
    state.selProducts.clear();
    await refresh();
    addMessage({ role: 'bot', text: 'Added ' + ids.length + ' product' + (ids.length === 1 ? '' : 's') + ' to your cart. Say “make one order” or “pay for my cart” when you’re ready.' });
    draw(true);
  } catch (e) {
    view.toast(e.message, 'error');
  }
}

/* ---------- PayPal window (used when chat-pay is not linked) ---------- */
let sdkPromise = null;

function loadPayPalSdk() {
  if (window.paypal) return Promise.resolve();
  if (sdkPromise) return sdkPromise;
  const { paypal_client_id: id, currency } = state.config;
  if (!id) return Promise.reject(new Error('PayPal is not configured on the server (missing client id).'));
  sdkPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://www.paypal.com/sdk/js?client-id=' + encodeURIComponent(id)
      + '&currency=' + encodeURIComponent(currency || 'USD')
      + '&components=buttons&disable-funding=card,credit,paylater,venmo';
    s.onload = resolve;
    s.onerror = () => { sdkPromise = null; reject(new Error('Could not load the PayPal SDK.')); };
    document.head.appendChild(s);
  });
  return sdkPromise;
}

async function openPayModal(order) {
  view.showModal(order);
  try {
    await loadPayPalSdk();
  } catch (e) {
    view.setModalStatus(e.message, 'error');
    return;
  }
  $('paypalButtons').innerHTML = '';
  window.paypal.Buttons({
    style: { layout: 'vertical', shape: 'pill', label: 'pay' },
    createOrder: () => order.order_id,   // the server already created it
    onApprove: async (data) => {
      view.setModalStatus('Confirming your payment…');
      try {
        const res = await api.captureOrder(state.sessionId, data.orderID);
        view.hideModal();
        await refresh();
        addMessage({
          role: 'bot',
          text: 'Payment successful. Thank you!',
          payment: { total: res.total, orders: res.orders, capture_id: res.capture_id },
        });
        view.toast('Payment complete', 'ok');
        draw(true);
      } catch (e) {
        view.setModalStatus(e.message, 'error');
      }
    },
    onCancel: () => view.setModalStatus('Payment window closed. Your orders are still pending.'),
    onError: (err) => view.setModalStatus('PayPal error: ' + ((err && err.message) || err), 'error'),
  }).render('#paypalButtons');
}

/* ---------- saved PayPal (chat-pay) ---------- */
async function toggleVault() {
  try {
    if (state.vaultLinked) {
      await api.vaultUnlink(state.sessionId);
      state.vaultLinked = false;
      view.toast('Chat-pay turned off');
      draw();
      return;
    }
    const res = await api.vaultStart(state.sessionId);
    if (!res.approve_url) throw new Error('PayPal did not return a link page.');
    window.location.href = res.approve_url;   // comes back to /?vault=success
  } catch (e) {
    view.toast(e.message, 'error');
  }
}

async function handleVaultReturn() {
  const params = new URLSearchParams(window.location.search);
  const v = params.get('vault');
  if (!v) return;
  history.replaceState({}, '', window.location.pathname);
  if (v === 'success') {
    try {
      const res = await api.vaultComplete(state.sessionId);
      state.vaultLinked = !!res.linked;
      view.toast('PayPal linked. I can now pay in chat, after you confirm.', 'ok');
    } catch (e) {
      view.toast(e.message, 'error');
    }
  } else {
    view.toast('PayPal linking was cancelled.');
  }
}

/* ---------- clicks ---------- */
function findMessage(el) {
  const id = Number(el.dataset.msg);
  return state.messages.find((m) => m.id === id);
}

function lastBotMessage() {
  return [...state.messages].reverse().find((m) => m.role === 'bot' && m.confirm && !m.confirmDone);
}

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el || el.tagName === 'INPUT') return;
  const a = el.dataset.action;
  const ids = [...state.selOrders].join(', ');

  switch (a) {
    case 'chip': sendMessage(el.dataset.text); break;
    case 'add-product': addProducts([el.dataset.id]); break;
    case 'add-selected': addProducts([...state.selProducts]); break;
    case 'cart-order': sendMessage('Make one order from my cart'); break;
    case 'cart-separate': sendMessage('Make separate orders, one per item, from my cart'); break;
    case 'cart-pay': sendMessage('Checkout my cart'); break;
    case 'pay-orders': state.selOrders.clear(); sendMessage('Pay orders ' + ids); break;
    case 'cancel-orders': state.selOrders.clear(); sendMessage('Cancel orders ' + ids); break;
    case 'confirm-yes': { const m = lastBotMessage(); if (m) m.confirmDone = true; sendMessage('Yes'); break; }
    case 'confirm-no': { const m = lastBotMessage(); if (m) m.confirmDone = true; sendMessage('No, leave it'); break; }
    case 'open-pay': { const m = findMessage(el); if (m && m.approval) openPayModal(m.approval); break; }
    case 'modal-close': view.hideModal(); break;
    default: break;
  }
});

document.addEventListener('change', (e) => {
  const el = e.target;
  if (el.dataset.action === 'toggle-product') { toggle(state.selProducts, el.dataset.id); draw(); }
  if (el.dataset.action === 'toggle-order') { toggle(state.selOrders, el.dataset.id); draw(); }
});

/* ---------- start ---------- */
async function init() {
  loadSession();
  view.initStatic();
  try { state.config = await api.config(); } catch (e) { view.toast('Could not load settings from the server.', 'error'); }
  addMessage({
    role: 'bot',
    text: 'Hi, I’m **PayPilot**. Tell me what you’re after, pick a few things, and I’ll handle the order, the payment and any cancellation. Try one of the prompts below.',
  });
  await handleVaultReturn();
  await refresh();
  draw(true);

  $('composer').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('input');
    const v = input.value;
    input.value = '';
    sendMessage(v);
  });
  $('vaultBtn').addEventListener('click', toggleVault);
  $('modal').addEventListener('click', (e) => { if (e.target.id === 'modal') view.hideModal(); });
}

init();
