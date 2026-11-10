/* ЕГМ — интерфейс. Без сборки и внешних библиотек. Маршрут в адресе после # */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const H = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const R = n => n == null || n === "" ? "" : Number(n).toLocaleString("ru-RU", {maximumFractionDigits: 2});
const RUB = n => n == null || n === "" ? "" : Number(n).toLocaleString("ru-RU", {maximumFractionDigits: 0}) + " ₽";
const D = d => d ? (d.length >= 10 ? `${d.slice(8, 10)}.${d.slice(5, 7)}.${d.slice(0, 4)}` : d) + (d.length > 11 ? " " + d.slice(11, 16) : "") : "";
const TODAY = () => new Date(Date.now() - new Date().getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
const addDays = (d, n) => { const x = new Date(d + "T12:00:00"); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); };
const M0 = () => TODAY().slice(0, 8) + "01";
let ME = null, META = null, MENU = [];

async function api(url, opt = {}) {
  const o = {method: opt.method || (opt.body ? "POST" : "GET"), headers: {}, credentials: "same-origin"};
  if (opt.body instanceof FormData) o.body = opt.body;
  else if (opt.body !== undefined) { o.body = JSON.stringify(opt.body); o.headers["Content-Type"] = "application/json"; }
  const r = await fetch(url, o);
  if (r.status === 401 && !url.includes("/login")) { ME = null; renderLogin(); throw new Error("Нужно войти"); }
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(data.error || data.detail || "Ошибка " + r.status);
  return data;
}
function toast(msg, err) {
  const t = document.createElement("div"); t.className = "toast" + (err ? " err" : ""); t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), err ? 6000 : 3000);
}
async function run(fn) { try { return await fn(); } catch (e) { toast(e.message, true); } }
const lbl = (en, v) => (META.enums[en] || []).find(x => x[0] === v)?.[1] ?? v ?? "";
const tag = (en, v) => v ? `<span class="tag ${H(v)}">${H(lbl(en, v))}</span>` : "";
const ENT = n => META.entities[n];

/* ---------- каркас ---------- */
const ICON = {owner: "◉", voice: "🎙", dashboard: "◧", dispatch: "▦", orders: "✎", trips: "⇄", waybills: "▤", documents: "▣", clients: "☺", sites: "⌂", leads: "☎",
  tasks: "✓", contracts: "§", client_prices: "₽", materials: "◆", zones: "◎", suppliers: "⛰", supplier_prices: "₽", warehouses: "▥",
  purchases: "⇣", stock_moves: "⇵", vehicles: "🚚", drivers: "👤", carriers: "⛟", fuel: "⛽", maintenance: "🔧", invoices: "₽",
  payments: "⇆", payroll: "₽", users: "⚙", reports: "▲", fleet: "!", stock: "▥", settings: "⚙", import: "⇪", audit: "≡", bank: "⇆"};
const MENU_GROUPS = [
  ["Работа", [["owner", "Панель руководителя"], ["dashboard", "Сводка"], ["voice", "Заявка голосом"], ["dispatch", "Диспетчерская"], ["orders"], ["trips"], ["waybills"], ["documents"]]],
  ["Продажи", [["leads"], ["clients"], ["sites"], ["contracts"], ["client_prices"], ["tasks"]]],
  ["Финансы", [["invoices"], ["payments"], ["bank", "Выписка банка"], ["payroll"], ["reports", "Отчёты"]]],
  ["Склад и закупки", [["stock", "Остатки"], ["purchases"], ["stock_moves"], ["suppliers"], ["supplier_prices"], ["warehouses"]]],
  ["Автопарк", [["vehicles"], ["drivers"], ["fleet", "Сроки документов"], ["fuel"], ["maintenance"], ["carriers"]]],
  ["Справочники", [["materials"], ["zones"]]],
  ["Настройки", [["settings", "Компания и боты"], ["users"], ["import", "Импорт из Excel"], ["audit", "Журнал действий"]]],
];
const PAGE_ROLES = {owner: ["director"], voice: ["director", "dispatcher", "manager"], dashboard: ["director", "dispatcher", "manager", "accountant", "mechanic"], dispatch: ["director", "dispatcher", "manager", "mechanic"],
  bank: ["director", "accountant"], reports: ["director", "accountant", "dispatcher", "manager"], stock: ["director", "accountant", "dispatcher"],
  fleet: ["director", "mechanic", "dispatcher"], settings: ["director"], import: ["director", "accountant", "manager", "dispatcher"], audit: ["director"]};
const allowed = k => ME.role === "admin" || (PAGE_ROLES[k] ? PAGE_ROLES[k].includes(ME.role) : MENU.includes(k));

function shell(title, html, actions = "") {
  const r = location.hash.slice(2).split("/")[0] || "dashboard";
  const nav = MENU_GROUPS.map(([g, items]) => {
    const its = items.filter(([k]) => allowed(k));
    if (!its.length) return "";
    return `<div class="grp">${g}</div>` + its.map(([k, t]) => `<a href="#/${k}" class="${r === k ? "on" : ""}"><span class="ic">${ICON[k] || "•"}</span>${H(t || ENT(k)?.title || k)}</a>`).join("");
  }).join("");
  const mnav = MENU_GROUPS.flatMap(([, it]) => it).filter(([k]) => allowed(k)).map(([k, t]) => `<a href="#/${k}" class="${r === k ? "on" : ""}">${H(t || ENT(k)?.title)}</a>`).join("");
  $("#root").innerHTML = `<div class="app"><nav class="side"><div class="brand"><img src="/web/logo.png" alt="ЕГМ"><small>Рабочая<br>система</small></div>${nav}
    <div class="me"><b>${H(ME.name)}</b><span>${H(lbl("role", ME.role))}</span><div class="mt"><a href="#" id="logout" style="padding:0;border:0;color:#ff8d87">Выйти</a></div></div></nav>
    <div class="main"><div class="mnav">${mnav}</div><div class="top"><h1>${H(title)}</h1><div class="sp"></div>${actions}<button class="bell" id="bell" title="Уведомления">🔔<i id="bellc" hidden></i></button></div>
    <div class="content" id="c">${html}</div></div></div>`;
  $("#logout").onclick = async e => { e.preventDefault(); await api("/api/logout", {body: {}}); location.hash = ""; location.reload(); };
  $("#bell").onclick = showNotifs;
  refreshBell();
  return $("#c");
}
async function refreshBell() {
  try { const n = await api("/api/notifications"); const b = $("#bellc"); if (b) { b.hidden = !n.unread; b.textContent = n.unread; } } catch (e) {}
}
async function showNotifs() {
  const n = await api("/api/notifications");
  modal("Уведомления", n.rows.length ? `<div class="tw"><table class="t">${n.rows.map(x => `<tr class="cl" data-l="${H(x.link)}"><td class="sm muted" style="width:120px">${D(x.ts)}</td><td>${x.read ? "" : "<b>●</b> "}${H(x.text)}</td></tr>`).join("")}</table></div>` : "<p class=muted>Пусто</p>", "sm");
  $$(".modal tr.cl").forEach(tr => tr.onclick = () => { if (tr.dataset.l) location.hash = tr.dataset.l; closeModal(); });
  await api("/api/notifications/read", {body: {}}); refreshBell();
}
function modal(title, html, size = "") {
  closeModal();
  const m = document.createElement("div"); m.className = "modal";
  m.innerHTML = `<div class="box ${size}"><div class="row" style="justify-content:space-between"><h2>${H(title)}</h2><button class="btn s" data-x>✕</button></div>${html}</div>`;
  m.onclick = e => { if (e.target === m || e.target.dataset.x !== undefined) closeModal(); };
  document.body.appendChild(m); return $(".box", m);
}
const closeModal = () => $$(".modal").forEach(m => m.remove());

/* ---------- вход ---------- */
function renderLogin() {
  $("#root").innerHTML = `<div class="login"><div class="l"><img src="/web/logo.png" alt="ЕГМ"><div><h2>Заявки, рейсы, документы<br>и деньги — в одном окне</h2>
    <p>Диспетчерская, водители в Telegram, транспортные накладные и путевые листы, счета и сверки, CRM и кабинет клиента.</p></div><p class="sm">ЕГМ · нерудные материалы и спецтехника</p></div>
    <div class="r"><form id="lf"><h1>Вход</h1><p class="muted">Логин и пароль выдаёт руководитель</p>
    <div class="form" style="grid-template-columns:1fr"><div><label>Логин</label><input class="i" name="login" autocomplete="username" required autofocus></div>
    <div><label>Пароль</label><input class="i" type="password" name="password" autocomplete="current-password" required></div>
    <button class="btn p big">Войти</button></div></form></div></div>`;
  $("#lf").onsubmit = e => { e.preventDefault(); run(async () => { await api("/api/login", {body: Object.fromEntries(new FormData(e.target))}); await boot(); }); };
}

/* ---------- поля и формы ---------- */
const REFCACHE = {};
async function refs(ent, force) {
  if (!REFCACHE[ent] || force) REFCACHE[ent] = await api("/api/refs/" + ent);
  return REFCACHE[ent];
}
function fieldInput(f, v, ro) {
  const t = f.type, n = f.name, dis = ro || f.opt.includes("ro") ? "disabled" : "";
  const cls = `i ${dis ? "ro" : ""}`;
  if (t.startsWith("enum:")) return `<select class="${cls}" name="${n}" ${dis}><option value=""></option>${META.enums[t.slice(5)].map(([k, l]) => `<option value="${k}" ${k === v ? "selected" : ""}>${H(l)}</option>`).join("")}</select>`;
  if (t.startsWith("ref:")) return `<select class="${cls}" name="${n}" data-ref="${t.slice(4)}" data-v="${v ?? ""}" ${dis}><option value="">${v ? "…" : ""}</option></select>`;
  if (t === "t") return `<textarea class="${cls}" name="${n}" ${dis}>${H(v)}</textarea>`;
  if (t === "b") return `<select class="${cls}" name="${n}" ${dis}><option value="0">нет</option><option value="1" ${v ? "selected" : ""}>да</option></select>`;
  const it = {d: "date", dt: "text", i: "number", n: "number", m: "number", pw: "password", ph: "tel"}[t] || "text";
  const step = t === "n" || t === "m" ? 'step="any"' : "";
  return `<input class="${cls}" type="${it}" ${step} name="${n}" value="${H(t === "pw" ? "" : v)}" ${dis} ${t === "pw" ? 'placeholder="оставьте пустым, чтобы не менять" autocomplete="new-password"' : ""}>`;
}
async function fillRefs(root) {
  for (const s of $$("select[data-ref]", root)) {
    const list = await refs(s.dataset.ref);
    const v = s.dataset.v;
    s.innerHTML = `<option value=""></option>` + list.map(r => `<option value="${r.id}" ${String(r.id) === v ? "selected" : ""}>${H(r.t)}</option>`).join("");
  }
}
function formHtml(ent, rec = {}, opts = {}) {
  const e = ENT(ent);
  return `<form class="form" data-ent="${ent}">` + e.fields.filter(f => !f.opt.includes("hide") && !(opts.skip || []).includes(f.name)).map(f =>
    `<div class="${f.type === "t" ? "w2" : ""}"><label class="${f.opt.includes("req") ? "req" : ""}">${H(f.label)}</label>${fieldInput(f, rec[f.name], opts.ro)}</div>`).join("") + `</form>`;
}
function formData(form) {
  const d = {};
  $$("[name]", form).forEach(el => { if (!el.disabled) d[el.name] = el.value; });
  return d;
}
async function openForm(ent, id, defaults = {}, after) {
  const e = ENT(ent);
  const rec = id ? await api(`/api/e/${ent}/${id}`) : {...defaults};
  const canW = ME.role === "admin" || e.roles_w.includes(ME.role);
  const box = modal((id ? "" : "Новая запись: ") + e.title + (id ? " — " + (rec[e.title_field] ?? "") : ""),
    formHtml(ent, rec, {ro: !canW}) + `<div class="row end mt">${id && canW ? `<button class="btn g" data-del>Удалить</button>` : ""}<div style="flex:1"></div>
    <button class="btn" data-x>Закрыть</button>${canW ? `<button class="btn p" data-save>Сохранить</button>` : ""}</div>` + (id ? historyHtml(rec) : ""));
  await fillRefs(box);
  if (ent === "orders") wireOrderForm(box);
  const save = $("[data-save]", box), del = $("[data-del]", box);
  if (save) save.onclick = () => run(async () => {
    const d = formData($("form", box));
    const r = id ? await api(`/api/e/${ent}/${id}`, {method: "PUT", body: d}) : await api(`/api/e/${ent}`, {body: d});
    Object.keys(REFCACHE).forEach(k => k === ent && delete REFCACHE[k]);
    closeModal(); toast("Сохранено"); after ? after(r.id || id) : route();
  });
  if (del) del.onclick = () => run(async () => {
    if (!confirm("Удалить запись? Действие попадёт в журнал.")) return;
    await api(`/api/e/${ent}/${id}`, {method: "DELETE"}); closeModal(); toast("Удалено"); route();
  });
}
function historyHtml(rec) {
  if (!rec._audit?.length) return "";
  return `<details class="mt"><summary class="muted sm">История изменений (${rec._audit.length})</summary><div class="sm mt">` +
    rec._audit.map(a => `<div><span class="muted">${D(a.ts)} ${H(a.uname || "система")}:</span> ${H(a.action)} ${H((a.data || "").slice(0, 300))}</div>`).join("") + "</div></details>";
}

/* ---------- универсальный список ---------- */
const LIST_COLS = {
  orders: ["number", "date", "client_id", "site_id", "material_id", "qty", "unit", "total", "status", "credit_flag"],
  trips: ["number", "date", "order_id", "vehicle_id", "driver_id", "plan_qty", "unload_qty", "status", "revenue", "margin"],
  waybills: ["number", "date", "vehicle_id", "driver_id", "odo_start", "odo_end", "status", "edo_status"],
  documents: ["kind", "number", "date", "client_id", "trip_id", "invoice_id", "total", "status"],
  clients: ["name", "inn", "contact", "phone", "pay_terms", "delay_days", "credit_limit", "manager_id"],
  invoices: ["number", "date", "client_id", "total", "paid", "due_date", "status"],
  payments: ["date", "direction", "amount", "client_id", "supplier_id", "invoice_id", "doc_no", "purpose"],
  leads: ["name", "phone", "source", "stage", "material", "qty", "manager_id", "next_date"],
  vehicles: ["plate", "model", "vtype", "capacity_t", "owner", "status", "odometer", "osago_to", "insp_to", "pass_to"],
  drivers: ["name", "phone", "vehicle_id", "pay_type", "pay_rate", "license_to", "med_to", "status"],
  payroll: ["driver_id", "period_from", "period_to", "trips", "tons", "accrued", "bonus", "deduction", "advance", "total", "status"],
  users: ["login", "name", "role", "phone", "client_id", "driver_id", "active"],
};
function cell(f, r) {
  const v = r[f.name];
  if (f.type.startsWith("ref:")) return H(r[f.name + "__t"]);
  if (f.type.startsWith("enum:")) return tag(f.type.slice(5), v);
  if (f.type === "m") return RUB(v);
  if (f.type === "n" || f.type === "i") return R(v);
  if (f.type === "d" || f.type === "dt") return D(v);
  if (f.type === "b") return v ? "✓" : "";
  if (f.name === "credit_flag") return v && v !== "ок" ? `<span class="tag canceled" title="${H(v)}">⚠ проверить</span>` : "";
  return H(String(v ?? "").slice(0, 80));
}
async function pageList(ent, params = {}) {
  const e = ENT(ent);
  if (!e) return pageNotFound();
  const canW = ME.role === "admin" || e.roles_w.includes(ME.role);
  const cols = (LIST_COLS[ent] || e.fields.filter(f => !["t", "pw"].includes(f.type) && !f.opt.includes("hide")).slice(0, 8).map(f => f.name))
    .map(n => e.fields.find(f => f.name === n)).filter(Boolean);
  const statusF = e.fields.find(f => ["status", "stage"].includes(f.name) && f.type.startsWith("enum:"));
  const dateF = e.fields.find(f => f.name === "date");
  const extra = {orders: `<button class="btn p" id="new">+ Заявка</button>`, invoices: `<button class="btn p" id="build">Сформировать счета за период</button>`,
    payroll: `<button class="btn p" id="build">Рассчитать за период</button>`}[ent] || (canW ? `<button class="btn p" id="new">+ Добавить</button>` : "");
  const c = shell(e.title, `<div class="row mb"><input class="i" id="q" placeholder="Поиск" style="max-width:280px" value="${H(params.q || "")}">
    ${statusF ? `<select class="i" id="st" style="max-width:200px"><option value="">Все: ${H(statusF.label.toLowerCase())}</option>${META.enums[statusF.type.slice(5)].map(([k, l]) => `<option value="${k}" ${params[statusF.name] === k ? "selected" : ""}>${H(l)}</option>`).join("")}</select>` : ""}
    ${dateF ? `<input class="i" type="date" id="df" style="max-width:160px" value="${params.df || ""}"><input class="i" type="date" id="dt" style="max-width:160px" value="${params.dt || ""}">` : ""}
    <div style="flex:1"></div><a class="btn" href="/api/export/${ent}.xlsx">⇩ Excel</a>${extra}</div><div class="tw" id="tw"><p class="muted" style="padding:14px">Загрузка…</p></div><div class="pager" id="pg"></div>`);
  let offset = 0;
  const load = async () => {
    const p = new URLSearchParams({q: $("#q").value, limit: 200, offset});
    if (statusF && $("#st").value) p.set(statusF.name, $("#st").value);
    if (dateF && $("#df").value) p.set("date__from", $("#df").value);
    if (dateF && $("#dt").value) p.set("date__to", $("#dt").value);
    Object.entries(params).forEach(([k, v]) => !["q", "df", "dt", "status", "stage"].includes(k) && p.set(k, v));
    const d = await api(`/api/e/${ent}?` + p);
    const sumF = cols.filter(f => f.type === "m");
    $("#tw").innerHTML = d.rows.length ? `<table class="t"><thead><tr>${cols.map(f => `<th class="${["m", "n", "i"].includes(f.type) ? "n" : ""}">${H(f.label)}</th>`).join("")}</tr></thead><tbody>` +
      d.rows.map(r => `<tr class="cl" data-id="${r.id}">${cols.map(f => `<td class="${["m", "n", "i"].includes(f.type) ? "n" : ""}">${cell(f, r)}</td>`).join("")}</tr>`).join("") +
      `</tbody>${sumF.length ? `<tfoot><tr>${cols.map(f => `<td class="n b">${sumF.includes(f) ? RUB(d.rows.reduce((s, r) => s + (r[f.name] || 0), 0)) : ""}</td>`).join("")}</tr></tfoot>` : ""}</table>`
      : `<p class="muted" style="padding:14px">Записей нет${canW ? ". Нажмите «Добавить» или загрузите из Excel (Настройки → Импорт)." : ""}</p>`;
    $("#pg").innerHTML = d.total > 200 ? `<span class="muted">${offset + 1}–${Math.min(offset + 200, d.total)} из ${d.total}</span><button class="btn s" id="pp" ${offset ? "" : "disabled"}>‹</button><button class="btn s" id="pn" ${offset + 200 < d.total ? "" : "disabled"}>›</button>` : `<span class="muted sm">Всего: ${d.total}</span>`;
    $("#pp") && ($("#pp").onclick = () => { offset -= 200; load(); });
    $("#pn") && ($("#pn").onclick = () => { offset += 200; load(); });
    $$("#tw tr.cl").forEach(tr => tr.onclick = () => openRecord(ent, +tr.dataset.id));
  };
  let tm; $("#q").oninput = () => { clearTimeout(tm); tm = setTimeout(() => { offset = 0; load(); }, 300); };
  ["#st", "#df", "#dt"].forEach(s => $(s) && ($(s).onchange = () => { offset = 0; load(); }));
  if ($("#new")) $("#new").onclick = () => ent === "orders" ? openForm("orders", null, {date: addDays(TODAY(), 1), unit: "t", status: "new", source: "phone"}) : openForm(ent, null, ent === "leads" ? {stage: "new", next_date: TODAY()} : {});
  if ($("#build")) $("#build").onclick = ent === "invoices" ? buildInvoices : buildPayroll;
  run(load);
}
function openRecord(ent, id) {
  if (ent === "orders") return location.hash = "#/orders/" + id;
  if (ent === "trips") return location.hash = "#/trips/" + id;
  if (ent === "clients") return location.hash = "#/clients/" + id;
  if (ent === "invoices") return location.hash = "#/invoices/" + id;
  if (ent === "waybills") return location.hash = "#/waybills/" + id;
  if (ent === "documents") return window.open("/doc/document/" + id);
  if (ent === "leads") return location.hash = "#/leads/" + id;
  openForm(ent, id);
}
function pageNotFound() { shell("Нет доступа", `<p class="muted">Раздел недоступен для вашей роли.</p>`); }

/* ---------- заявка ---------- */
function wireOrderForm(box) {
  const f = $("form", box), g = n => $(`[name=${n}]`, f);
  const info = document.createElement("div"); info.className = "note w2"; info.style.display = "none"; f.appendChild(info);
  const filterSites = async () => {
    const all = await refs("sites"), cid = g("client_id").value, cur = g("site_id").value;
    g("site_id").innerHTML = `<option value=""></option>` + all.filter(s => !cid || String(s.client_id) === cid).map(s => `<option value="${s.id}" ${String(s.id) === cur ? "selected" : ""}>${H(s.t)}</option>`).join("");
  };
  const calc = () => run(async () => {
    if (!g("material_id").value || !g("qty").value) return;
    const q = await api("/api/quote", {body: {client_id: g("client_id").value, site_id: g("site_id").value, material_id: g("material_id").value, qty: g("qty").value, unit: g("unit").value}});
    info.style.display = "";
    info.innerHTML = `Расчёт: цена ${RUB(q.price)} (${H(q.price_how)}) × ${R(g("qty").value)} = ${RUB(q.goods)}; доставка ${RUB(q.delivery)} (зона «${H(q.zone)}», рейсов ≈ ${q.trips}, ${R(q.tons)} т). <b>Итого ${RUB(q.total)}</b>
      <button type="button" class="btn s" id="applyq" style="margin-left:8px">Подставить цену и доставку</button>`;
    $("#applyq").onclick = () => { g("price").value = q.price; g("delivery").value = q.delivery; };
    if (g("client_id").value) {
      const b = await api("/api/balance/" + g("client_id").value).catch(() => null);
      if (b && (b.debt > 0 || b.overdue.length)) info.innerHTML += `<div class="mt">Долг клиента: <b>${RUB(b.debt)}</b>, не выставлено: ${RUB(b.uninvoiced)}${b.overdue.length ? `, <b style="color:var(--red2)">просрочено счетов: ${b.overdue.length}</b>` : ""}</div>`;
    }
  });
  g("client_id").addEventListener("change", () => { filterSites(); calc(); });
  ["site_id", "material_id", "qty", "unit"].forEach(n => g(n).addEventListener("change", calc));
  filterSites();
  const add = document.createElement("div"); add.className = "w2";
  add.innerHTML = `<button type="button" class="btn s" id="addsite">+ новый объект клиента</button> <button type="button" class="btn s" id="addcl">+ новый клиент</button>`;
  f.appendChild(add);
  $("#addcl", f).onclick = () => quickAdd("clients", {pay_terms: "prepay"}, async id => { await refs("clients", true); await fillRefs(f); g("client_id").value = id; filterSites(); });
  $("#addsite", f).onclick = () => quickAdd("sites", {client_id: g("client_id").value}, async id => { await refs("sites", true); await filterSites(); g("site_id").value = id; calc(); });
  if (g("material_id").value) calc();
}
function quickAdd(ent, defaults, cb) {
  const m = document.createElement("div"); m.className = "modal"; m.style.zIndex = 60;
  m.innerHTML = `<div class="box sm"><h2>Новая запись: ${H(ENT(ent).title)}</h2>${formHtml(ent, defaults)}<div class="row end mt"><button class="btn" data-c>Отмена</button><button class="btn p" data-s>Сохранить</button></div></div>`;
  document.body.appendChild(m); fillRefs(m);
  $("[data-c]", m).onclick = () => m.remove();
  $("[data-s]", m).onclick = () => run(async () => { const r = await api(`/api/e/${ent}`, {body: formData($("form", m))}); m.remove(); toast("Добавлено"); cb(r.id); });
}
async function pageOrder(id) {
  const o = await api("/api/e/orders/" + id);
  const trips = (await api(`/api/e/trips?order_id=${id}&limit=500`)).rows;
  const done = trips.filter(t => t.status === "closed").reduce((s, t) => s + (t.unload_qty || 0), 0);
  const planned = trips.filter(t => t.status !== "canceled").reduce((s, t) => s + (t.plan_qty || 0), 0);
  const canW = ["admin", "director", "dispatcher", "manager"].includes(ME.role);
  const c = shell(`Заявка ${o.number}`, `<div class="grid g2"><div class="card"><div class="row mb" style="justify-content:space-between"><h3>${H(o.client_id__t)}</h3>${tag("order_status", o.status)}</div>
    <div class="kv"><span>Дата</span><b>${D(o.date)} ${H(o.time_from || "")}${o.time_to ? "–" + H(o.time_to) : ""}</b><span>Объект</span><div>${H(o.site_id__t)}</div>
    <span>Материал</span><div>${H(o.material_id__t)}, <b>${R(o.qty)} ${H(lbl("unit", o.unit))}</b></div><span>Цена</span><div>${RUB(o.price)} за ед. + доставка ${RUB(o.delivery)}</div>
    <span>Сумма</span><b>${RUB(o.total)}</b><span>Источник</span><div>${H(lbl("order_source", o.source))}, менеджер: ${H(o.manager_id__t || "—")}</div>
    <span>Контакт</span><div>${H(o.contact || "")}</div><span>Комментарий</span><div>${H(o.comment || "")}</div></div>
    ${o.credit_flag && o.credit_flag !== "ок" ? `<div class="note r mt">⚠ ${H(o.credit_flag)}</div>` : ""}
    <div class="row mt">${canW ? `<button class="btn" id="edit">Изменить</button>` : ""}${canW && o.status === "new" ? `<button class="btn" id="conf">Подтвердить</button>` : ""}
    ${canW && !["done", "canceled"].includes(o.status) ? `<button class="btn p" id="plan">Разбить на рейсы</button><button class="btn g" id="cancel">Отменить</button>` : ""}</div></div>
    <div class="card"><h3>Исполнение</h3><div class="grid g4" style="grid-template-columns:repeat(3,1fr)"><div class="kpi"><span>Рейсов</span><b>${trips.filter(t => t.status !== "canceled").length}</b></div>
    <div class="kpi"><span>Запланировано, т</span><b>${R(planned)}</b></div><div class="kpi"><span>Доставлено, т</span><b>${R(done)}</b></div></div>
    <div class="mt">${activityBox("orders", id, o._activity)}</div></div></div>
    <h3 class="mt">Рейсы</h3><div class="tw">${tripsTable(trips)}</div>`);
  if ($("#edit")) $("#edit").onclick = () => openForm("orders", id);
  if ($("#conf")) $("#conf").onclick = () => run(async () => { await api(`/api/orders/${id}/status`, {body: {status: "confirmed"}}); route(); });
  if ($("#cancel")) $("#cancel").onclick = () => run(async () => { if (confirm("Отменить заявку и незапущенные рейсы?")) { await api(`/api/orders/${id}/status`, {body: {status: "canceled"}}); route(); } });
  if ($("#plan")) $("#plan").onclick = () => run(async () => {
    const cap = prompt("Сколько тонн в одну машину?", "25"); if (!cap) return;
    const r = await api(`/api/orders/${id}/plan`, {body: {capacity: cap}}); toast(`Создано рейсов: ${r.trips.length}. Назначьте машины в Диспетчерской.`); route();
  });
  wireActivity("orders", id);
  $$("tr.cl", c).forEach(tr => tr.onclick = () => location.hash = "#/trips/" + tr.dataset.id);
}
function tripsTable(trips) {
  if (!trips.length) return `<p class="muted" style="padding:14px">Рейсов пока нет</p>`;
  return `<table class="t"><thead><tr><th>№</th><th>Дата</th><th>Машина</th><th>Водитель</th><th class=n>План, т</th><th class=n>Принято, т</th><th>Статус</th><th>ТН</th><th class=n>Маржа</th></tr></thead><tbody>` +
    trips.map(t => `<tr class="cl" data-id="${t.id}"><td>${H(t.number)}</td><td>${D(t.date)}</td><td>${H(t.vehicle_id__t || "—")}</td><td>${H(t.driver_id__t || "—")}</td>
    <td class=n>${R(t.plan_qty)}</td><td class=n>${R(t.unload_qty)}</td><td>${tag("trip_status", t.status)}</td><td>${H(t.tn_number || "")}</td><td class=n>${RUB(t.margin)}</td></tr>`).join("") + `</tbody></table>`;
}
function activityBox(ent, id, list = []) {
  return `<h3>Комментарии и звонки</h3><div class="row"><input class="i" id="actx" placeholder="Что обсудили, договорённости…" style="flex:1"><button class="btn s" id="acts">Добавить</button></div>
    <div class="sm mt">${list.map(a => `<div style="margin-bottom:6px"><span class="muted">${D(a.ts)} ${H(a.uname || "")}:</span> ${H(a.text)}</div>`).join("") || `<span class="muted">Пока пусто</span>`}</div>`;
}
function wireActivity(ent, id) {
  const b = $("#acts"); if (!b) return;
  b.onclick = () => run(async () => { const t = $("#actx").value.trim(); if (!t) return; await api(`/api/activity/${ent}/${id}`, {body: {text: t}}); route(); });
}

/* ---------- рейс ---------- */
const FLOW = ["plan", "assigned", "accepted", "loading", "loaded", "on_way", "delivered", "closed"];
async function pageTrip(id) {
  const t = await api("/api/e/trips/" + id);
  const canW = ["admin", "director", "dispatcher"].includes(ME.role);
  const i = FLOW.indexOf(t.status);
  const nxt = {assigned: "accepted", accepted: "loading", loading: "loaded", loaded: "on_way", on_way: "delivered", delivered: "closed"}[t.status];
  const c = shell(`Рейс ${t.number}`, `<div class="steps">${FLOW.map((s, k) => `<i class="${k <= i ? "on" : ""}" title="${H(lbl("trip_status", s))}"></i>`).join("")}</div>
    <div class="grid g2"><div class="card"><div class="row mb" style="justify-content:space-between"><h3>${H(t.order_id__t)} · ${D(t.date)}</h3>${tag("trip_status", t.status)}</div>
    <div class="kv"><span>Машина</span><b>${H(t.vehicle_id__t || "не назначена")}</b><span>Водитель</span><div>${H(t.driver_id__t || "—")}</div>
    <span>Откуда</span><div>${H(lbl("source_kind", t.source_kind))}: ${H(t.supplier_id__t || t.warehouse_id__t || "—")}</div><span>Расстояние</span><div>${R(t.distance_km)} км</div>
    <span>План / погружено / принято</span><b>${R(t.plan_qty)} / ${R(t.load_qty) || "—"} / ${R(t.unload_qty) || "—"} т</b>
    <span>ТН</span><div>${t.tn_number ? `<a href="/doc/tn/${id}" target="_blank">${H(t.tn_number)}</a>` : "появится после выгрузки"}</div>
    <span>Путевой лист</span><div>${t.waybill_id ? `<a href="#/waybills/${t.waybill_id}">${H(t.waybill_id__t)}</a>` : "—"}</div>
    <span>Фото накладной</span><div>${t.photo ? `<a href="/files/${H(t.photo)}" target="_blank">открыть</a>` : "—"}</div>
    <span>Счёт</span><div>${t.invoice_id ? `<a href="#/invoices/${t.invoice_id}">${H(t.invoice_id__t)}</a>` : "не выставлен"}</div></div>
    ${canW ? `<div class="row mt">${nxt ? `<button class="btn p" id="next">→ ${H(lbl("trip_status", nxt))}</button>` : ""}<button class="btn" id="edit">Изменить</button>
    ${["plan", "assigned", "accepted"].includes(t.status) ? `<button class="btn" id="asg">Назначить машину</button>` : ""}
    ${t.status !== "closed" && t.status !== "canceled" ? `<button class="btn g" id="cnl">Отменить рейс</button>` : ""}
    ${t.status === "closed" ? `<button class="btn" id="recalc">Пересчитать экономику</button>` : ""}</div>` : ""}</div>
    <div class="card"><h3>Экономика рейса</h3><table class="t"><tr><td>Выручка</td><td class=n><b>${RUB(t.revenue)}</b></td></tr><tr><td>Материал (закупка/себестоимость)</td><td class=n>−${RUB(t.cost_material)}</td></tr>
    <tr><td>Водитель</td><td class=n>−${RUB(t.cost_driver)}</td></tr><tr><td>Топливо (по норме)</td><td class=n>−${RUB(t.cost_fuel)}</td></tr><tr><td>Наёмный перевозчик</td><td class=n>−${RUB(t.cost_carrier)}</td></tr>
    <tr><td><b>Маржа</b></td><td class=n><b style="color:${(t.margin || 0) < 0 ? "var(--red2)" : "var(--ok)"}">${RUB(t.margin)}</b></td></tr></table>
    <p class="sm muted">Считается автоматически при закрытии рейса. Ставки — в карточках водителя, машины, карьера и в настройках (цена топлива).</p>
    <div class="sm mt"><b>Хронология:</b> назначен ${D(t.ts_assigned) || "—"} · загружен ${D(t.ts_loaded) || "—"} · выгружен ${D(t.ts_delivered) || "—"}</div></div></div>`);
  if ($("#edit")) $("#edit").onclick = () => openForm("trips", id);
  if ($("#asg")) $("#asg").onclick = () => assignDialog(t);
  if ($("#recalc")) $("#recalc").onclick = () => run(async () => { await api(`/api/trips/${id}/status`, {body: {status: "closed"}}); route(); });
  if ($("#cnl")) $("#cnl").onclick = () => run(async () => { if (confirm("Отменить рейс?")) { await api(`/api/e/trips/${id}`, {method: "PUT", body: {status: "canceled"}}); route(); } });
  if ($("#next")) $("#next").onclick = () => run(async () => {
    let qty = null;
    if (nxt === "loaded" || nxt === "delivered") { qty = prompt(nxt === "loaded" ? "Погружено, тонн:" : "Принято на объекте, тонн:", t.load_qty || t.plan_qty); if (qty === null) return; }
    await api(`/api/trips/${id}/status`, {body: {status: nxt, qty}}); route();
  });
}
async function assignDialog(t, vehicleId) {
  const vs = await refs("vehicles", true), ds = await refs("drivers", true);
  const box = modal(`Назначить рейс ${t.number}`, `<div class="form"><div><label>Машина</label><select class="i" id="av"><option value=""></option>${vs.map(v => `<option value="${v.id}" ${v.id === (vehicleId || t.vehicle_id) ? "selected" : ""}>${H(v.t)} · ${R(v.capacity_t)} т${v.owner === "hired" ? " · наёмная" : ""}</option>`).join("")}</select></div>
    <div><label>Водитель (пусто — закреплённый за машиной)</label><select class="i" id="ad"><option value=""></option>${ds.map(d => `<option value="${d.id}" ${d.id === t.driver_id ? "selected" : ""}>${H(d.t)}</option>`).join("")}</select></div></div>
    <div id="aw"></div><div class="row end mt"><button class="btn" data-x>Отмена</button><button class="btn p" id="ago">Назначить и отправить водителю</button></div>`, "sm");
  $("#av").onchange = () => { const d = ds.find(x => String(x.vehicle_id) === $("#av").value); if (d) $("#ad").value = d.id; };
  if (vehicleId) $("#av").onchange();
  const go = force => run(async () => {
    const r = await api(`/api/trips/${t.id}/assign`, {body: {vehicle_id: $("#av").value, driver_id: $("#ad").value, force}});
    if (!r.ok) {
      $("#aw").innerHTML = `<div class="note r mt"><b>Проверьте:</b><br>${r.warnings.map(H).join("<br>")}<div class="mt"><button class="btn s p" id="aforce">Всё равно назначить</button></div></div>`;
      $("#aforce").onclick = () => go(true); return;
    }
    closeModal(); toast(r.warnings.length ? "Назначено с предупреждениями" : "Назначено, водителю ушло сообщение"); route();
  });
  $("#ago").onclick = () => go(false);
}

/* ---------- диспетчерская ---------- */
async function pageDispatch(date) {
  date = date || sessionStorage.dispDate || TODAY(); sessionStorage.dispDate = date;
  const d = await api("/api/dispatch?date=" + date);
  const free = d.trips.filter(t => t.status === "plan");
  const byV = {}; d.trips.filter(t => t.vehicle_id).forEach(t => (byV[t.vehicle_id] ||= []).push(t));
  const card = t => `<div class="tc ${t.status}" draggable="${["plan", "assigned", "accepted"].includes(t.status)}" data-t="${t.id}"><b>${H(t.number)}</b> ${tag("trip_status", t.status)}<br>
    ${H(t.client)} · ${H(t.material)} <b>${R(t.unload_qty || t.plan_qty)} т</b><div class="muted">${H(t.addr || t.site || "")}${t.time_from ? " · " + H(t.time_from) + "–" + H(t.time_to || "") : ""}${t.date < date ? ` · <b style="color:var(--red2)">с ${D(t.date)}</b>` : ""}</div></div>`;
  const vrows = d.vehicles.map(v => {
    const ts = byV[v.id] || [];
    const tons = ts.reduce((s, t) => s + (t.plan_qty || 0), 0);
    return `<div class="vrow ${v.status === "repair" ? "over" : ""}" data-v="${v.id}"><div class="vh"><b>${H(v.plate)}</b> ${v.owner === "hired" ? '<span class="tag">наёмн.</span>' : ""} ${v.status !== "work" ? tag("veh_status", v.status) : ""}<br>
      <span class="muted">${H(v.driver || "нет водителя")}${v.driver_phone ? " · " + H(v.driver_phone) : ""}</span><br><span class="sm">${ts.length} рейс. · ${R(tons)} т · ${R(v.capacity_t)} т/рейс</span>
      ${v.gps ? `<br><a class="sm" target="_blank" href="https://yandex.ru/maps/?pt=${v.gps.lon},${v.gps.lat}&z=14&l=map">📍 ${D(v.gps.ts).slice(11)}</a>` : ""}${v.tg_chat ? "" : `<br><span class="sm" style="color:var(--warn)">бот не подключён</span>`}</div>
      <div class="vt">${ts.map(card).join("")}</div></div>`;
  }).join("");
  const c = shell("Диспетчерская", `<div class="row mb"><button class="btn" id="dprev">‹</button><input class="i" type="date" id="dd" value="${date}" style="max-width:170px"><button class="btn" id="dnext">›</button>
    <button class="btn" id="dtoday">Сегодня</button><span class="muted">Перетащите рейс на строку машины — система проверит документы и отправит задание водителю в Telegram.</span><div style="flex:1"></div>
    <button class="btn p" id="dneworder">+ Заявка</button></div>
    <div class="disp"><div><div class="lane"><h3>Заявки без рейсов <span class="tag">${d.orders.length}</span></h3>${d.orders.map(o => `<div class="tc" data-o="${o.id}" style="cursor:pointer;border-left-color:#999"><b>${H(o.number)}</b> ${tag("order_status", o.status)} <span class="muted">${D(o.date)}</span><br>${H(o.client)} · ${H(o.material)} <b>${R(o.qty)} ${H(lbl("unit", o.unit))}</b><div class="muted">${H(o.addr || "")}</div>
    <button class="btn s p mt" data-plan="${o.id}">Разбить на рейсы</button></div>`).join("") || `<p class="muted sm">Все заявки распределены</p>`}</div>
    <div class="lane mt" id="freelane"><h3>Рейсы без машины <span class="tag">${free.length}</span></h3>${free.map(card).join("") || `<p class="muted sm">Нет</p>`}</div></div>
    <div class="lane" style="padding:0;overflow:hidden"><div style="padding:12px 12px 8px"><h3>Машины на ${D(date)}</h3></div>${vrows || `<p class="muted" style="padding:12px">Добавьте технику в Автопарк → Техника</p>`}</div></div>`);
  const go = x => pageDispatch(x);
  $("#dd").onchange = e => go(e.target.value); $("#dprev").onclick = () => go(addDays(date, -1)); $("#dnext").onclick = () => go(addDays(date, 1)); $("#dtoday").onclick = () => go(TODAY());
  $("#dneworder").onclick = () => openForm("orders", null, {date, unit: "t", status: "confirmed", source: "phone"}, () => pageDispatch(date));
  $$("[data-plan]", c).forEach(b => b.onclick = e => { e.stopPropagation(); run(async () => { const cap = prompt("Тонн в одну машину?", "25"); if (!cap) return; await api(`/api/orders/${b.dataset.plan}/plan`, {body: {capacity: cap}}); go(date); }); });
  $$("[data-o]", c).forEach(el => el.onclick = () => location.hash = "#/orders/" + el.dataset.o);
  const tripById = id => d.trips.find(t => t.id === +id);
  $$(".tc[data-t]", c).forEach(el => {
    el.ondragstart = e => e.dataTransfer.setData("text", el.dataset.t);
    el.ondblclick = () => location.hash = "#/trips/" + el.dataset.t;
    el.onclick = () => { const t = tripById(el.dataset.t); ["plan", "assigned", "accepted"].includes(t.status) ? assignDialog({...t, number: t.number}) : (location.hash = "#/trips/" + t.id); };
  });
  $$(".vrow", c).forEach(row => {
    row.ondragover = e => { e.preventDefault(); row.classList.add("drop"); };
    row.ondragleave = () => row.classList.remove("drop");
    row.ondrop = e => { e.preventDefault(); row.classList.remove("drop"); const t = tripById(e.dataTransfer.getData("text")); if (!t) return;
      run(async () => {
        const r = await api(`/api/trips/${t.id}/assign`, {body: {vehicle_id: row.dataset.v}});
        if (!r.ok) { if (confirm("Внимание:\n• " + r.warnings.join("\n• ") + "\n\nВсё равно назначить?")) await api(`/api/trips/${t.id}/assign`, {body: {vehicle_id: row.dataset.v, force: true}}); else return; }
        toast("Назначено"); go(date);
      });
    };
  });
  clearTimeout(window._dispT); window._dispT = setTimeout(() => location.hash.startsWith("#/dispatch") && !$(".modal") && go(date), 30000);
}

/* ---------- сводка ---------- */
async function pageDashboard() {
  const d = await api("/api/dashboard");
  const days = await api(`/api/report/days?date_from=${addDays(TODAY(), -13)}&date_to=${TODAY()}`);
  const mx = Math.max(1, ...days.map(x => x.revenue || 0));
  const alerts = ["director", "mechanic", "dispatcher", "admin"].includes(ME.role) ? await api(`/api/report/fleet?date_from=&date_to=`).catch(() => []) : [];
  const k = (t, v, href, red, sub = "") => `<a class="kpi ${red ? "r" : ""}" href="${href}"><span>${t}</span><b>${v}</b><small>${sub}</small></a>`;
  shell("Сводка на " + D(d.date), `<div class="grid g4">
    ${k("Новые заявки", d.orders_new, "#/orders?status=new", d.orders_new > 0, "ждут подтверждения")}
    ${k("Рейсов сегодня", d.trips_today, "#/dispatch", false, `выполнено ${d.trips_done_today}, в пути ${d.trips_active}`)}
    ${k("Рейсы без машины", d.trips_unassigned, "#/dispatch", d.trips_unassigned > 0, "на сегодня и раньше")}
    ${k("Отгружено сегодня", R(d.tons_today) + " т", "#/trips", false)}
    ${k("Выручка за месяц", RUB(d.revenue_month), "#/reports", false, `${R(d.tons_month)} т`)}
    ${k("Маржа за месяц", RUB(d.margin_month), "#/reports", d.margin_month < 0, d.revenue_month ? Math.round(d.margin_month / d.revenue_month * 100) + "% от выручки" : "")}
    ${k("Дебиторка", RUB(d.debt), "#/reports/aging", false, "выставлено и не оплачено")}
    ${k("Просрочено", RUB(d.overdue), "#/reports/aging", d.overdue > 0)}
    ${k("Не выставлено счетов", RUB(d.uninvoiced), "#/invoices", d.uninvoiced > 0, "закрытые рейсы без счёта")}
    ${k("Техника", `${d.vehicles_work} в работе`, "#/vehicles", d.vehicles_repair > 0, `${d.vehicles_repair} в ремонте`)}
    ${k("Сроки документов", d.alerts, "#/fleet", d.alerts > 0, "ОСАГО, ТО, ВУ, медсправки, пропуска")}
    ${k("Открытые лиды", d.leads_open, "#/leads", false)}</div>
    <div class="grid g2 mt"><div class="card"><h3>Выручка по дням, 14 дней</h3><div class="bar-chart">${days.slice().reverse().sort((a, b) => a.name < b.name ? -1 : 1).map(x => `<div style="height:${Math.round((x.revenue || 0) / mx * 100)}%" title="${D(x.name)}: ${RUB(x.revenue)}"><span>${x.name.slice(8)}</span></div>`).join("") || `<p class="muted">Пока нет закрытых рейсов</p>`}</div></div>
    <div class="card"><h3>Требует внимания</h3>${alerts.slice(0, 8).map(a => `<div class="sm" style="margin-bottom:5px">${a.overdue ? "🔴" : "🟡"} <b>${H(a.who)}</b> — ${H(a.what)} ${D(a.date)}</div>`).join("") || `<p class="muted sm">Сроки документов в порядке</p>`}</div></div>`);
}


/* ---------- панель руководителя: один экран, светофор ---------- */
async function pageOwner() {
  const x = await api("/api/owner");
  const s = x.sales, m = x.money, t = x.today;
  const L = {r: "🔴", y: "🟡", g: "🟢"};
  const big = (title, v, sub, href, cls = "") => `<a class="kpi ow ${cls}" href="${href}"><span>${title}</span><b>${v}</b><small>${sub || ""}</small></a>`;
  const bar = pct => pct == null ? "" : `<div class="obar"><i style="width:${Math.min(100, pct)}%" class="${pct >= 100 ? "g" : pct >= 80 ? "y" : "r"}"></i></div>`;
  const c = shell("Панель · " + D(x.date).slice(0, 5), `
  <div class="grid g4">
    ${big("Выручка за месяц", RUB(s.revenue), s.plan ? `${s.plan_pct}% плана ${RUB(s.plan)}` + bar(s.plan_pct) : "план не задан — Настройки", "#/reports")}
    ${big("Прогноз на конец месяца", RUB(s.forecast), `при текущем темпе, день ${s.day} из ${s.days}` + (s.plan ? bar(s.forecast_pct) : ""), "#/reports", s.plan && s.forecast_pct < 100 ? "r" : "")}
    ${big("Маржа", RUB(s.margin), s.margin_pct != null ? s.margin_pct + "% от выручки · " + R(s.tons) + " т" : "", "#/reports", s.margin < 0 ? "r" : "")}
    ${big("Можно выставить сейчас", RUB(m.uninvoiced), "закрытые рейсы без счёта", "#/invoices", m.uninvoiced > 0 ? "y" : "")}
    ${big("Долг клиентов", RUB(m.debt), `просрочено ${RUB(m.overdue)}`, "#/reports/aging", m.overdue > 0 ? "r" : "")}
    ${big("Пришло денег за месяц", RUB(m.paid_month), "оплаты клиентов", "#/payments")}
    ${big("Рейсы сегодня", `${t.done} / ${t.trips}`, `${R(t.tons)} т выгружено`, "#/dispatch")}
    ${big("Машины", `${L.g}${t.green} ${L.y}${t.yellow} ${L.r}${t.red}`, "в работе / внимание / проблема", "#/vehicles", t.red ? "r" : "")}
  </div>
  <div class="grid g2 mt">
    <div class="card"><h3>Требует реакции</h3>${x.problems.map(p => `<a class="oprob ${p.sev}" href="${p.href}"><b>${p.n}</b><div>${H(p.title)}${p.sub ? `<small>${H(p.sub)}</small>` : ""}</div></a>`).join("") || `<p class="muted">Проблем нет 👍</p>`}</div>
    <div class="card"><h3>Продажи за месяц</h3><div class="kv"><span>Новых лидов</span><b>${s.leads}</b><span>Стали клиентами</span><b>${s.won}${s.conv != null ? ` (${s.conv}%)` : ""}</b><span>Заявок</span><b>${s.orders}</b></div>
      <h3 class="mt">Менеджеры</h3>${x.managers.length ? `<table class="t"><tr><th></th><th>Менеджер</th><th>Выручка</th><th>Заявок</th><th>Лидов в работе</th><th>Не перезвонил</th></tr>${x.managers.map(u => `<tr><td>${L[u.light]}</td><td>${H(u.name)}</td><td>${RUB(u.revenue)}</td><td>${u.orders}</td><td>${u.leads}</td><td class="${u.overdue_calls ? "red" : ""}">${u.overdue_calls}</td></tr>`).join("")}</table>` : `<p class="muted sm">Нет пользователей с ролью «Менеджер продаж»</p>`}</div>
  </div>
  <div class="card mt"><h3>Техника — светофор на сегодня</h3><table class="t"><tr><th></th><th>Машина</th><th>Рейсов</th><th>Выполнено</th><th>Тонн</th><th>Выручка</th><th>Почему</th></tr>
    ${x.fleet.map(v => `<tr class="cl" data-v="${v.id}"><td>${L[v.light]}</td><td><b>${H(v.plate)}</b> <span class="muted sm">${H(v.model)}</span></td><td>${v.trips}</td><td>${v.done}</td><td>${R(v.tons)}</td><td>${RUB(v.revenue)}</td><td class="sm">${H(v.why.join("; "))}</td></tr>`).join("") || `<tr><td colspan="7" class="muted">Техника не заведена</td></tr>`}</table></div>`,
    `<button class="btn" id="mytg">Мой Telegram</button><button class="btn" id="dg">Сводка в Telegram</button><a class="btn p" href="#/voice">🎙 Заявка голосом</a>`);
  $$("tr[data-v]", c).forEach(r => r.onclick = () => openForm("vehicles", +r.dataset.v));
  $("#mytg").onclick = () => showLink("u", ME.id, "себе (руководителю)");
  $("#dg").onclick = () => run(async () => { const d = await api("/api/owner/digest"); const r = await api("/api/owner/digest/send", {body: {}});
    modal("Утренняя сводка", `<pre class="dig">${H(d.text)}</pre><p class="sm muted">${r.sent ? `Отправлено в Telegram: ${r.sent}` : "Telegram руководителя не подключён: Пользователи → карточка → «Подключить Telegram». Сводка приходит сама каждый день утром."}</p>`, "sm"); });
}

/* ---------- заявка голосом ---------- */
async function pageVoice() {
  const c = shell("Заявка голосом", `<div class="grid g2"><div class="card">
    <p>Нажмите и скажите заявку: <b>клиент, объект, материал, сколько, когда</b>.<br><span class="muted sm">Например: «Стройинвест, Подольск, щебень гранитный 20-40, три машины на завтра». Речь распознаётся на этом компьютере и никуда не отправляется.</span></p>
    <div class="row"><button class="btn p" id="rec">🎙 Начать запись</button><span id="rs" class="muted sm"></span></div>
    <label class="mt">Или напишите текстом</label><textarea class="i" id="vt" rows="3" placeholder="Стройинвест Подольск щебень 20-40 60 тонн завтра"></textarea>
    <div class="row mt"><button class="btn" id="vp">Разобрать</button></div></div>
    <div class="card" id="vd"><h3>Черновик</h3><p class="muted sm">Здесь появится заявка. Проверьте и нажмите «Создать».</p></div></div>`);
  let mr = null, chunks = [];
  const show = async p => {
    const [cl, mt] = await Promise.all([api("/api/e/clients?limit=1000"), api("/api/e/materials?limit=1000")]);
    const sites = p.client_id ? (await api(`/api/e/sites?client_id=${p.client_id}`)).rows : [];
    const sel = (id, rows, v, f = "name") => `<select class="i" id="${id}"><option value=""></option>${rows.map(r => `<option value="${r.id}" ${r.id === v ? "selected" : ""}>${H(r[f])}</option>`).join("")}</select>`;
    $("#vt").value = p.text || $("#vt").value;
    $("#vd").innerHTML = `<h3>Черновик заявки</h3>${p.missing.length ? `<div class="note mb">Не понял: ${H(p.missing.join(", "))} — выберите вручную</div>` : `<div class="note g mb">Всё распознано — проверьте</div>`}
      <div class="form"><div><label>Клиент</label>${sel("vc", cl.rows, p.client_id)}</div><div><label>Объект</label>${sel("vs", sites, p.site_id)}</div>
      <div><label>Материал</label>${sel("vm", mt.rows, p.material_id)}</div><div><label>Количество</label><input class="i" id="vq" value="${p.qty ?? ""}"></div>
      <div><label>Ед.</label><select class="i" id="vu">${META.enums.unit.map(([k, t]) => `<option value="${k}" ${k === p.unit ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div><label>Дата</label><input class="i" type="date" id="vdt" value="${p.date || addDays(TODAY(), 1)}"></div></div>
      ${p.phone ? `<p class="sm">Телефон в тексте: ${H(p.phone)}</p>` : ""}<div class="row mt"><button class="btn p" id="vok">Создать заявку</button></div>`;
    $("#vc").onchange = async () => { const s = (await api(`/api/e/sites?client_id=${$("#vc").value}`)).rows; $("#vs").innerHTML = `<option value=""></option>` + s.map(r => `<option value="${r.id}">${H(r.name)}</option>`).join(""); if (s.length === 1) $("#vs").value = s[0].id; };
    $("#vok").onclick = () => run(async () => { const r = await api("/api/voice/order", {body: {text: $("#vt").value, client_id: +$("#vc").value || null, site_id: +$("#vs").value || null,
      material_id: +$("#vm").value || null, qty: parseFloat(String($("#vq").value).replace(",", ".")) || null, unit: $("#vu").value, date: $("#vdt").value}});
      toast("Заявка создана"); location.hash = "#/orders/" + r.id; });
  };
  $("#vp").onclick = () => run(async () => show(await api("/api/voice/parse", {body: {text: $("#vt").value}})));
  $("#rec").onclick = () => run(async () => {
    if (mr && mr.state === "recording") { mr.stop(); return; }
    if (!navigator.mediaDevices) throw new Error("Микрофон доступен только на этом ПК (localhost) или по https");
    const st = await navigator.mediaDevices.getUserMedia({audio: true});
    mr = new MediaRecorder(st); chunks = [];
    mr.ondataavailable = e => chunks.push(e.data);
    mr.onstop = () => run(async () => { st.getTracks().forEach(t => t.stop()); $("#rec").textContent = "🎙 Начать запись"; $("#rs").textContent = "Распознаю…";
      const fd = new FormData(); fd.append("file", new Blob(chunks, {type: mr.mimeType}), "voice.webm");
      try { await show(await api("/api/voice/audio", {body: fd})); } finally { $("#rs").textContent = ""; } });
    mr.start(); $("#rec").textContent = "⏹ Закончить"; $("#rs").textContent = "Идёт запись…";
  });
}

/* ---------- клиент (карточка 360) ---------- */
async function pageClient(id) {
  const [c, b, orders, invs, sites, prices, contracts] = await Promise.all([api("/api/e/clients/" + id), api("/api/balance/" + id).catch(() => null),
    api(`/api/e/orders?client_id=${id}&limit=50`), api(`/api/e/invoices?client_id=${id}&limit=50`).catch(() => ({rows: []})), api(`/api/e/sites?client_id=${id}`),
    api(`/api/e/client_prices?client_id=${id}`), api(`/api/e/contracts?client_id=${id}`)]);
  const cc = shell(c.name, `<div class="row mb"><button class="btn" id="edit">Изменить</button><button class="btn p" id="neworder">+ Заявка</button><button class="btn" id="newsite">+ Объект</button>
    <button class="btn" id="newprice">+ Своя цена</button><button class="btn" id="cab">Доступ в кабинет</button><button class="btn" id="tg">Telegram-уведомления</button>
    <a class="btn" target="_blank" href="/doc/recon/${id}?date_from=${TODAY().slice(0, 4)}-01-01&date_to=${TODAY()}">Акт сверки</a></div>
    <div class="grid g4">${b ? `<div class="kpi ${b.debt > 0 ? "r" : ""}"><span>Долг по счетам</span><b>${RUB(b.debt)}</b></div><div class="kpi"><span>Отгружено без счёта</span><b>${RUB(b.uninvoiced)}</b></div>
    <div class="kpi"><span>Лимит</span><b>${RUB(c.credit_limit) || "—"}</b><small>${H(lbl("pay_terms", c.pay_terms))}, отсрочка ${c.delay_days || 0} дн.</small></div><div class="kpi ${b.overdue.length ? "r" : ""}"><span>Просроченных счетов</span><b>${b.overdue.length}</b></div>` : ""}</div>
    <div class="grid g2 mt"><div class="card"><h3>Реквизиты</h3><div class="kv"><span>ИНН / КПП</span><div>${H(c.inn || "—")} / ${H(c.kpp || "—")}</div><span>Адрес</span><div>${H(c.legal_addr || "")}</div>
    <span>Контакт</span><div>${H(c.contact || "")} ${H(c.phone || "")}</div><span>E-mail</span><div>${H(c.email || "")}</div><span>Менеджер</span><div>${H(c.manager_id__t || "")}</div><span>Telegram</span><div>${c.tg_chat ? "подключён ✓" : "не подключён"}</div></div>
    <h3 class="mt">Объекты</h3>${sites.rows.map(s => `<div class="sm">⌂ <a href="#" data-site="${s.id}">${H(s.name)}</a> — ${H(s.address)} ${s.distance_km ? `(${R(s.distance_km)} км)` : ""}</div>`).join("") || `<p class="muted sm">Нет объектов</p>`}
    <h3 class="mt">Индивидуальные цены</h3>${prices.rows.map(p => `<div class="sm">${H(p.material_id__t)}: <b>${RUB(p.price)}</b>${p.valid_to ? " до " + D(p.valid_to) : ""}</div>`).join("") || `<p class="muted sm">Базовый прайс${c.discount_pct ? ` − ${c.discount_pct}%` : ""}</p>`}
    <h3 class="mt">Договоры</h3>${contracts.rows.map(x => `<div class="sm">§ ${H(x.number)} от ${D(x.date)}${x.valid_to ? ", до " + D(x.valid_to) : ""}</div>`).join("") || `<p class="muted sm">Нет</p>`}</div>
    <div class="card">${activityBox("clients", id, c._activity)}</div></div>
    <h3 class="mt">Заявки</h3><div class="tw"><table class="t"><tr><th>№</th><th>Дата</th><th>Материал</th><th class=n>Кол-во</th><th class=n>Сумма</th><th>Статус</th></tr>${orders.rows.map(o => `<tr class="cl" data-h="#/orders/${o.id}"><td>${H(o.number)}</td><td>${D(o.date)}</td><td>${H(o.material_id__t)}</td><td class=n>${R(o.qty)} ${H(lbl("unit", o.unit))}</td><td class=n>${RUB(o.total)}</td><td>${tag("order_status", o.status)}</td></tr>`).join("")}</table></div>
    <h3 class="mt">Счета</h3><div class="tw"><table class="t"><tr><th>№</th><th>Дата</th><th class=n>Сумма</th><th class=n>Оплачено</th><th>Оплатить до</th><th>Статус</th></tr>${invs.rows.map(i => `<tr class="cl" data-h="#/invoices/${i.id}"><td>${H(i.number)}</td><td>${D(i.date)}</td><td class=n>${RUB(i.total)}</td><td class=n>${RUB(i.paid)}</td><td>${D(i.due_date)}</td><td>${tag("inv_status", i.status)}</td></tr>`).join("")}</table></div>`);
  $("#edit").onclick = () => openForm("clients", id);
  $("#neworder").onclick = () => openForm("orders", null, {client_id: id, date: addDays(TODAY(), 1), unit: "t", status: "new", source: "phone"});
  $("#newsite").onclick = () => openForm("sites", null, {client_id: id});
  $("#newprice").onclick = () => openForm("client_prices", null, {client_id: id});
  $$("[data-site]", cc).forEach(a => a.onclick = e => { e.preventDefault(); openForm("sites", +a.dataset.site); });
  $$("tr[data-h]", cc).forEach(tr => tr.onclick = () => location.hash = tr.dataset.h);
  $("#tg").onclick = () => showLink("c", id, "клиенту");
  $("#cab").onclick = () => run(async () => {
    const login = prompt("Логин для кабинета клиента (латиницей):", (c.inn || "client" + id)); if (!login) return;
    const pw = Math.random().toString(36).slice(2, 10);
    await api("/api/e/users", {body: {login, name: c.name, role: "client", client_id: id, password: pw, active: 1}});
    modal("Кабинет клиента создан", `<p>Передайте клиенту:</p><div class="note g">Адрес: <b>${location.origin}</b><br>Логин: <b>${H(login)}</b><br>Пароль: <b>${H(pw)}</b></div><p class="sm muted">Пароль показан один раз. Сменить — Настройки → Пользователи.</p>`, "sm");
  });
  wireActivity("clients", id);
}
async function showLink(kind, id, who) {
  const l = await api(`/api/link/${kind}/${id}`);
  modal("Подключение Telegram-бота", l.url ? `<p>Отправьте ${who} эту ссылку. После нажатия «Запустить» бот привяжется автоматически:</p><div class="note g"><a href="${l.url}" target="_blank">${l.url}</a></div>
    <p class="sm muted">Или: найти бота @${H(l.bot)} и отправить ему <b>/start ${H(l.code)}</b></p>` : `<div class="note">Бот ещё не подключён. Руководитель вводит токен бота в «Настройки → Компания и боты». Код привязки: <b>${H(l.code)}</b></div>`, "sm");
}

/* ---------- лид ---------- */
async function pageLead(id) {
  const l = await api("/api/e/leads/" + id);
  const c = shell("Лид: " + l.name, `<div class="grid g2"><div class="card"><div class="row mb" style="justify-content:space-between"><h3>${H(l.name)}</h3>${tag("lead_stage", l.stage)}</div>
    <div class="kv"><span>Телефон</span><b>${l.phone ? `<a href="tel:${H(l.phone)}">${H(l.phone)}</a>` : "—"}</b><span>Источник</span><div>${H(lbl("lead_source", l.source))}</div><span>Что нужно</span><div>${H(l.material || "")} ${H(l.qty || "")}</div>
    <span>Куда</span><div>${H(l.address || "")}</div><span>Потенциал</span><div>${RUB(l.amount)}</div><span>Следующий контакт</span><div>${D(l.next_date)}</div><span>Комментарий</span><div>${H(l.note || "")}</div></div>
    <div class="row mt">${META.enums.lead_stage.map(([k, t]) => `<button class="btn s ${k === l.stage ? "d" : ""}" data-stage="${k}">${H(t)}</button>`).join("")}</div>
    <div class="row mt"><button class="btn" id="edit">Изменить</button>${l.client_id ? `<a class="btn" href="#/clients/${l.client_id}">Карточка клиента</a>` : `<button class="btn p" id="conv">Сделать клиентом и создать заявку</button>`}</div></div>
    <div class="card">${activityBox("leads", id, l._activity)}</div></div>`);
  $("#edit").onclick = () => openForm("leads", id);
  $$("[data-stage]", c).forEach(b => b.onclick = () => run(async () => { await api(`/api/e/leads/${id}`, {method: "PUT", body: {stage: b.dataset.stage}}); route(); }));
  if ($("#conv")) $("#conv").onclick = () => run(async () => {
    const r = await api("/api/e/clients", {body: {name: l.name, phone: l.phone, email: l.email, inn: l.inn, pay_terms: "prepay", manager_id: l.manager_id || ME.id}});
    await api(`/api/e/leads/${id}`, {method: "PUT", body: {stage: "won", client_id: r.id}});
    if (l.address) await api("/api/e/sites", {body: {client_id: r.id, name: l.address.slice(0, 40), address: l.address}});
    delete REFCACHE.clients; delete REFCACHE.sites;
    toast("Клиент создан"); openForm("orders", null, {client_id: r.id, date: addDays(TODAY(), 1), unit: "t", status: "new", source: "crm", comment: [l.material, l.qty].filter(Boolean).join(", ")}, oid => location.hash = "#/orders/" + oid);
  });
  wireActivity("leads", id);
}

/* ---------- путевой лист ---------- */
async function pageWaybill(id) {
  const w = await api("/api/e/waybills/" + id);
  const trips = (await api(`/api/e/trips?waybill_id=${id}`)).rows;
  const c = shell("Путевой лист " + w.number, `<div class="row mb"><a class="btn" target="_blank" href="/doc/waybill/${id}">🖨 Печать</a>${w.status !== "closed" ? `<button class="btn p" id="close">Закрыть путевой лист</button>` : ""}<button class="btn" id="edit">Изменить</button></div>
    <div class="card"><div class="kv"><span>Дата</span><b>${D(w.date)}</b><span>Машина</span><div>${H(w.vehicle_id__t)}</div><span>Водитель</span><div>${H(w.driver_id__t)}</div>
    <span>Одометр</span><div>${R(w.odo_start)} → ${R(w.odo_end) || "…"} ${w.odo_end && w.odo_start ? `(<b>${R(w.odo_end - w.odo_start)} км</b>)` : ""}</div><span>Топливо</span><div>${R(w.fuel_start)} + ${R(w.fuel_issued)} → ${R(w.fuel_end)} л</div>
    <span>Медосмотр / техконтроль</span><div>${H(w.med_pre || "—")} / ${H(w.tech_check || "—")}</div><span>Статус</span><div>${tag("wb_status", w.status)} ЭПЛ: ${tag("doc_status", w.edo_status)}</div></div></div>
    <h3 class="mt">Рейсы по листу</h3><div class="tw">${tripsTable(trips)}</div>`);
  $("#edit").onclick = () => openForm("waybills", id);
  if ($("#close")) $("#close").onclick = () => {
    const b = modal("Закрыть путевой лист", `<div class="form"><div><label>Одометр при возврате</label><input class="i" name="odo_end" type="number" value="${w.odo_end || ""}"></div>
      <div><label>Выдано топлива, л</label><input class="i" name="fuel_issued" type="number" step="any" value="${w.fuel_issued || ""}"></div><div><label>Остаток топлива, л</label><input class="i" name="fuel_end" type="number" step="any" value="${w.fuel_end || ""}"></div>
      <div><label>Послерейсовый медосмотр</label><input class="i" name="med_post" value="${H(w.med_post || "")}"></div></div><div class="row end mt"><button class="btn p" id="cgo">Закрыть</button></div>`, "sm");
    $("#cgo", b).onclick = () => run(async () => { await api(`/api/waybills/${id}/close`, {body: formData(b)}); closeModal(); toast("Путевой лист закрыт"); route(); });
  };
  $$("tr.cl", c).forEach(tr => tr.onclick = () => location.hash = "#/trips/" + tr.dataset.id);
}

/* ---------- счета ---------- */
async function pageInvoice(id) {
  const i = await api("/api/e/invoices/" + id);
  const lines = (await api(`/api/e/invoice_lines?invoice_id=${id}`)).rows;
  const pays = (await api(`/api/e/payments?invoice_id=${id}`).catch(() => ({rows: []}))).rows;
  shell("Счёт " + i.number, `<div class="row mb"><a class="btn" target="_blank" href="/doc/invoice/${id}">🖨 Счёт</a><a class="btn" target="_blank" href="/doc/upd/${id}">🖨 УПД</a>
    <button class="btn p" id="pay">+ Оплата</button><button class="btn" id="edit">Изменить</button></div>
    <div class="grid g4"><div class="kpi"><span>Клиент</span><b style="font-size:17px">${H(i.client_id__t)}</b></div><div class="kpi"><span>Сумма</span><b>${RUB(i.total)}</b><small>НДС ${RUB(i.vat)}</small></div>
    <div class="kpi"><span>Оплачено</span><b>${RUB(i.paid)}</b></div><div class="kpi ${i.due_date < TODAY() && i.status !== "paid" ? "r" : ""}"><span>Оплатить до</span><b>${D(i.due_date)}</b><small>${tag("inv_status", i.status)}</small></div></div>
    <h3 class="mt">Строки</h3><div class="tw"><table class="t"><tr><th>Наименование</th><th class=n>Кол-во</th><th>Ед.</th><th class=n>Цена</th><th class=n>Сумма</th></tr>${lines.map(l => `<tr><td>${H(l.name)}</td><td class=n>${R(l.qty)}</td><td>${H(l.unit)}</td><td class=n>${RUB(l.price)}</td><td class=n>${RUB(l.sum)}</td></tr>`).join("")}</table></div>
    <h3 class="mt">Оплаты</h3><div class="tw"><table class="t"><tr><th>Дата</th><th class=n>Сумма</th><th>П/п</th><th>Назначение</th></tr>${pays.map(p => `<tr><td>${D(p.date)}</td><td class=n>${RUB(p.amount)}</td><td>${H(p.doc_no || "")}</td><td class=sm>${H(p.purpose || "")}</td></tr>`).join("") || `<tr><td colspan=4 class=muted>Нет</td></tr>`}</table></div>`);
  $("#edit").onclick = () => openForm("invoices", id);
  $("#pay").onclick = () => openForm("payments", null, {date: TODAY(), direction: "in", client_id: i.client_id, invoice_id: id, amount: Math.round(((i.total || 0) - (i.paid || 0)) * 100) / 100, source: "manual"});
}
function periodDialog(title, extra, cb) {
  const prev = new Date(); prev.setDate(0);
  const pf = prev.toISOString().slice(0, 8) + "01", pt = prev.toISOString().slice(0, 10);
  const b = modal(title, `<div class="form"><div><label>С</label><input class="i" type="date" name="date_from" value="${pf}"></div><div><label>По</label><input class="i" type="date" name="date_to" value="${pt}"></div>${extra}</div>
    <div class="row mt"><button class="btn s" data-p="m">Прошлый месяц</button><button class="btn s" data-p="c">Этот месяц</button><button class="btn s" data-p="w">Эта неделя</button><div style="flex:1"></div><button class="btn p" id="pgo">Сформировать</button></div><div id="pres" class="mt"></div>`, "sm");
  const set = (a, z) => { $("[name=date_from]", b).value = a; $("[name=date_to]", b).value = z; };
  $$("[data-p]", b).forEach(x => x.onclick = () => { const t = TODAY(); if (x.dataset.p === "m") set(pf, pt); if (x.dataset.p === "c") set(M0(), t); if (x.dataset.p === "w") { const d = new Date(); const k = (d.getDay() + 6) % 7; set(addDays(t, -k), t); } });
  fillRefs(b);
  $("#pgo", b).onclick = () => run(async () => cb(formData(b), $("#pres", b)));
}
function buildInvoices() {
  periodDialog("Счета и УПД по закрытым рейсам", `<div class="w2"><label>Клиент (пусто — все с отгрузками)</label><select class="i" name="client_id" data-ref="clients"></select></div>`, async (d, out) => {
    const r = await api("/api/invoices/build", {body: d});
    out.innerHTML = `<div class="note g">Создано счетов: <b>${r.invoices.length}</b>. К каждому сформирован УПД. Клиентам с подключённым ботом ушло уведомление.</div>` + (r.errors.length ? `<div class="note mt">${r.errors.map(H).join("<br>")}</div>` : "");
    setTimeout(route, 400);
  });
}
function buildPayroll() {
  periodDialog("Расчёт зарплаты водителей", `<div class="w2"><label>Водитель (пусто — все)</label><select class="i" name="driver_id" data-ref="drivers"></select></div>`, async (d, out) => {
    const r = await api("/api/payroll/build", {body: d});
    out.innerHTML = `<div class="note g">Рассчитано ведомостей: <b>${r.payroll.length}</b>. Откройте ведомость, чтобы добавить премии, удержания и аванс.</div>`; setTimeout(route, 400);
  });
}

/* ---------- выписка банка ---------- */
function pageBank() {
  const c = shell("Выписка банка", `<div class="card" style="max-width:760px"><h3>Загрузка выписки 1С (kl_to_1c.txt)</h3>
    <p class="muted">Выгрузите выписку из интернет-банка в формате «1С:Предприятие» (есть в Сбере, Точке, Альфе, ВТБ, Модуле, Тинькофф). Система сама найдёт клиента по ИНН, разнесёт оплату на счёт по номеру в назначении платежа или на самый старый неоплаченный, и пропустит уже загруженные платежи.</p>
    <div class="row"><input type="file" id="bf" accept=".txt"><button class="btn p" id="bgo">Загрузить</button></div><div id="bres" class="mt"></div>
    <p class="sm muted mt">ИНН вашей компании для определения входящих — в Настройках.</p></div>`);
  $("#bgo").onclick = () => run(async () => {
    const f = $("#bf").files[0]; if (!f) return toast("Выберите файл", true);
    const fd = new FormData(); fd.append("file", f);
    const r = await api("/api/bank/import", {body: fd});
    $("#bres").innerHTML = `<div class="note g">Добавлено платежей: <b>${r.added}</b>, привязано к клиентам: <b>${r.matched}</b>, повторов пропущено: ${r.skipped}</div>` +
      (r.unmatched.length ? `<div class="note mt"><b>Не нашли клиента по ИНН</b> — добавьте ИНН в карточку клиента и привяжите платёж вручную:<br>${r.unmatched.map(H).join("<br>")}</div>` : "");
  });
}

/* ---------- отчёты ---------- */
const REPORTS = [["clients", "По клиентам"], ["materials", "По материалам"], ["vehicles", "По машинам"], ["drivers", "По водителям"], ["suppliers", "По карьерам"], ["days", "По дням"],
  ["aging", "Дебиторка по срокам"], ["fuel", "Топливо: факт и норма"], ["stock", "Остатки на складах"]];
async function pageReports(kind = "clients") {
  const p = JSON.parse(sessionStorage.rep || "{}"); const df = p.df || M0(), dt = p.dt || TODAY();
  const c = shell("Отчёты", `<div class="tabs">${REPORTS.map(([k, t]) => `<a href="#/reports/${k}" class="${k === kind ? "on" : ""}">${t}</a>`).join("")}</div>
    <div class="row mb"><input class="i" type="date" id="rf" value="${df}" style="max-width:170px"><input class="i" type="date" id="rt" value="${dt}" style="max-width:170px"><button class="btn" id="rgo">Показать</button><div style="flex:1"></div><button class="btn" id="rx">⇩ CSV для Excel</button></div><div class="tw" id="rr"></div>`);
  const load = async () => {
    sessionStorage.rep = JSON.stringify({df: $("#rf").value, dt: $("#rt").value});
    const rows = await api(`/api/report/${kind}?date_from=${$("#rf").value}&date_to=${$("#rt").value}`);
    let cols;
    if (kind === "aging") cols = [["client", "Клиент"], ["0", "Не просрочено", 1], ["1-15", "1–15 дн.", 1], ["16-30", "16–30 дн.", 1], ["31-60", "31–60 дн.", 1], ["60+", "Более 60", 1], ["total", "Итого долг", 1], ["uninvoiced", "Без счёта", 1]];
    else if (kind === "fuel") cols = [["plate", "Машина"], ["km", "Пробег, км", 2], ["liters", "Заправлено, л", 2], ["norm_l", "По норме, л", 2], ["over_l", "Перерасход, л", 2], ["fact_100", "Факт л/100", 2], ["norm_100", "Норма л/100", 2], ["amount", "Сумма", 1]];
    else if (kind === "stock") cols = [["warehouse", "Склад"], ["material", "Материал"], ["qty", "Остаток, т", 2], ["avg_price", "Ср. цена", 1]];
    else cols = [["name", kind === "days" ? "День" : "Название"], ["trips", "Рейсов", 2], ["tons", "Тонн", 2], ["revenue", "Выручка", 1], ["material", "Материал", 1], ["transport", "Транспорт", 1], ["margin", "Маржа", 1], ["margin_pct", "Маржа, %", 2]];
    const fmt = (c, v) => c[2] === 1 ? RUB(v) : c[2] === 2 ? R(v) : (kind === "days" ? D(v) : H(v ?? "—"));
    const tot = cols.map(c => c[2] && !["margin_pct", "fact_100", "norm_100", "avg_price"].includes(c[0]) ? rows.reduce((s, r) => s + (+r[c[0]] || 0), 0) : null);
    $("#rr").innerHTML = rows.length ? `<table class="t"><tr>${cols.map(c => `<th class="${c[2] ? "n" : ""}">${c[1]}</th>`).join("")}</tr>${rows.map(r => `<tr>${cols.map(c => `<td class="${c[2] ? "n" : ""}" style="${c[0] === "over_l" && r.over_l > 0 ? "color:var(--red2);font-weight:600" : ""}">${fmt(c, r[c[0]])}</td>`).join("")}</tr>`).join("")}
      <tr>${cols.map((c, i) => `<td class="n b">${i === 0 ? "Итого" : tot[i] != null ? fmt(c, tot[i]) : ""}</td>`).join("")}</tr></table>` : `<p class="muted" style="padding:14px">Нет данных за период</p>`;
    $("#rx").onclick = () => { const csv = "\ufeff" + [cols.map(c => c[1]).join(";"), ...rows.map(r => cols.map(c => String(r[c[0]] ?? "").replace(".", ",")).join(";"))].join("\n");
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], {type: "text/csv"})); a.download = `egm_report_${kind}.csv`; a.click(); };
  };
  $("#rgo").onclick = () => run(load); run(load);
}
async function pageFleet() {
  const rows = await api("/api/report/fleet?date_from=&date_to=");
  const c = shell("Сроки документов и ТО", `<p class="muted">Всё, что истекает в ближайшие 60 дней или уже просрочено. Механику и руководителю ежедневно приходит уведомление. Просроченная машина или водитель не назначатся на рейс без подтверждения.</p>
    <div class="tw"><table class="t"><tr><th></th><th>Кто</th><th>Что</th><th>Срок</th></tr>${rows.map(a => `<tr class="cl" data-k="${a.kind}" data-id="${a.id}"><td>${a.overdue ? "🔴 просрочено" : "🟡 скоро"}</td><td><b>${H(a.who)}</b></td><td>${H(a.what)}</td><td>${D(a.date)}</td></tr>`).join("") || `<tr><td colspan=4 class=muted>Всё в порядке</td></tr>`}</table></div>`);
  $$("tr.cl", c).forEach(tr => tr.onclick = () => openForm(tr.dataset.k === "vehicle" ? "vehicles" : "drivers", +tr.dataset.id));
}
async function pageStock() { location.hash = "#/reports/stock"; }

/* ---------- импорт ---------- */
function pageImport() {
  const ents = ["clients", "sites", "materials", "client_prices", "suppliers", "supplier_prices", "vehicles", "drivers", "carriers", "zones", "leads", "orders", "payments", "fuel"].filter(e => ME.role === "admin" || ENT(e).roles_w.includes(ME.role));
  const c = shell("Импорт из Excel", `<div class="card" style="max-width:820px"><h3>Перенос данных из Excel и Saby</h3>
    <ol class="muted"><li>Выберите, что загружаем, и скачайте шаблон.</li><li>Скопируйте в шаблон данные из ваших таблиц или выгрузки Saby (заголовки колонок — как в шаблоне).</li>
    <li>Нажмите «Проверить» — система покажет ошибки, ничего не записывая. Затем «Загрузить».</li></ol>
    <p class="sm muted">Порядок переноса: клиенты → объекты → номенклатура → цены → карьеры → техника → водители → заявки. Связанные поля (клиент, материал, машина) пишите названием так же, как в справочнике. Колонка ID — для обновления уже загруженных записей.</p>
    <div class="form"><div><label>Что загружаем</label><select class="i" id="ie">${ents.map(e => `<option value="${e}">${H(ENT(e).title)}</option>`).join("")}</select></div><div><label>Файл .xlsx</label><input type="file" id="if" accept=".xlsx"></div></div>
    <div class="row mt"><a class="btn" id="itpl">⇩ Шаблон</a><button class="btn" id="idry">Проверить</button><button class="btn p" id="igo">Загрузить</button></div><div id="ires" class="mt"></div></div>`);
  const upd = () => $("#itpl").href = `/api/export/${$("#ie").value}.xlsx?template=1`; $("#ie").onchange = upd; upd();
  const send = dry => run(async () => {
    const f = $("#if").files[0]; if (!f) return toast("Выберите файл", true);
    const fd = new FormData(); fd.append("file", f); fd.append("dry", dry ? "1" : "0");
    const r = await api(`/api/import/${$("#ie").value}`, {body: fd});
    Object.keys(REFCACHE).forEach(k => delete REFCACHE[k]);
    $("#ires").innerHTML = `<div class="note ${r.errors.length ? "" : "g"}">${dry ? "Проверка: будет" : "Готово:"} добавлено <b>${r.added}</b>, обновлено <b>${r.updated}</b>. Распознаны колонки: ${r.columns.map(H).join(", ")}</div>` +
      (r.errors.length ? `<div class="note r mt"><b>Ошибки (${r.errors.length}):</b><br>${r.errors.slice(0, 50).map(H).join("<br>")}</div>` : "");
  });
  $("#idry").onclick = () => send(true); $("#igo").onclick = () => send(false);
}

/* ---------- настройки ---------- */
const SETTINGS = [["Компания", [["company_name", "Название (для документов)"], ["company_inn", "ИНН"], ["company_kpp", "КПП"], ["company_ogrn", "ОГРН"], ["company_addr", "Юридический адрес"],
  ["company_bank", "Банк, БИК, р/с, к/с"], ["company_phone", "Телефон диспетчерской"], ["company_director", "Руководитель (ФИО)"], ["company_accountant", "Главный бухгалтер (ФИО)"]]],
  ["Расчёты", [["plan_month_revenue", "План выручки на месяц, ₽ (для панели руководителя)"], ["stuck_hours", "Рейс «завис», если нет движения, часов"], ["vat_pct", "НДС, % (0 — без НДС / УСН)"], ["fuel_price", "Цена дизеля, ₽/л"], ["fuel_norm", "Норма расхода по умолчанию, л/100 км"], ["default_capacity_t", "Тонн в одну машину по умолчанию"],
    ["default_distance_km", "Плечо по умолчанию, км"], ["max_trips_per_day", "Макс. рейсов на машину в день"], ["alert_days", "Предупреждать о сроках за, дней"],
    ["auto_close", "Закрывать рейс сразу после выгрузки (1/0)"], ["doc_mode_upd", "Закрывающий документ: 1 — УПД, 0 — акт"], ["notify_clients", "Уведомлять клиентов в Telegram (1/0)"]]],
  ["Telegram-бот", [["digest_on", "Утренняя сводка руководителю в Telegram (1/0)"], ["digest_hour", "Час отправки сводки (по умолчанию 8)"], ["tg_token", "Токен бота от @BotFather"], ["tg_proxy", "Прокси (если Telegram заблокирован), например socks5://127.0.0.1:10808"], ["tg_enabled", "Бот включён (1/0)"]]],
  ["Интеграции", [["gps_key", "Ключ для трекеров ГЛОНАСС (заголовок X-GPS-Key)"], ["edo_operator", "Оператор ЭДО (для подключения ЭТрН/ЭПЛ)"]]]];
async function pageSettings() {
  const s = await api("/api/settings");
  const c = shell("Компания и боты", SETTINGS.map(([g, fs]) => `<div class="card mb"><h3>${g}</h3><div class="form">${fs.map(([k, t]) => `<div class="${k === "company_bank" || k === "tg_proxy" ? "w2" : ""}"><label>${H(t)}</label><input class="i" data-k="${k}" value="${H(s[k] ?? "")}"></div>`).join("")}</div></div>`).join("") +
    `<div class="row"><button class="btn p" id="ssave">Сохранить</button><button class="btn" id="sbk">Резервная копия сейчас</button><a class="btn" href="/api/backup/download">⇩ Скачать базу</a></div>
    <p class="sm muted mt">Бот: имя @${H(s.tg_bot_username || "—")}. Резервная копия базы делается автоматически каждый день (хранятся последние 30) в папке data/backups.</p>`);
  $("#ssave").onclick = () => run(async () => { const d = {}; $$("[data-k]", c).forEach(i => d[i.dataset.k] = i.value); await api("/api/settings", {body: d}); toast("Сохранено"); });
  $("#sbk").onclick = () => run(async () => { const r = await api("/api/backup", {body: {}}); toast("Копия: " + r.file); });
}
async function pageAudit() {
  const rows = await api("/api/audit");
  shell("Журнал действий", `<div class="tw"><table class="t"><tr><th>Когда</th><th>Кто</th><th>Действие</th><th>Раздел</th><th>ID</th><th>Данные</th></tr>${rows.map(a => `<tr><td class=sm>${D(a.ts)}</td><td>${H(a.uname || "система")}</td><td>${H(a.action)}</td><td>${H(ENT(a.entity)?.title || a.entity)}</td><td>${a.entity_id}</td><td class="sm muted">${H((a.data || "").slice(0, 160))}</td></tr>`).join("")}</table></div>`);
}
async function pageDriverCard(id) {
  await openForm("drivers", id);
  const box = $(".modal .box"); if (!box) return;
  const r = document.createElement("div"); r.className = "row mt";
  r.innerHTML = `<button class="btn" id="dlink">Подключить Telegram водителю</button><button class="btn" id="dacc">Вход в приложение водителя</button>`;
  box.appendChild(r);
  $("#dlink").onclick = () => showLink("d", id, "водителю");
  $("#dacc").onclick = () => run(async () => {
    const d = await api("/api/e/drivers/" + id); const login = prompt("Логин водителя:", (d.phone || "").replace(/\D/g, "") || "driver" + id); if (!login) return;
    const pw = String(Math.floor(100000 + Math.random() * 899999));
    await api("/api/e/users", {body: {login, name: d.name, role: "driver", driver_id: id, password: pw, active: 1, phone: d.phone}});
    modal("Доступ водителя создан", `<div class="note g">Адрес: <b>${location.origin}</b><br>Логин: <b>${H(login)}</b><br>Пароль: <b>${pw}</b></div>`, "sm");
  });
}

/* ---------- кабинет клиента ---------- */
async function pageCabinet() {
  const d = await api("/api/cabinet");
  const b = d.balance;
  $("#root").innerHTML = `<div class="mob" style="max-width:900px"><div class="hd"><img src="/web/logo.png" alt="ЕГМ"><div style="text-align:right"><b>${H(d.client.name)}</b><br><a href="#" id="lo" style="color:#ff8d87;font-size:13px">Выйти</a></div></div>
    <div class="grid g4"><div class="kpi ${b.debt > 0 ? "r" : ""}"><span>К оплате по счетам</span><b>${RUB(b.debt)}</b></div><div class="kpi"><span>Отгружено, счёт ещё не выставлен</span><b>${RUB(b.uninvoiced)}</b></div>
    <div class="kpi"><span>Условия</span><b style="font-size:17px">${H(lbl("pay_terms", d.client.pay_terms))}</b><small>${d.client.delay_days ? "отсрочка " + d.client.delay_days + " дн." : ""}</small></div></div>
    <div class="card mt"><h3>Новая заявка</h3><form id="cf" class="form"><div><label class="req">Материал</label><select class="i" name="material_id" required>${d.materials.map(m => `<option value="${m.id}">${H(m.name)}</option>`).join("")}</select></div>
    <div><label class="req">Количество</label><input class="i" name="qty" type="number" step="any" required></div><div><label>Ед.</label><select class="i" name="unit"><option value="t">т</option><option value="m3">м³</option></select></div>
    <div><label class="req">Дата</label><input class="i" type="date" name="date" value="${addDays(TODAY(), 1)}" required></div><div><label>Время с</label><input class="i" name="time_from" placeholder="08:00"></div><div><label>до</label><input class="i" name="time_to" placeholder="18:00"></div>
    <div class="w2"><label>Объект</label><select class="i" name="site_id">${d.sites.map(s => `<option value="${s.id}">${H(s.name)} — ${H(s.address)}</option>`).join("")}<option value="">+ новый адрес</option></select></div>
    <div class="w2" id="na" style="${d.sites.length ? "display:none" : ""}"><label>Новый адрес доставки</label><input class="i" name="new_address"></div>
    <div class="w2"><label>Контакт на объекте, комментарий</label><input class="i" name="comment"></div><div class="w2" id="cq"></div><div><button class="btn p">Отправить заявку</button></div></form></div>
    <h3 class="mt">Мои заявки</h3>${d.orders.map(o => `<div class="card mb"><div class="row" style="justify-content:space-between"><b>${H(o.number)} · ${D(o.date)}</b>${tag("order_status", o.status)}</div>
    <div class="muted">${H(o.material)} ${R(o.qty)} ${H(lbl("unit", o.unit))} · ${H(o.addr || "")} · ${RUB(o.total)}</div>
    ${o.trips.map(t => `<div class="sm" style="margin-top:6px">🚚 ${H(t.number)} ${H(t.plate || "")} — <b>${H(t.status_t)}</b> ${t.unload_qty ? R(t.unload_qty) + " т" : R(t.plan_qty) + " т план"}
      ${t.tn_number ? ` · <a href="/doc/tn/${t.id}" target="_blank">ТН ${H(t.tn_number)}</a>` : ""}${t.gps ? ` · <a target="_blank" href="https://yandex.ru/maps/?pt=${t.gps.lon},${t.gps.lat}&z=13&l=map">где машина</a>` : ""}</div>`).join("")}</div>`).join("") || `<p class="muted">Заявок пока нет</p>`}
    <h3 class="mt">Счета и документы</h3><div class="tw"><table class="t"><tr><th>Счёт</th><th>Дата</th><th class=n>Сумма</th><th class=n>Оплачено</th><th>Оплатить до</th><th>Статус</th><th></th></tr>
    ${d.invoices.map(i => `<tr><td>${H(i.number)}</td><td>${D(i.date)}</td><td class=n>${RUB(i.total)}</td><td class=n>${RUB(i.paid)}</td><td>${D(i.due_date)}</td><td>${tag("inv_status", i.status)}</td><td><a href="/doc/invoice/${i.id}" target="_blank">счёт</a> · <a href="/doc/upd/${i.id}" target="_blank">УПД</a></td></tr>`).join("")}</table></div>
    <p class="mt"><a class="btn" target="_blank" href="/doc/recon/${ME.client_id}?date_from=${TODAY().slice(0, 4)}-01-01&date_to=${TODAY()}">Акт сверки с начала года</a> ${d.manager_phone ? `<a class="btn" href="tel:${H(d.manager_phone)}">Позвонить менеджеру</a>` : ""}</p></div>`;
  $("#lo").onclick = async e => { e.preventDefault(); await api("/api/logout", {body: {}}); location.reload(); };
  const f = $("#cf");
  f.site_id.onchange = () => $("#na").style.display = f.site_id.value ? "none" : "";
  const q = () => f.qty.value && run(async () => { const r = await api("/api/cabinet/quote", {body: formData(f)}); $("#cq").innerHTML = `<div class="note">Предварительно: материал ${RUB(r.goods)} + доставка ${RUB(r.delivery)} = <b>${RUB(r.total)}</b> (≈ ${r.trips} рейс.). Менеджер подтвердит цену.</div>`; });
  ["qty", "unit", "material_id", "site_id"].forEach(n => f[n].addEventListener("change", q));
  f.onsubmit = e => { e.preventDefault(); run(async () => { await api("/api/cabinet/order", {body: formData(f)}); toast("Заявка отправлена, менеджер подтвердит"); pageCabinet(); }); };
}

/* ---------- приложение водителя ---------- */
async function pageDriver() {
  const d = await api("/api/driver");
  $("#root").innerHTML = `<div class="mob"><div class="hd"><img src="/web/logo.png" alt="ЕГМ"><div style="text-align:right"><b>${H(d.driver)}</b><br><a href="#" id="lo" style="color:#ff8d87;font-size:13px">Выйти</a></div></div>
    <div class="grid" style="grid-template-columns:repeat(3,1fr)"><div class="kpi"><span>Рейсов в месяце</span><b>${d.month.trips}</b></div><div class="kpi"><span>Тонн</span><b>${R(d.month.tons)}</b></div><div class="kpi"><span>Заработано</span><b style="font-size:19px">${RUB(d.month.earned)}</b></div></div>
    ${d.trips.map(t => `<div class="card mt"><div class="row" style="justify-content:space-between"><b style="font-size:17px">${H(t.number)} · ${D(t.date)}</b>${tag("trip_status", t.status)}</div>
      <div class="kv mt"><span>Груз</span><b>${H(t.material)}, ${R(t.load_qty || t.plan_qty)} т</b><span>Погрузка</span><div>${H(t.src || "")}<br><a target="_blank" href="https://yandex.ru/maps/?${t.src_lat ? `rtext=~${t.src_lat},${t.src_lon}` : "text=" + encodeURIComponent(t.src_addr || "")}">${H(t.src_addr || "маршрут")}</a></div>
      <span>Выгрузка</span><div><a target="_blank" href="https://yandex.ru/maps/?${t.dst_lat ? `rtext=~${t.dst_lat},${t.dst_lon}` : "text=" + encodeURIComponent(t.dst || "")}">${H(t.dst || "")}</a></div>
      <span>Приёмщик</span><div>${H(t.contact || "")} ${t.phone ? `<a href="tel:${H(t.phone)}">${H(t.phone)}</a>` : ""}</div><span>Окно</span><div>${H(t.window)}</div>${t.access ? `<span>Подъезд</span><div>${H(t.access)}</div>` : ""}</div>
      ${t.next && t.next !== "closed" ? `<button class="btn p big mt" data-next="${t.id}" data-st="${t.next}">${H({accepted: "✅ Принял рейс", loading: "📍 Приехал на погрузку", loaded: "⚖️ Загружен", on_way: "🚚 Выехал к клиенту", delivered: "🏁 Выгрузился"}[t.next] || t.next_t)}</button>` : ""}
      ${t.status === "assigned" ? `<button class="btn big mt" data-next="${t.id}" data-st="reject">Не могу взять</button>` : ""}
      <div class="row mt"><label class="btn"><input type="file" accept="image/*" capture="environment" data-photo="${t.id}" hidden>📷 Фото накладной${t.photo ? " ✓" : ""}</label>
      ${t.waybill_id ? `<a class="btn" target="_blank" href="/doc/waybill/${t.waybill_id}">Путевой лист</a>` : ""}</div></div>`).join("") || `<div class="card mt"><p class="muted">Активных рейсов нет. Новые рейсы появятся здесь и в Telegram.</p></div>`}
    <h3 class="mt">Выполнено в этом месяце</h3>${d.done.map(x => `<div class="sm">${D(x.date)} · ${H(x.number)} · ${R(x.unload_qty)} т · ${RUB(x.cost_driver)}</div>`).join("") || `<p class="muted sm">—</p>`}
    <p class="sm muted mt">Геопозиция передаётся, пока приложение открыто и есть активный рейс.</p></div>`;
  $("#lo").onclick = async e => { e.preventDefault(); await api("/api/logout", {body: {}}); location.reload(); };
  $$("[data-next]").forEach(b => b.onclick = () => run(async () => {
    let qty = null;
    if (b.dataset.st === "loaded" || b.dataset.st === "delivered") { qty = prompt(b.dataset.st === "loaded" ? "Сколько тонн погрузили?" : "Сколько тонн приняли?"); if (!qty) return; qty = qty.replace(",", "."); }
    await api(`/api/trips/${b.dataset.next}/status`, {body: {status: b.dataset.st, qty}}); toast("Отмечено"); pageDriver();
  }));
  $$("[data-photo]").forEach(i => i.onchange = () => run(async () => { const fd = new FormData(); fd.append("file", i.files[0]); await api(`/api/trips/${i.dataset.photo}/photo`, {body: fd}); toast("Фото сохранено"); pageDriver(); }));
  if (d.trips.length && navigator.geolocation && !window._gps) {
    window._gps = navigator.geolocation.watchPosition(p => { const n = Date.now(); if (n - (window._gpsT || 0) < 60000) return; window._gpsT = n;
      api("/api/gps", {body: {lat: p.coords.latitude, lon: p.coords.longitude, speed: p.coords.speed}}).catch(() => {}); }, () => {}, {enableHighAccuracy: true});
  }
}

/* ---------- маршрутизация ---------- */
async function route() {
  if (!ME) return;
  closeModal();
  if (ME.role === "client") return run(pageCabinet);
  if (ME.role === "driver") return run(pageDriver);
  const [path, qs] = (location.hash.slice(2) || "dashboard").split("?");
  const [p, id] = path.split("/");
  const params = Object.fromEntries(new URLSearchParams(qs || ""));
  if (!allowed(p) && !["orders", "trips", "clients", "invoices", "waybills", "leads"].includes(p)) return pageNotFound();
  const pages = {owner: pageOwner, voice: pageVoice, dashboard: pageDashboard, dispatch: pageDispatch, bank: pageBank, reports: () => pageReports(id), fleet: pageFleet, stock: pageStock,
    import: pageImport, settings: pageSettings, audit: pageAudit};
  const cards = {orders: pageOrder, trips: pageTrip, clients: pageClient, invoices: pageInvoice, waybills: pageWaybill, leads: pageLead};
  await run(async () => {
    if (pages[p]) return pages[p]();
    if (id && cards[p]) return cards[p](+id);
    if (p === "drivers" && id) { await pageList("drivers"); return pageDriverCard(+id); }
    if (ENT(p)) { await pageList(p, params); if (p === "drivers") { /* открыть карточку водителя по клику */ setTimeout(() => $$("#tw tr.cl").forEach(tr => tr.onclick = () => pageDriverCard(+tr.dataset.id)), 600); } return; }
    pageNotFound();
  });
}
async function boot() {
  try {
    const m = await api("/api/me"); ME = m.user; MENU = m.menu; META = await api("/api/meta");
  } catch (e) { return renderLogin(); }
  if (!location.hash && ME.role === "dispatcher") location.hash = "#/dispatch";
  if (!location.hash && ["director", "admin"].includes(ME.role)) location.hash = "#/owner";
  route();
  clearInterval(window._bellT); window._bellT = setInterval(refreshBell, 60000);
}
window.addEventListener("hashchange", route);
boot();
