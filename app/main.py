"""HTTP-сервер ЕГМ: вход, права, API сущностей, действия, документы, Excel, кабинет клиента, водитель, сайт."""
import os, io, json, secrets, datetime, hashlib, hmac, threading, time
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from . import db, logic, docs, schema

app = FastAPI(title="ЕГМ")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST", "GET"], allow_headers=["*"])
WEB = os.path.join(db.BASE, "web")
UPL = os.path.join(db.DATA, "uploads")


# ---------------- вход и права ----------------

def user_of(req: Request):
    tok = req.cookies.get("egm") or req.headers.get("X-Token")
    if not tok:
        return None
    s = db.q1("SELECT * FROM sessions WHERE token=?", (tok,))
    if not s:
        return None
    u = db.get("users", s["user_id"])
    if not u or not u.get("active"):
        return None
    db.ex("UPDATE sessions SET last=? WHERE token=?", (db.now(), tok))
    u.pop("password", None)
    return u


def need(req, roles=None):
    u = user_of(req)
    if not u:
        raise HTTPException(401, "Нужно войти")
    if roles and u["role"] not in roles and u["role"] != "admin":
        raise HTTPException(403, "Нет прав")
    return u


def can(u, ent, write=False):
    e = schema.E.get(ent)
    if not e:
        raise HTTPException(404, "Нет такого раздела")
    roles = e["roles_w"] if write else e["roles_r"]
    if u["role"] == "admin" or u["role"] in roles:
        return
    raise HTTPException(403, f"Нет прав на «{e['title']}»")


@app.exception_handler(ValueError)
async def _ve(req, exc):
    return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/login")
async def login(req: Request):
    d = await req.json()
    u = db.q1("SELECT * FROM users WHERE login=? AND active=1", ((d.get("login") or "").strip().lower(),))
    if not u or not db.check_pw(d.get("password") or "", u["password"]):
        time.sleep(0.5)
        raise HTTPException(401, "Неверный логин или пароль")
    tok = secrets.token_urlsafe(24)
    db.ex("INSERT INTO sessions(token,user_id,created,last) VALUES(?,?,?,?)", (tok, u["id"], db.now(), db.now()))
    db.audit(u["id"], "login", "users", u["id"], {})
    r = JSONResponse({"ok": True, "role": u["role"]})
    r.set_cookie("egm", tok, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return r


@app.post("/api/logout")
async def logout(req: Request):
    tok = req.cookies.get("egm")
    if tok:
        db.ex("DELETE FROM sessions WHERE token=?", (tok,))
    r = JSONResponse({"ok": True})
    r.delete_cookie("egm")
    return r


@app.get("/api/me")
def me(req: Request):
    u = need(req)
    menu = [k for k, e in schema.E.items() if not e["hidden"] and (u["role"] == "admin" or u["role"] in e["roles_r"])]
    return {"user": u, "menu": menu, "company": db.setting("company_name", "ООО «ЕГМ»")}


@app.get("/api/meta")
def meta(req: Request):
    need(req)
    return schema.meta_public()


# ---------------- общий CRUD ----------------

def ref_titles(ent, ids):
    e = schema.E[ent]
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    tf = e["title_field"]
    return {r["id"]: r["t"] for r in db.q(f'SELECT id, "{tf}" t FROM {ent} WHERE id IN ({",".join("?" * len(ids))})', ids)}


def decorate(ent, rows):
    """Подставляет названия связанных записей: client_id -> client_id__t."""
    for f in schema.E[ent]["fields"]:
        if f["type"].startswith("ref:"):
            m = ref_titles(f["type"][4:], [r.get(f["name"]) for r in rows])
            for r in rows:
                r[f["name"] + "__t"] = m.get(r.get(f["name"]), "")
    for r in rows:
        r.pop("password", None)
    return rows


@app.get("/api/e/{ent}")
def list_(ent: str, req: Request, q: str = "", limit: int = 500, offset: int = 0):
    u = need(req)
    can(u, ent)
    e = schema.E[ent]
    where, args = [], []
    names = {f["name"]: f for f in e["fields"]}
    for k, v in req.query_params.items():
        if k in names and v != "":
            where.append(f'"{k}"=?')
            args.append(v)
        elif k.endswith("__from") and k[:-6] in names:
            where.append(f'"{k[:-6]}">=?'); args.append(v)
        elif k.endswith("__to") and k[:-4] in names:
            where.append(f'"{k[:-4]}"<=?'); args.append(v)
        elif k.endswith("__in") and k[:-4] in names:
            vs = v.split(",")
            where.append(f'"{k[:-4]}" IN ({",".join("?" * len(vs))})'); args += vs
    if q:
        txt = [f["name"] for f in e["fields"] if f["type"] in ("s", "t", "ph")]
        where.append("(" + " OR ".join(f'"{n}" LIKE ?' for n in txt) + ")")
        args += [f"%{q}%"] * len(txt)
    sql = f"SELECT * FROM {ent}" + (" WHERE " + " AND ".join(where) if where else "")
    total = db.val(f"SELECT COUNT(*) FROM ({sql})", args)
    rows = db.q(sql + f" ORDER BY {e['order']} LIMIT ? OFFSET ?", args + [min(limit, 5000), offset])
    return {"rows": decorate(ent, rows), "total": total}


@app.get("/api/e/{ent}/{id_}")
def get_(ent: str, id_: int, req: Request):
    u = need(req)
    can(u, ent)
    r = db.get(ent, id_)
    if not r:
        raise HTTPException(404, "Не найдено")
    out = decorate(ent, [r])[0]
    out["_activity"] = db.q("SELECT a.*, u.name uname FROM activities a LEFT JOIN users u ON u.id=a.user_id WHERE entity=? AND entity_id=? ORDER BY id DESC LIMIT 100", (ent, id_))
    out["_audit"] = db.q("SELECT a.ts, a.action, a.data, u.name uname FROM audit a LEFT JOIN users u ON u.id=a.user_id WHERE entity=? AND entity_id=? ORDER BY a.id DESC LIMIT 50", (ent, id_))
    return out


@app.get("/api/refs/{ent}")
def refs(ent: str, req: Request, q: str = ""):
    need(req)
    e = schema.E[ent]
    tf = e["title_field"]
    extra = {"sites": ", client_id", "drivers": ", vehicle_id", "vehicles": ", capacity_t, owner", "materials": ", unit, base_price"}.get(ent, "")
    sql = f'SELECT id, "{tf}" t{extra} FROM {ent}'
    a = []
    if q:
        sql += f' WHERE "{tf}" LIKE ?'
        a.append(f"%{q}%")
    return db.q(sql + f' ORDER BY "{tf}" LIMIT 3000', a)


SPECIAL_CREATE = {"orders": logic.create_order}


@app.post("/api/e/{ent}")
async def create(ent: str, req: Request):
    u = need(req)
    can(u, ent, True)
    d = await req.json()
    if ent in SPECIAL_CREATE:
        id_ = SPECIAL_CREATE[ent](d, u)
    else:
        data = db.clean(ent, d)
        if ent == "users":
            data["login"] = data["login"].lower()
            if db.q1("SELECT id FROM users WHERE login=?", (data["login"],)):
                raise ValueError("Такой логин уже есть")
            data["password"] = db.hash_pw(d.get("password") or secrets.token_urlsafe(6))
            data.setdefault("active", 1)
        if ent == "drivers":
            data["link_code"] = "d" + secrets.token_hex(3)
        id_ = db.insert(ent, data, u["id"])
        after_save(ent, id_, u, created=True)
    return {"id": id_}


@app.put("/api/e/{ent}/{id_}")
async def save(ent: str, id_: int, req: Request):
    u = need(req)
    can(u, ent, True)
    d = await req.json()
    if ent == "orders":
        logic.update_order(id_, d, u)
        return {"ok": True}
    data = db.clean(ent, d, partial=True)
    if ent == "users":
        if d.get("password"):
            data["password"] = db.hash_pw(d["password"])
        if "login" in data and data["login"]:
            data["login"] = data["login"].lower()
    db.update(ent, id_, data, u["id"])
    if ent == "users" and "password" in data:
        db.ex("UPDATE users SET password=? WHERE id=?", (data["password"], id_))
    after_save(ent, id_, u)
    return {"ok": True}


def after_save(ent, id_, u, created=False):
    if ent == "payments":
        logic.apply_payment(id_)
    if ent == "purchases":
        p = db.get("purchases", id_)
        db.update("purchases", id_, {"total": round((p["qty"] or 0) * (p["price"] or 0), 2)})
        logic.purchase_to_stock(id_, u)
    if ent == "payroll":
        logic.payroll_total(id_)
    if ent == "trips":
        t = db.get("trips", id_)
        if t["status"] == "closed":
            logic.calc_trip(id_)
        logic.recalc_order_status(t["order_id"])
    if ent == "leads":
        l = db.get("leads", id_)
        if created and l.get("manager_id"):
            logic.notify(f"Новый лид: {l['name']}", user_id=l["manager_id"], link=f"#/leads/{id_}", kind="lead")
        if not l.get("created_at"):
            db.update("leads", id_, {"created_at": db.now()})


@app.delete("/api/e/{ent}/{id_}")
def remove(ent: str, id_: int, req: Request):
    u = need(req)
    can(u, ent, True)
    if ent == "orders" and db.q1("SELECT id FROM trips WHERE order_id=? AND status NOT IN ('plan','canceled')", (id_,)):
        raise ValueError("По заявке есть рейсы в работе — отмените заявку вместо удаления")
    if ent == "trips" and (db.get("trips", id_) or {}).get("invoice_id"):
        raise ValueError("Рейс уже в счёте — удалить нельзя")
    db.delete(ent, id_, u["id"])
    return {"ok": True}


@app.post("/api/activity/{ent}/{id_}")
async def add_activity(ent: str, id_: int, req: Request):
    u = need(req)
    d = await req.json()
    db.ex("INSERT INTO activities(ts,user_id,entity,entity_id,kind,text) VALUES(?,?,?,?,?,?)",
          (db.now(), u["id"], ent, id_, d.get("kind") or "note", d.get("text") or ""))
    return {"ok": True}


# ---------------- действия ----------------

@app.post("/api/quote")
async def quote(req: Request):
    need(req)
    d = await req.json()
    return logic.quote(int(d["client_id"]) if d.get("client_id") else None, int(d["site_id"]) if d.get("site_id") else None,
                       int(d["material_id"]), float(d.get("qty") or 0), d.get("unit") or "t")


@app.post("/api/orders/{id_}/plan")
async def plan(id_: int, req: Request):
    u = need(req, ["dispatcher", "director", "manager"])
    d = await req.json() if (await req.body()) else {}
    return {"trips": logic.plan_trips(id_, u, float(d["capacity"]) if d.get("capacity") else None)}


@app.post("/api/orders/{id_}/status")
async def order_status(id_: int, req: Request):
    u = need(req, ["dispatcher", "director", "manager"])
    st = (await req.json())["status"]
    logic.update_order(id_, {"status": st}, u)
    if st == "canceled":
        for t in db.q("SELECT id FROM trips WHERE order_id=? AND status IN ('plan','assigned','accepted')", (id_,)):
            db.update("trips", t["id"], {"status": "canceled"}, u["id"])
    return {"ok": True}


@app.get("/api/dispatch")
def dispatch(req: Request, date: str = ""):
    need(req, ["dispatcher", "director", "manager", "mechanic"])
    d = date or db.today()
    trips = db.q("""SELECT t.*, o.number onum, o.time_from, o.time_to, o.client_id, c.name client, m.name material, s.address addr, s.name site,
                    v.plate, dr.name driver, sp.name supplier FROM trips t JOIN orders o ON o.id=t.order_id LEFT JOIN clients c ON c.id=o.client_id
                    LEFT JOIN materials m ON m.id=o.material_id LEFT JOIN sites s ON s.id=o.site_id LEFT JOIN vehicles v ON v.id=t.vehicle_id
                    LEFT JOIN drivers dr ON dr.id=t.driver_id LEFT JOIN suppliers sp ON sp.id=t.supplier_id
                    WHERE (t.date=? OR (t.date<? AND t.status NOT IN ('closed','canceled'))) AND t.status!='canceled' ORDER BY o.time_from, t.id""", (d, d))
    vehicles = db.q("""SELECT v.*, d.id driver_id, d.name driver, d.phone driver_phone, d.tg_chat FROM vehicles v LEFT JOIN drivers d ON d.vehicle_id=v.id AND (d.status='work' OR d.status IS NULL)
                       WHERE v.status!='off' OR v.status IS NULL ORDER BY v.owner, v.plate""")
    pos = {r["vehicle_id"]: r for r in db.q("SELECT g.* FROM gps_points g JOIN (SELECT vehicle_id, MAX(id) mid FROM gps_points GROUP BY vehicle_id) x ON x.mid=g.id")}
    for v in vehicles:
        v["gps"] = pos.get(v["id"])
    orders = db.q("""SELECT o.*, c.name client, m.name material, s.address addr FROM orders o LEFT JOIN clients c ON c.id=o.client_id
                     LEFT JOIN materials m ON m.id=o.material_id LEFT JOIN sites s ON s.id=o.site_id WHERE o.status IN ('new','confirmed') AND o.date<=? ORDER BY o.date, o.time_from""",
                  ((datetime.date.fromisoformat(d) + datetime.timedelta(days=1)).isoformat(),))
    drivers = db.q("SELECT id, name, vehicle_id, status FROM drivers WHERE status='work' OR status IS NULL ORDER BY name")
    return {"date": d, "trips": trips, "vehicles": vehicles, "orders": orders, "drivers": drivers}


@app.post("/api/trips/{id_}/assign")
async def assign(id_: int, req: Request):
    u = need(req, ["dispatcher", "director"])
    d = await req.json()
    return logic.assign_trip(id_, int(d["vehicle_id"]) if d.get("vehicle_id") else None, int(d["driver_id"]) if d.get("driver_id") else None,
                             u, bool(d.get("force")))


@app.post("/api/trips/{id_}/status")
async def trip_status(id_: int, req: Request):
    u = need(req, ["dispatcher", "director", "driver"])
    d = await req.json()
    if u["role"] == "driver":
        t = db.get("trips", id_)
        if t.get("driver_id") != u.get("driver_id"):
            raise HTTPException(403, "Это не ваш рейс")
    logic.set_trip_status(id_, d["status"], u, float(d["qty"]) if d.get("qty") not in (None, "") else None, by_driver=u["role"] == "driver")
    return {"ok": True}


@app.post("/api/trips/{id_}/photo")
async def trip_photo(id_: int, req: Request, file: UploadFile = File(...)):
    u = need(req, ["dispatcher", "director", "driver"])
    os.makedirs(UPL, exist_ok=True)
    ext = os.path.splitext(file.filename or "x.jpg")[1][:5] or ".jpg"
    fn = f"trip{id_}_{int(time.time())}{ext}"
    with open(os.path.join(UPL, fn), "wb") as f:
        f.write(await file.read())
    db.update("trips", id_, {"photo": fn}, u["id"])
    return {"ok": True, "file": fn}


@app.get("/files/{fn}")
def files(fn: str, req: Request):
    need(req)
    p = os.path.join(UPL, os.path.basename(fn))
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/api/waybills/{id_}/close")
async def wb_close(id_: int, req: Request):
    u = need(req, ["dispatcher", "director", "mechanic"])
    logic.close_waybill(id_, await req.json(), u)
    return {"ok": True}


@app.post("/api/invoices/build")
async def inv_build(req: Request):
    u = need(req, ["accountant", "director"])
    d = await req.json()
    ids = [int(d["client_id"])] if d.get("client_id") else [r["cid"] for r in db.q(
        "SELECT DISTINCT o.client_id cid FROM trips t JOIN orders o ON o.id=t.order_id WHERE t.status='closed' AND t.invoice_id IS NULL AND t.date BETWEEN ? AND ?",
        (d["date_from"], d["date_to"]))]
    made, errs = [], []
    for cid in ids:
        try:
            made.append(logic.build_invoice(cid, d["date_from"], d["date_to"], u, d.get("contract_id")))
        except ValueError as ex:
            errs.append(f"{logic.name_of('clients', cid)}: {ex}")
    return {"invoices": made, "errors": errs}


@app.post("/api/payroll/build")
async def pr_build(req: Request):
    u = need(req, ["accountant", "director"])
    d = await req.json()
    ids = [int(d["driver_id"])] if d.get("driver_id") else [r["id"] for r in db.q("SELECT id FROM drivers WHERE status!='fired' OR status IS NULL")]
    return {"payroll": [logic.calc_payroll(i, d["date_from"], d["date_to"], u) for i in ids]}


@app.post("/api/bank/import")
async def bank_import(req: Request, file: UploadFile = File(...)):
    u = need(req, ["accountant", "director"])
    raw = await file.read()
    for enc in ("cp1251", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return logic.import_bank(text, u)


@app.get("/api/dashboard")
def dashboard(req: Request, date: str = ""):
    need(req, ["director", "dispatcher", "manager", "accountant", "mechanic"])
    return logic.dashboard(date or None)


@app.get("/api/report/{kind}")
def report(kind: str, req: Request, date_from: str, date_to: str):
    need(req, ["director", "accountant", "dispatcher", "manager"])
    if kind == "aging":
        return logic.aging()
    if kind == "fuel":
        return logic.fuel_report(date_from, date_to)
    if kind == "stock":
        return logic.stock()
    if kind == "fleet":
        return logic.fleet_alerts(60)
    return logic.report(kind, date_from, date_to)


@app.get("/api/balance/{client_id}")
def balance(client_id: int, req: Request):
    need(req, ["director", "accountant", "manager", "dispatcher"])
    return {**logic.client_balance(client_id), "overdue": logic.overdue(client_id)}


@app.get("/api/notifications")
def notifs(req: Request):
    u = need(req)
    rows = db.q("SELECT * FROM notifications WHERE (user_id=? OR role=? OR (? IN ('admin','director') AND role IS NOT NULL)) ORDER BY id DESC LIMIT 60",
                (u["id"], u["role"], u["role"]))
    return {"rows": rows, "unread": sum(1 for r in rows if not r["read"])}


@app.post("/api/notifications/read")
def notifs_read(req: Request):
    u = need(req)
    db.ex("UPDATE notifications SET read=1 WHERE user_id=? OR role=? OR ?='admin' OR ?='director'", (u["id"], u["role"], u["role"], u["role"]))
    return {"ok": True}


@app.get("/api/audit")
def audit(req: Request, limit: int = 300):
    need(req, ["director"])
    return db.q("SELECT a.*, u.name uname FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT ?", (limit,))


@app.get("/api/settings")
def settings(req: Request):
    need(req, ["director"])
    rows = {r["key"]: r["value"] for r in db.q("SELECT * FROM settings")}
    if rows.get("tg_token"):
        rows["tg_token"] = "••••" + rows["tg_token"][-4:]
    return rows


@app.post("/api/settings")
async def settings_save(req: Request):
    u = need(req, ["director"])
    d = await req.json()
    for k, v in d.items():
        if k == "tg_token" and str(v).startswith("••••"):
            continue
        db.set_setting(k, v)
    db.audit(u["id"], "settings", "settings", 0, {k: ("***" if "token" in k else v) for k, v in d.items()})
    return {"ok": True}


@app.post("/api/backup")
def backup_now(req: Request):
    need(req, ["director"])
    return {"file": os.path.basename(db.backup("manual"))}


@app.get("/api/backup/download")
def backup_dl(req: Request):
    need(req, ["director"])
    fn = db.backup("download")
    return FileResponse(fn, filename=os.path.basename(fn))


@app.get("/api/link/{kind}/{id_}")
def link_code(kind: str, id_: int, req: Request):
    need(req, ["dispatcher", "director", "manager"])
    bot = db.setting("tg_bot_username", "")
    code = bot_code(kind, id_)
    return {"code": code, "url": f"https://t.me/{bot}?start={code}" if bot else "", "bot": bot}


def bot_code(kind, id_):
    sec = db.setting("secret") or ""
    h = hmac.new(sec.encode(), f"{kind}{id_}".encode(), hashlib.sha256).hexdigest()[:6]
    return f"{kind}{id_}_{h}"


# ---------------- документы ----------------

@app.get("/doc/{kind}/{id_}", response_class=HTMLResponse)
def doc(kind: str, id_: int, req: Request, date_from: str = "", date_to: str = ""):
    u = need(req)
    if u["role"] == "client":
        cid = u.get("client_id")
        own = {"tn": lambda: db.get("orders", (db.get("trips", id_) or {}).get("order_id"))["client_id"],
               "invoice": lambda: db.get("invoices", id_)["client_id"], "upd": lambda: db.get("invoices", id_)["client_id"],
               "recon": lambda: id_}.get(kind)
        if not own or own() != cid:
            raise HTTPException(403)
    elif u["role"] == "driver" and kind not in ("tn", "waybill"):
        raise HTTPException(403)
    if kind == "tn":
        return docs.tn(id_)
    if kind == "waybill":
        return docs.waybill(id_)
    if kind in ("invoice", "upd"):
        return docs.invoice(id_, kind)
    if kind == "recon":
        return docs.recon(id_, date_from or db.today()[:4] + "-01-01", date_to or db.today())
    if kind == "payroll":
        need(req, ["accountant", "director"])
        return docs.payroll_sheet(id_)
    if kind == "document":
        d = db.get("documents", id_)
        target = {"tn": ("tn", d.get("trip_id")), "waybill": ("waybill", d.get("waybill_id")), "invoice": ("invoice", d.get("invoice_id")),
                  "upd": ("upd", d.get("invoice_id")), "act": ("upd", d.get("invoice_id"))}.get(d["kind"])
        if target and target[1]:
            return RedirectResponse(f"/doc/{target[0]}/{target[1]}")
    raise HTTPException(404, "Документ не найден")


# ---------------- Excel ----------------

@app.get("/api/export/{ent}.xlsx")
def export_xlsx(ent: str, req: Request, template: int = 0):
    u = need(req)
    can(u, ent)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    e = schema.E[ent]
    fl = [f for f in e["fields"] if f["type"] != "pw" and "hide" not in f["opt"]]
    wb = Workbook()
    ws = wb.active
    ws.title = e["title"][:30]
    ws.append(["ID"] + [f["label"] for f in fl])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="E3120B")
    if not template:
        rows = decorate(ent, db.q(f"SELECT * FROM {ent} ORDER BY {e['order']}"))
        for r in rows:
            out = [r["id"]]
            for f in fl:
                v = r.get(f["name"])
                if f["type"].startswith("ref:"):
                    v = r.get(f["name"] + "__t")
                elif f["type"].startswith("enum:"):
                    v = logic.LBL[f["type"][5:]].get(v, v)
                elif f["type"] == "b":
                    v = "да" if v else ""
                out.append(v)
            ws.append(out)
    for i, f in enumerate(["ID"] + fl, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = 12 if i == 1 else min(40, max(12, len(f["label"]) + 4))
    ws.freeze_panes = "A2"
    bio = io.BytesIO()
    wb.save(bio)
    name = f"egm_{ent}_{db.today()}.xlsx"
    return Response(bio.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/import/{ent}")
async def import_xlsx(ent: str, req: Request, file: UploadFile = File(...), dry: str = Form("0")):
    u = need(req)
    can(u, ent, True)
    from openpyxl import load_workbook
    e = schema.E[ent]
    wb = load_workbook(io.BytesIO(await file.read()), data_only=True, read_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    head = [str(h or "").strip().lower() for h in next(it)]
    by = {}
    for f in e["fields"]:
        for i, h in enumerate(head):
            if h and (h == f["label"].lower() or h == f["name"].lower() or h.split(",")[0] == f["label"].lower().split(",")[0]):
                by.setdefault(f["name"], i)
    idcol = head.index("id") if "id" in head else None
    if not by:
        raise ValueError("Не нашёл ни одной знакомой колонки. Скачайте шаблон и заполните его.")
    res = {"added": 0, "updated": 0, "errors": [], "columns": [schema_label(ent, k) for k in by]}
    refcache = {}
    for n, row in enumerate(it, 2):
        if not row or all(v in (None, "") for v in row):
            continue
        d = {}
        try:
            for k, i in by.items():
                if i >= len(row):
                    continue
                v = row[i]
                f = next(f for f in e["fields"] if f["name"] == k)
                if isinstance(v, (datetime.date, datetime.datetime)):
                    v = v.strftime("%Y-%m-%d")
                if f["type"].startswith("ref:") and v not in (None, ""):
                    r_ent = f["type"][4:]
                    key = (r_ent, str(v).strip().lower())
                    if key not in refcache:
                        tf = schema.E[r_ent]["title_field"]
                        rr = db.q1(f'SELECT id FROM {r_ent} WHERE LOWER("{tf}")=? OR id=?', (key[1], v if str(v).isdigit() else -1))
                        refcache[key] = rr and rr["id"]
                    if not refcache[key]:
                        raise ValueError(f"«{f['label']}»: не найдено «{v}»")
                    v = refcache[key]
                if f["type"] == "d" and isinstance(v, str) and len(v) == 10 and v[2] == ".":
                    v = f"{v[6:]}-{v[3:5]}-{v[:2]}"
                d[k] = v
            rid = row[idcol] if idcol is not None and idcol < len(row) else None
            if dry == "1":
                db.clean(ent, d, partial=bool(rid))
                res["added" if not rid else "updated"] += 1
                continue
            if rid and db.get(ent, int(rid)):
                db.update(ent, int(rid), db.clean(ent, d, partial=True), u["id"])
                res["updated"] += 1
            else:
                if ent == "orders":
                    d.setdefault("source", "import")
                    logic.create_order(d, u)
                else:
                    data = db.clean(ent, d)
                    if ent == "drivers":
                        data["link_code"] = "d" + secrets.token_hex(3)
                    db.insert(ent, data, u["id"])
                res["added"] += 1
        except (ValueError, StopIteration) as ex:
            res["errors"].append(f"строка {n}: {ex}")
    return res


def schema_label(ent, name):
    return next(f["label"] for f in schema.E[ent]["fields"] if f["name"] == name)


# ---------------- кабинет клиента ----------------

def client_user(req):
    u = need(req, ["client"])
    if not u.get("client_id"):
        raise HTTPException(403, "Учётка не привязана к клиенту")
    return u


@app.get("/api/cabinet")
def cabinet(req: Request):
    u = client_user(req)
    cid = u["client_id"]
    c = db.get("clients", cid)
    orders = db.q("""SELECT o.*, m.name material, s.address addr FROM orders o LEFT JOIN materials m ON m.id=o.material_id LEFT JOIN sites s ON s.id=o.site_id
                     WHERE o.client_id=? ORDER BY o.date DESC, o.id DESC LIMIT 200""", (cid,))
    for o in orders:
        o["trips"] = db.q("""SELECT t.id, t.number, t.status, t.plan_qty, t.unload_qty, t.tn_number, t.ts_delivered, v.plate FROM trips t LEFT JOIN vehicles v ON v.id=t.vehicle_id
                             WHERE t.order_id=? AND t.status!='canceled' ORDER BY t.id""", (o["id"],))
        for t in o["trips"]:
            t["status_t"] = logic.LBL["trip_status"].get(t["status"])
            if t["status"] in ("on_way", "loaded"):
                g = db.q1("SELECT lat, lon, ts FROM gps_points WHERE vehicle_id=(SELECT vehicle_id FROM trips WHERE id=?) ORDER BY id DESC", (t["id"],))
                t["gps"] = g
    return {"client": {k: c.get(k) for k in ("name", "inn", "pay_terms", "delay_days", "credit_limit")},
            "balance": logic.client_balance(cid),
            "invoices": db.q("SELECT id, number, date, total, paid, due_date, status FROM invoices WHERE client_id=? ORDER BY date DESC", (cid,)),
            "sites": db.q("SELECT id, name, address FROM sites WHERE client_id=?", (cid,)),
            "materials": db.q("SELECT id, name, unit FROM materials WHERE active=1 ORDER BY name"),
            "orders": orders, "manager_phone": db.setting("company_phone", "")}


@app.post("/api/cabinet/order")
async def cabinet_order(req: Request):
    u = client_user(req)
    d = await req.json()
    d["client_id"] = u["client_id"]
    d["source"] = "cabinet"
    d["status"] = "new"
    site = db.get("sites", int(d.get("site_id") or 0))
    if not site or site["client_id"] != u["client_id"]:
        if d.get("new_address"):
            d["site_id"] = db.insert("sites", dict(client_id=u["client_id"], name=d["new_address"][:40], address=d["new_address"]), u["id"])
        else:
            raise ValueError("Выберите объект или укажите адрес")
    for k in ("price", "delivery"):
        d.pop(k, None)
    return {"id": logic.create_order(d, u)}


@app.post("/api/cabinet/quote")
async def cabinet_quote(req: Request):
    u = client_user(req)
    d = await req.json()
    return logic.quote(u["client_id"], int(d["site_id"]) if d.get("site_id") else None, int(d["material_id"]), float(d.get("qty") or 0), d.get("unit") or "t")


# ---------------- водитель ----------------

@app.get("/api/driver")
def driver_home(req: Request):
    u = need(req, ["driver"])
    did = u.get("driver_id")
    if not did:
        raise HTTPException(403, "Учётка не привязана к водителю")
    trips = db.q("SELECT id FROM trips WHERE driver_id=? AND status NOT IN ('closed','canceled','plan') ORDER BY date, id", (did,))
    out = []
    for r in trips:
        t, o, site, src = logic.trip_card(r["id"])
        out.append(dict(id=t["id"], number=t["number"], date=t["date"], status=t["status"], status_t=logic.LBL["trip_status"][t["status"]],
                        next=logic.NEXT.get(t["status"]), next_t=logic.LBL["trip_status"].get(logic.NEXT.get(t["status"], ""), ""),
                        plan_qty=t["plan_qty"], load_qty=t.get("load_qty"), material=logic.name_of("materials", o.get("material_id")),
                        src=src.get("name"), src_addr=src.get("address"), src_lat=src.get("lat"), src_lon=src.get("lon"),
                        dst=site.get("address"), dst_lat=site.get("lat"), dst_lon=site.get("lon"), contact=site.get("contact") or o.get("contact"),
                        phone=site.get("phone"), access=site.get("access"), window=f"{o.get('time_from') or ''}–{o.get('time_to') or ''}",
                        waybill_id=t.get("waybill_id"), photo=t.get("photo")))
    done = db.q("SELECT number, date, unload_qty, cost_driver FROM trips WHERE driver_id=? AND status='closed' AND date>=? ORDER BY date DESC",
                (did, db.today()[:8] + "01"))
    return {"driver": db.get("drivers", did)["name"], "trips": out, "month": {"trips": len(done), "tons": round(sum(x["unload_qty"] or 0 for x in done), 1),
                                                                               "earned": round(sum(x["cost_driver"] or 0 for x in done))}, "done": done[:20]}


@app.post("/api/gps")
async def gps(req: Request):
    """Точка от телефона водителя (браузер) или от внешнего трекера (заголовок X-GPS-Key)."""
    d = await req.json()
    key = req.headers.get("X-GPS-Key")
    if key and key == db.setting("gps_key"):
        v = db.q1("SELECT id FROM vehicles WHERE glonass_id=? OR plate=?", (str(d.get("device")), str(d.get("device"))))
        if not v:
            raise HTTPException(404, "Машина не найдена")
        vid, did, src = v["id"], None, "tracker"
    else:
        u = need(req, ["driver"])
        did = u["driver_id"]
        t = db.q1("SELECT vehicle_id FROM trips WHERE driver_id=? AND status NOT IN ('closed','canceled','plan') ORDER BY id DESC", (did,))
        vid = (t or {}).get("vehicle_id") or (db.get("drivers", did) or {}).get("vehicle_id")
        src = "phone"
    db.ex("INSERT INTO gps_points(vehicle_id,driver_id,ts,lat,lon,speed,source) VALUES(?,?,?,?,?,?,?)",
          (vid, did, db.now(), float(d["lat"]), float(d["lon"]), d.get("speed"), src))
    return {"ok": True}


# ---------------- сайт (публично) ----------------

_rate = {}


@app.post("/api/public/lead")
async def public_lead(req: Request):
    ip = req.client.host if req.client else "?"
    now = time.time()
    _rate[ip] = [t for t in _rate.get(ip, []) if now - t < 600] + [now]
    if len(_rate[ip]) > 5:
        raise HTTPException(429, "Слишком много заявок, позвоните нам")
    ct = req.headers.get("content-type", "")
    d = await req.json() if "json" in ct else dict(await req.form())
    if d.get("website"):
        return {"ok": True}
    name, phone = (d.get("name") or "").strip()[:80], (d.get("phone") or "").strip()[:30]
    if len("".join(ch for ch in phone if ch.isdigit())) < 10:
        raise ValueError("Укажите телефон")
    mgr = db.q1("SELECT id FROM users WHERE role='manager' AND active=1 ORDER BY id")
    lid = db.insert("leads", dict(name=name or "Без имени", phone=phone, source="site", stage="new", material=(d.get("material") or "")[:80],
                                  qty=(d.get("qty") or "")[:40], address=(d.get("address") or "")[:200], note=(d.get("comment") or "")[:1000],
                                  manager_id=mgr and mgr["id"], created_at=db.now(), next_date=db.today()))
    logic.notify(f"Заявка с сайта: {name} {phone} — {d.get('material') or ''}", role="manager", link=f"#/leads/{lid}", kind="lead")
    return {"ok": True}


@app.get("/api/public/materials")
def public_materials():
    return db.q("SELECT id, name, unit FROM materials WHERE active=1 AND (is_service=0 OR is_service IS NULL) ORDER BY name")


# ---------------- статика ----------------

@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
        return f.read()


@app.get("/web/{fn}")
def web_static(fn: str):
    p = os.path.join(WEB, os.path.basename(fn))
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health():
    return {"ok": True, "db": os.path.basename(db.DB_PATH), "ts": db.now()}


# ---------------- фоновые задачи ----------------

def _cron():
    last_day = None
    while True:
        try:
            d = db.today()
            if d != last_day:
                last_day = d
                db.backup("daily")
                logic.fleet_checks()
                for i in logic.overdue():
                    txt = f"Просрочен счёт {i['number']} ({logic.name_of('clients', i['client_id'])}): {i['total'] - (i['paid'] or 0):,.0f} ₽".replace(",", " ")
                    if not db.q1("SELECT id FROM notifications WHERE text=? AND ts>=?", (txt, d)):
                        logic.notify(txt, role="accountant", link=f"#/invoices/{i['id']}", kind="debt")
                for l in db.q("SELECT * FROM leads WHERE next_date<=? AND stage NOT IN ('won','lost')", (d,)):
                    txt = f"Перезвонить: {l['name']} {l.get('phone') or ''}"
                    if not db.q1("SELECT id FROM notifications WHERE text=? AND ts>=?", (txt, d)):
                        logic.notify(txt, user_id=l.get("manager_id"), role=None if l.get("manager_id") else "manager", link=f"#/leads/{l['id']}", kind="lead")
        except Exception as ex:
            print("cron error:", ex)
        time.sleep(300)


@app.on_event("startup")
def _startup():
    db.conn()
    if not db.setting("secret"):
        db.set_setting("secret", secrets.token_hex(16))
    if not db.setting("gps_key"):
        db.set_setting("gps_key", secrets.token_hex(12))
    if not db.q1("SELECT id FROM users LIMIT 1"):
        pw = secrets.token_urlsafe(8)
        db.insert("users", {"login": "admin", "name": "Администратор", "role": "admin", "password": db.hash_pw(pw), "active": 1})
        with open(os.path.join(db.DATA, "FIRST_LOGIN.txt"), "w", encoding="utf-8") as f:
            f.write(f"Первый вход в систему ЕГМ\nАдрес: http://localhost:8000\nЛогин: admin\nПароль: {pw}\n\n"
                    "Сразу смените пароль (Настройки → Пользователи) и удалите этот файл.\n")
        print("Создан пользователь admin, пароль в data/FIRST_LOGIN.txt")
    threading.Thread(target=_cron, daemon=True).start()
    from . import bot
    threading.Thread(target=bot.run, daemon=True).start()
