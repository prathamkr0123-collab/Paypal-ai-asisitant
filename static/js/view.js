// The View: turns state into HTML. It never calls the API.
const $ = (id) => document.getElementById(id);

let CUR = 'USD';

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

const fmt = (v) => (CUR === 'USD' ? '$' + Number(v).toFixed(2) : Number(v).toFixed(2) + ' ' + CUR);

function text(t) {
  return esc(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
}

/* ---------------- chat ---------------- */
function productsHtml(m, state) {
  const cards = m.products.map((p) => {
    const sel = state.selProducts.has(p.id);
    return `
      <div class="pcard ${sel ? 'sel' : ''}">
        <input class="pick" type="checkbox" data-action="toggle-product" data-id="${esc(p.id)}" ${sel ? 'checked' : ''} aria-label="Select ${esc(p.name)}">
        <div class="tile cat-${esc(p.category)}">${esc(p.emoji)}</div>
        <div class="pname">${esc(p.name)}</div>
        <div class="pdesc">${esc(p.description)}</div>
        <div class="pfoot">
          <span class="price">${fmt(p.price)}</span>
          <button class="btn ghost small" type="button" data-action="add-product" data-id="${esc(p.id)}">Add</button>
        </div>
      </div>`;
  }).join('');
  const n = state.selProducts.size;
  return `
    <div class="products">${cards}</div>
    <div class="picker-bar">
      <button class="btn primary small" type="button" data-action="add-selected" ${n ? '' : 'disabled'}>Add selected${n ? ' (' + n + ')' : ''}</button>
      <span>Tick several products to add them together.</span>
    </div>`;
}

function confirmHtml(m) {
  const c = m.confirm;
  const isRefund = c.action === 'refund';
  const verb = isRefund ? 'Refund' : 'Pay';
  const done = m.confirmDone;
  return `
    <div class="callout confirm">
      <div class="title">${verb} ${fmt(c.total)}?</div>
      <div class="sub">${esc((c.orders || []).join(', '))}${isRefund ? ' · refunded to your PayPal' : ' · charged to your linked PayPal'}</div>
      <div class="btns">
        <button class="btn primary small" type="button" data-action="confirm-yes" ${done ? 'disabled' : ''}>Yes, ${verb.toLowerCase()}</button>
        <button class="btn ghost small" type="button" data-action="confirm-no" ${done ? 'disabled' : ''}>No</button>
      </div>
    </div>`;
}

function approvalHtml(m) {
  const o = m.approval;
  return `
    <div class="callout approve">
      <div class="title">Approve ${fmt(o.total)} with PayPal</div>
      <div class="sub">${esc((o.order_ids || []).join(', '))}</div>
      <div class="btns"><button class="btn primary small" type="button" data-action="open-pay" data-msg="${m.id}">Open PayPal</button></div>
    </div>`;
}

function paidHtml(m) {
  const p = m.payment;
  return `
    <div class="callout paid">
      <div class="title">Paid ${fmt(p.total)} ✓</div>
      <div class="sub">${esc((p.orders || []).join(', '))}${p.capture_id ? ' · PayPal ref ' + esc(p.capture_id) : ''}</div>
    </div>`;
}

function messageHtml(m, state) {
  if (m.role === 'user') {
    return `<div class="row user"><div class="bubble">${esc(m.text)}</div></div>`;
  }
  let inner = `<div class="bubble ${m.error ? 'error' : ''}">${text(m.text)}</div>`;
  if (m.products && m.products.length) inner += productsHtml(m, state);
  if (m.confirm) inner += confirmHtml(m);
  if (m.approval) inner += approvalHtml(m);
  if (m.payment) inner += paidHtml(m);
  return `<div class="row bot"><div class="avatar" aria-hidden="true">P</div><div class="stack">${inner}</div></div>`;
}

const typingHtml = `<div class="row bot"><div class="avatar" aria-hidden="true">P</div><div class="stack"><div class="bubble typing" aria-label="PayPilot is typing"><i></i><i></i><i></i></div></div></div>`;

function renderMessages(state, scroll) {
  const box = $('messages');
  box.innerHTML = state.messages.map((m) => messageHtml(m, state)).join('') + (state.busy ? typingHtml : '');
  if (scroll) box.scrollTop = box.scrollHeight;
}

const CHIPS = [
  'Show me something for music',
  'Add the headphones and the speaker',
  'Make one order from my cart',
  'Pay for my cart',
  'Show my orders',
  'How do refunds work?',
];

function renderChips() {
  $('chips').innerHTML = CHIPS.map((c) => `<button type="button" data-action="chip" data-text="${esc(c)}">${esc(c)}</button>`).join('');
}

/* ---------------- side panels ---------------- */
function renderCart(state) {
  const c = state.cart;
  const has = c.items.length > 0;
  const lines = c.items.map((i) => `
    <li><span class="em">${esc(i.emoji)}</span>
      <span class="nm">${esc(i.name)}<small>${i.qty} × ${fmt(i.price)}</small></span>
      <strong>${fmt(i.subtotal)}</strong></li>`).join('');
  $('cartPanel').innerHTML = `
    <h3>Cart <span class="count">${c.count} item${c.count === 1 ? '' : 's'}</span></h3>
    ${has ? `<ul class="lines">${lines}</ul>
      <div class="total-row"><span>Total</span><span class="price">${fmt(c.total)}</span></div>` : '<p class="empty">Your cart is empty. Ask me to find something.</p>'}
    <div class="btn-row">
      <button class="btn ghost small" type="button" data-action="cart-order" ${has ? '' : 'disabled'}>Order together</button>
      <button class="btn ghost small" type="button" data-action="cart-separate" ${has ? '' : 'disabled'}>Order separately</button>
      <button class="btn primary small" type="button" data-action="cart-pay" ${has ? '' : 'disabled'}>Pay now</button>
    </div>`;
}

function orderHtml(o, state) {
  const sel = state.selOrders.has(o.id);
  const items = o.items.map((i) => `<li>${i.qty} × ${esc(i.name)}</li>`).join('');
  return `
    <label class="order ${sel ? 'sel' : ''}">
      <input type="checkbox" data-action="toggle-order" data-id="${esc(o.id)}" ${sel ? 'checked' : ''}>
      <div class="order-body">
        <div class="order-head">
          <strong>${esc(o.id)}</strong>
          <span class="badge type">${o.type === 'multi' ? 'Multi' : 'Single'}</span>
          <span class="badge st-${esc(o.status)}">${esc(o.status)}</span>
        </div>
        <ul>${items}</ul>
        <div class="otot">${fmt(o.total)}</div>
      </div>
    </label>`;
}

function renderOrders(state) {
  const orders = [...state.orders].reverse();
  const n = state.selOrders.size;
  $('ordersPanel').innerHTML = `
    <h3>Orders <span class="count">${orders.length}</span></h3>
    ${orders.length ? orders.map((o) => orderHtml(o, state)).join('') : '<p class="empty">No orders yet. Ask me to make one from your cart.</p>'}
    <div class="btn-row">
      <button class="btn primary small" type="button" data-action="pay-orders" ${n ? '' : 'disabled'}>Pay selected${n ? ' (' + n + ')' : ''}</button>
      <button class="btn ghost small" type="button" data-action="cancel-orders" ${n ? '' : 'disabled'}>Cancel selected</button>
    </div>`;
}

function renderVault(state) {
  const b = $('vaultBtn');
  b.textContent = state.vaultLinked ? 'Chat-pay on · unlink' : 'Link PayPal for chat-pay';
  b.classList.toggle('on', state.vaultLinked);
}

export function render(state, opts = {}) {
  CUR = state.config.currency || 'USD';
  renderMessages(state, !!opts.scroll);
  renderCart(state);
  renderOrders(state);
  renderVault(state);
  $('sendBtn').disabled = state.busy;
}

export function initStatic() {
  renderChips();
}

/* ---------------- modal + toasts ---------------- */
export function showModal(order) {
  $('modalTotal').textContent = fmt(order.total);
  $('modalOrders').textContent = (order.order_ids || []).join(', ');
  setModalStatus('');
  $('paypalButtons').innerHTML = '';
  $('modal').classList.remove('hidden');
}

export function hideModal() {
  $('modal').classList.add('hidden');
}

export function setModalStatus(msg, kind) {
  const el = $('modalStatus');
  el.textContent = msg || '';
  el.className = 'modal-status' + (kind === 'error' ? ' error' : '');
}

export function toast(msg, kind = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.textContent = msg;
  $('toasts').appendChild(el);
  setTimeout(() => el.remove(), 4200);
}
