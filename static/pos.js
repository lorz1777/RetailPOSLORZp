(() => {
  "use strict";

  const root = document.getElementById("pos");
  const CSRF = root.dataset.csrf;
  const TAX = parseFloat(root.dataset.taxRate) || 0;
  const CUR = root.dataset.currency;

  const $ = (id) => document.getElementById(id);
  const search = $("search"), results = $("results");
  const cartTable = document.querySelector("table.cart"), cartBody = $("cart-body"), cartEmpty = $("cart-empty");
  const discountIn = $("discount"), methodSel = $("method"), tenderRow = $("tender-row"), tenderedIn = $("tendered");
  const payBtn = $("pay"), clearBtn = $("clear"), exactBtn = $("exact");
  const msg = $("pos-msg"), done = $("done");

  const cart = new Map(); // product id -> {id, name, sku, price (cents), stock, qty}
  let busy = false;

  // ---- helpers -----------------------------------------------------------
  const toCents = (s) => Math.round(parseFloat(s) * 100) || 0;
  const fmt = (c) =>
    CUR + (c / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function el(tag, props = {}, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") node.className = v;
      else node.setAttribute(k, v);
    }
    for (const kid of kids) node.append(kid);
    return node;
  }

  function showMsg(text) {
    msg.textContent = text;
    msg.hidden = false;
  }
  function clearMsg() {
    msg.hidden = true;
    msg.textContent = "";
  }

  // ---- product search ----------------------------------------------------
  let timer = null, seq = 0;

  async function loadProducts(q, autoAdd = false) {
    const mine = ++seq;
    try {
      const res = await fetch("/api/products/search?q=" + encodeURIComponent(q), {
        headers: { Accept: "application/json" },
      });
      if (res.status === 401) { window.location.href = "/login"; return; }
      const list = await res.json();
      if (mine !== seq) return; // a newer search replaced this one
      renderProducts(list);
      if (autoAdd && q) {
        const lq = q.toLowerCase();
        const exact = list.find((p) => (p.barcode || "").toLowerCase() === lq || p.sku.toLowerCase() === lq);
        const pick = exact || (list.length === 1 ? list[0] : null);
        if (pick) {
          addToCart(pick);
          search.value = "";
          loadProducts("");
        } else if (!list.length) {
          showMsg("No product found for “" + q + "”.");
        }
      }
    } catch (err) {
      showMsg("Could not load products. Check your connection.");
    }
  }

  function renderProducts(list) {
    results.replaceChildren();
    if (!list.length) {
      results.append(el("p", { class: "muted" }, "No matching products."));
      return;
    }
    for (const p of list) {
      const out = p.stock <= 0;
      const tile = el(
        "button",
        { type: "button", class: "tile" + (out ? " out" : "") },
        el("span", { class: "tile-name" }, p.name),
        el("span", { class: "tile-meta" }, p.sku),
        el("span", { class: "tile-price" }, fmt(toCents(p.price))),
        el("span", { class: "tile-stock" }, out ? "Out of stock" : p.stock + " in stock")
      );
      if (out) tile.disabled = true;
      else tile.addEventListener("click", () => addToCart(p));
      results.append(tile);
    }
  }

  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => loadProducts(search.value.trim()), 200);
  });
  search.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      clearTimeout(timer);
      loadProducts(search.value.trim(), true);
    }
  });

  // ---- cart --------------------------------------------------------------
  function addToCart(p) {
    const existing = cart.get(p.id);
    const qty = (existing ? existing.qty : 0) + 1;
    if (qty > p.stock) {
      showMsg("Only " + p.stock + " of " + p.name + " in stock.");
      return;
    }
    cart.set(p.id, { id: p.id, name: p.name, sku: p.sku, price: toCents(p.price), stock: p.stock, qty });
    done.hidden = true;
    clearMsg();
    redraw();
  }

  function setQty(id, qty) {
    const item = cart.get(id);
    if (!item) return;
    if (!Number.isFinite(qty) || qty < 1) qty = 1;
    if (qty > item.stock) {
      showMsg("Only " + item.stock + " of " + item.name + " in stock.");
      qty = item.stock;
    }
    item.qty = qty;
    redraw();
  }

  function totals() {
    let sub = 0;
    for (const i of cart.values()) sub += i.price * i.qty;
    let disc = Math.max(toCents(discountIn.value), 0);
    if (disc > sub) {
      disc = sub;
      discountIn.value = sub ? (sub / 100).toFixed(2) : "";
    }
    const taxable = sub - disc;
    const tax = Math.round(taxable * TAX);
    return { sub, disc, tax, total: taxable + tax };
  }

  function redraw() {
    cartBody.replaceChildren();
    for (const item of cart.values()) {
      const qtyInput = el("input", { type: "number", min: "1", max: String(item.stock), value: String(item.qty), "aria-label": "Quantity" });
      qtyInput.addEventListener("change", () => setQty(item.id, parseInt(qtyInput.value, 10)));
      const minus = el("button", { type: "button", class: "btn small", "aria-label": "Decrease" }, "−");
      const plus = el("button", { type: "button", class: "btn small", "aria-label": "Increase" }, "+");
      minus.addEventListener("click", () => {
        if (item.qty <= 1) { cart.delete(item.id); redraw(); } else setQty(item.id, item.qty - 1);
      });
      plus.addEventListener("click", () => setQty(item.id, item.qty + 1));
      const remove = el("button", { type: "button", class: "btn small link-danger", "aria-label": "Remove " + item.name }, "×");
      remove.addEventListener("click", () => { cart.delete(item.id); redraw(); });

      cartBody.append(
        el("tr", {},
          el("td", {}, el("div", { class: "strong" }, item.name), el("div", { class: "muted small-text" }, fmt(item.price) + " each")),
          el("td", { class: "qty" }, minus, qtyInput, plus),
          el("td", { class: "num strong" }, fmt(item.price * item.qty)),
          el("td", {}, remove))
      );
    }

    const has = cart.size > 0;
    cartTable.hidden = !has;
    cartEmpty.hidden = has;

    const t = totals();
    $("t-sub").textContent = fmt(t.sub);
    $("t-tax").textContent = fmt(t.tax);
    $("t-total").textContent = fmt(t.total);

    const cash = methodSel.value === "cash";
    tenderRow.hidden = !cash;
    const tendered = toCents(tenderedIn.value);
    $("t-change").textContent = fmt(Math.max(tendered - t.total, 0));

    payBtn.disabled = busy || !has || (cash && tendered < t.total);
    clearBtn.disabled = busy || !has;
  }

  discountIn.addEventListener("input", redraw);
  tenderedIn.addEventListener("input", redraw);
  methodSel.addEventListener("change", redraw);
  exactBtn.addEventListener("click", () => {
    tenderedIn.value = (totals().total / 100).toFixed(2);
    redraw();
  });
  clearBtn.addEventListener("click", () => {
    cart.clear();
    discountIn.value = "";
    tenderedIn.value = "";
    clearMsg();
    redraw();
    search.focus();
  });

  // ---- checkout ----------------------------------------------------------
  payBtn.addEventListener("click", async () => {
    if (busy || !cart.size) return;
    const t = totals();
    const cash = methodSel.value === "cash";
    busy = true;
    redraw();
    clearMsg();
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF },
        body: JSON.stringify({
          items: [...cart.values()].map((i) => ({ product_id: i.id, qty: i.qty })),
          discount: (t.disc / 100).toFixed(2),
          payment_method: methodSel.value,
          amount_paid: cash ? (toCents(tenderedIn.value) / 100).toFixed(2) : null,
        }),
      });
      if (res.status === 401) { window.location.href = "/login"; return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showMsg(data.error || "Checkout failed.");
        loadProducts(search.value.trim()); // refresh stock levels
        return;
      }
      $("done-title").textContent = "Sale " + data.receipt_no + " completed";
      $("done-detail").textContent =
        "Total " + fmt(toCents(data.total)) + (cash ? " · Change " + fmt(toCents(data.change)) : "");
      $("done-link").href = data.receipt_url;
      done.hidden = false;
      cart.clear();
      discountIn.value = "";
      tenderedIn.value = "";
      loadProducts("");
      search.value = "";
      search.focus();
    } catch (err) {
      showMsg("Network error. Check the Sales page before trying again so the sale is not entered twice.");
    } finally {
      busy = false;
      redraw();
    }
  });

  // ---- start -------------------------------------------------------------
  redraw();
  loadProducts("");
  search.focus();
})();
