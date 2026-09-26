const KEY = "sd_farm_cart_v3";
const get = () => JSON.parse(localStorage.getItem(KEY) || "{}");
const save = (c) => {
  localStorage.setItem(KEY, JSON.stringify(c));
  count();
  render();
  checkout();
};
const money = (n) => "Rs. " + Math.round(n).toLocaleString("en-IN");
function count() {
  let n = Object.values(get()).reduce((a, x) => a + x.qty, 0);
  document.querySelectorAll("#cart-count").forEach((e) => (e.textContent = n));
}
const draftQty = {};
function selectedQty(id) { return draftQty[id] ?? 0; }
function updateDraft(id, delta) {
  draftQty[id] = Math.max(0, Math.min(100, selectedQty(id) + delta));
  const el = document.getElementById("qty-" + id);
  if (el) el.textContent = draftQty[id];
  previewCart();
}
function previewCart() {
  const el = document.querySelector("#cart-subtotal");
  if (!el) return;
  const cart = get();
  document.querySelectorAll(".cart-add[data-id]").forEach(b => {
    const id = b.dataset.id;
    const qty = selectedQty(id);
    if (qty) {
      const existing = cart[id]?.qty || 0;
      cart[id] = { id, name:b.dataset.name, price:+b.dataset.price, unit:b.dataset.unit, qty:existing+qty };
    }
  });
  const total = Object.values(cart).reduce((n,x)=>n+x.price*x.qty,0);
  el.textContent = money(total);
}
function add(b) {
  let c = get(),
    id = b.dataset.id;
  if (!c[id])
    c[id] = {
      id,
      name: b.dataset.name,
      price: +b.dataset.price,
      unit: b.dataset.unit,
      qty: 0,
    };
  const qty = selectedQty(id) || 1;
  c[id].qty += qty;
  draftQty[id] = 0;
  const label = document.getElementById("qty-" + id);
  if (label) label.textContent = 0;
  save(c);
}
function change(id, d) {
  let c = get();
  if (!c[id]) return;
  c[id].qty += d;
  if (c[id].qty <= 0) delete c[id];
  save(c);
}
function render() {
  let box = document.querySelector("#cart-lines");
  if (!box) return;
  let c = get(),
    a = Object.values(c),
    t = 0;
  if (!a.length) {
    box.innerHTML = "<p>Your cart is empty.</p>";
  } else
    box.innerHTML = a
      .map((x) => {
        let l = x.price * x.qty;
        t += l;
        return `<div class="line"><span>${x.name} × ${x.qty}</span><b>${money(l)}</b></div>`;
      })
      .join("");
  let s = document.querySelector("#cart-subtotal");
  if (s) s.textContent = money(t);
  previewCart();
}
function checkout() {
  let box = document.querySelector("#checkout-lines");
  if (!box) return;
  let c = get(),
    a = Object.values(c),
    sub = 0;
  box.innerHTML =
    a
      .map((x) => {
        let l = x.price * x.qty;
        sub += l;
        return `<div class="line"><span>${x.name} × ${x.qty}</span><b>${money(l)}</b></div>`;
      })
      .join("") || "<p>Your cart is empty.</p>";
  document.querySelector("#checkout-subtotal").textContent = money(sub);
  let area = document.querySelector("#area"),
    fee = area ? +area.selectedOptions[0].dataset.fee : 0;
  document.querySelector("#delivery-fee").textContent = money(fee);
  document.querySelector("#checkout-total").textContent = money(sub + fee);
  let h = document.querySelector("#cart-json");
  if (h)
    h.value = JSON.stringify(Object.fromEntries(a.map((x) => [x.id, x.qty])));
}
document.addEventListener("DOMContentLoaded", () => {
  count();
  render();
  checkout();
  document
    .querySelector(".hamb")
    ?.addEventListener("click", () =>
      document.querySelector("nav").classList.toggle("open"),
    );
  document
    .querySelectorAll(".add")
    .forEach((b) => b.addEventListener("click", () => add(b)));
  document.querySelectorAll(".plus").forEach(b => b.addEventListener("click", () => updateDraft(b.dataset.id, 1)));
  document.querySelectorAll(".minus").forEach(b => b.addEventListener("click", () => updateDraft(b.dataset.id, -1)));
  document.querySelectorAll('input[name="payment_method"]').forEach(radio => radio.addEventListener('change', () => {
    const panel = document.getElementById('payment-details');
    const qr = document.getElementById('payment-qr');
    if (!panel || !qr) return;
    const method = document.querySelector('input[name="payment_method"]:checked')?.value;
    panel.hidden = method === 'Cash on Delivery';
    if (method !== 'Cash on Delivery') {
      const names = {eSewa:'eSewa', 'Bank Transfer':'Bank Transfer', Khalti:'Khalti'};
      qr.src = method === 'eSewa' ? qr.dataset.esewa : method === 'Bank Transfer' ? qr.dataset.bank : qr.dataset.khalti;
      qr.alt = method + ' payment QR code';
      document.getElementById('payment-details-title').textContent = names[method] + ' Payment';
    }
  }));
  document.querySelector("#area")?.addEventListener("change", checkout);
  document.querySelector("#checkout-form")?.addEventListener("submit", (e) => {
    if (!Object.keys(get()).length) {
      e.preventDefault();
      alert("Your cart is empty.");
    }
    checkout();
  });
});
