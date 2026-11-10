"""Бизнес-логика ЕГМ: заявки -> рейсы -> путевые листы -> документы -> счета -> оплаты -> зарплата."""
import datetime, json, math, re
from . import db
from .schema import ENUMS

LBL = {k: dict(v) for k, v in ENUMS.items()}


def S(key, default):
    v = db.setting(key)
    try:
        return type(default)(v) if v is not None else default
    except ValueError:
        return default


def notify(text, role=None, user_id=None, link="", kind="info"):
    db.ex("INSERT INTO notifications(ts,role,user_id,text,link,kind) VALUES(?,?,?,?,?,?)",
          (db.now(), role, user_id, text, link, kind))


def outbox(chat, text, buttons=None, channel="tg"):
    if not chat:
        return
    db.ex("INSERT INTO outbox(ts,channel,chat,text,buttons) VALUES(?,?,?,?,?)",
          (db.now(), channel, str(chat), text, json.dumps(buttons or [], ensure_ascii=False)))


def name_of(ent, id_, field="name"):
    if not id_:
        return ""
    r = db.get(ent, id_)
    return (r or {}).get(field) or ""


# ---------------- цены ----------------

def material_price(client_id, material_id):
    r = db.q1("SELECT price FROM client_prices WHERE client_id=? AND material_id=? AND (valid_to IS NULL OR valid_to>=?) ORDER BY id DESC",
              (client_id, material_id, db.today()))
    if r:
        return r["price"], "индивидуальная"
    m = db.get("materials", material_id) or {}
    price = m.get("base_price") or 0
    c = db.get("clients", client_id) or {}
    if c.get("discount_pct"):
        price = round(price * (1 - c["discount_pct"] / 100), 2)
        return price, f"базовая − {c['discount_pct']}%"
    return price, "базовая"


def site_distance(site):
    return (site or {}).get("distance_km") or S("default_distance_km", 40.0)


def delivery_price(site, trips):
    if site and site.get("zone_id"):
        z = db.get("zones", site["zone_id"]) or {}
    else:
        d = site_distance(site)
        z = db.q1("SELECT * FROM zones WHERE (km_from IS NULL OR km_from<=?) AND (km_to IS NULL OR km_to>?) ORDER BY km_from DESC", (d, d)) or {}
    per = (z.get("trip_price") or 0) + (z.get("km_price") or 0) * site_distance(site)
    return round(per * trips, 2), z.get("name") or "—"


def best_supplier(material_id):
    r = db.q1("""SELECT sp.supplier_id, sp.price FROM supplier_prices sp WHERE sp.material_id=?
                 ORDER BY sp.valid_from DESC, sp.price ASC LIMIT 1""", (material_id,))
    return r


def supplier_price(supplier_id, material_id):
    r = db.q1("SELECT price FROM supplier_prices WHERE supplier_id=? AND material_id=? ORDER BY valid_from DESC, id DESC",
              (supplier_id, material_id))
    return (r or {}).get("price") or 0


def to_tons(qty, unit, material):
    if unit == "m3":
        return round(qty * ((material or {}).get("density") or 1.5), 2)
    return qty


def quote(client_id, site_id, material_id, qty, unit="t"):
    """Расчёт цены заявки (используется формой, калькулятором и кабинетом)."""
    m = db.get("materials", material_id) or {}
    site = db.get("sites", site_id) if site_id else None
    price, how = material_price(client_id, material_id) if client_id else (m.get("base_price") or 0, "базовая")
    tons = to_tons(qty, unit, m) if not m.get("is_service") else qty
    cap = S("default_capacity_t", 25.0)
    trips = max(1, math.ceil(tons / cap)) if not m.get("is_service") else 1
    deliv, zone = delivery_price(site, trips) if not m.get("is_service") else (0, "—")
    goods = round(price * qty, 2)
    return dict(price=price, price_how=how, goods=goods, delivery=deliv, zone=zone, trips=trips, tons=tons,
                total=round(goods + deliv, 2), vat_pct=m.get("vat_pct") or S("vat_pct", 20.0))


# ---------------- долги и лимиты ----------------

def client_balance(client_id):
    inv = db.val("SELECT SUM(total) FROM invoices WHERE client_id=? AND status!='canceled'", (client_id,))
    paid = db.val("SELECT SUM(amount) FROM payments WHERE client_id=? AND direction='in'", (client_id,))
    uninvoiced = db.val("SELECT SUM(revenue) FROM trips t JOIN orders o ON o.id=t.order_id WHERE o.client_id=? AND t.status='closed' AND t.invoice_id IS NULL", (client_id,))
    return dict(invoiced=inv, paid=paid, debt=round(inv - paid, 2), uninvoiced=round(uninvoiced, 2),
                exposure=round(inv - paid + uninvoiced, 2))


def overdue(client_id=None):
    sql = "SELECT * FROM invoices WHERE status IN ('issued','partial') AND due_date<?"
    a = [db.today()]
    if client_id:
        sql += " AND client_id=?"
        a.append(client_id)
    return db.q(sql, a)


def credit_check(client_id, amount):
    c = db.get("clients", client_id) or {}
    b = client_balance(client_id)
    msgs = []
    if c.get("pay_terms") == "prepay":
        msgs.append("клиент на предоплате — отгрузка после оплаты")
    lim = c.get("credit_limit") or 0
    if lim and b["exposure"] + amount > lim:
        msgs.append(f"превышен кредитный лимит: долг {b['exposure']:,.0f} + заявка {amount:,.0f} > {lim:,.0f} ₽".replace(",", " "))
    od = overdue(client_id)
    if od:
        msgs.append(f"просроченных счетов: {len(od)} на {sum(i['total'] - (i['paid'] or 0) for i in od):,.0f} ₽".replace(",", " "))
    return "; ".join(msgs)


# ---------------- заявки ----------------

def create_order(data, user):
    data = db.clean("orders", data)
    data.setdefault("unit", "t")
    data["unit"] = data.get("unit") or "t"
    qt = quote(data["client_id"], data.get("site_id"), data["material_id"], data["qty"], data["unit"])
    if data.get("price") is None:
        data["price"] = qt["price"]
    if data.get("delivery") is None:
        data["delivery"] = qt["delivery"]
    data["total"] = round(data["price"] * data["qty"] + (data["delivery"] or 0), 2)
    data["number"] = db.next_no("order", "З-", 5)
    data["status"] = data.get("status") or "new"
    data["source"] = data.get("source") or "phone"
    data["created_at"] = db.now()
    if not data.get("manager_id") and user and user.get("role") == "manager":
        data["manager_id"] = user["id"]
    data["credit_flag"] = credit_check(data["client_id"], data["total"]) or "ок"
    id_ = db.insert("orders", data, user and user["id"])
    cl = name_of("clients", data["client_id"])
    notify(f"Новая заявка {data['number']}: {cl}, {name_of('materials', data['material_id'])} {data['qty']:g} {LBL['unit'].get(data['unit'], '')}",
           role="dispatcher", link=f"#/orders/{id_}", kind="order")
    if data["credit_flag"] != "ок":
        notify(f"⚠ {data['number']} ({cl}): {data['credit_flag']}", role="accountant", link=f"#/orders/{id_}", kind="credit")
    return id_


def update_order(id_, data, user):
    data = db.clean("orders", data, partial=True)
    o = db.get("orders", id_)
    m = {**o, **data}
    if any(k in data for k in ("price", "qty", "delivery")):
        data["total"] = round((m["price"] or 0) * (m["qty"] or 0) + (m["delivery"] or 0), 2)
    db.update("orders", id_, data, user and user["id"])
    if data.get("status") == "confirmed" and o["status"] != "confirmed":
        client_msg(o["client_id"], f"Заявка {o['number']} подтверждена. Доставка {o['date']}.")


def plan_trips(order_id, user, capacity=None):
    """Разбивает заявку на рейсы по грузоподъёмности."""
    o = db.get("orders", order_id)
    m = db.get("materials", o["material_id"]) or {}
    left = to_tons(o["qty"], o["unit"], m) - db.val("SELECT SUM(plan_qty) FROM trips WHERE order_id=? AND status!='canceled'", (order_id,))
    if left <= 0.01:
        raise ValueError("По заявке уже созданы рейсы на весь объём")
    cap = capacity or S("default_capacity_t", 25.0)
    site = db.get("sites", o["site_id"]) if o["site_id"] else None
    sup = o.get("supplier_id") or ((best_supplier(o["material_id"]) or {}).get("supplier_id") if not o.get("warehouse_id") else None)
    ids = []
    while left > 0.01:
        q_ = round(min(cap, left), 2)
        ids.append(db.insert("trips", dict(
            number=db.next_no("trip", "Р-", 6), order_id=order_id, date=o["date"], plan_qty=q_, status="plan",
            source_kind="warehouse" if o.get("warehouse_id") else "supplier", supplier_id=sup, warehouse_id=o.get("warehouse_id"),
            distance_km=site_distance(site)), user and user["id"]))
        left -= q_
    db.update("orders", order_id, {"status": "planned"}, user and user["id"])
    return ids


def recalc_order_status(order_id):
    o = db.get("orders", order_id)
    if not o or o["status"] == "canceled":
        return
    st = [r["status"] for r in db.q("SELECT status FROM trips WHERE order_id=? AND status!='canceled'", (order_id,))]
    if not st:
        return
    if all(s == "closed" for s in st):
        new = "done"
    elif any(s in ("accepted", "loading", "loaded", "on_way", "delivered", "closed") for s in st):
        new = "in_work"
    else:
        new = "planned"
    if new != o["status"]:
        db.update("orders", order_id, {"status": new})
        if new == "done":
            client_msg(o["client_id"], f"Заявка {o['number']} выполнена полностью. Спасибо!")


# ---------------- рейсы ----------------

def ensure_waybill(vehicle_id, driver_id, date, user=None):
    w = db.q1("SELECT * FROM waybills WHERE vehicle_id=? AND driver_id=? AND date=?", (vehicle_id, driver_id, date))
    if w:
        return w["id"]
    v = db.get("vehicles", vehicle_id) or {}
    prev = db.q1("SELECT odo_end, fuel_end FROM waybills WHERE vehicle_id=? AND status='closed' ORDER BY date DESC, id DESC", (vehicle_id,)) or {}
    return db.insert("waybills", dict(number=db.next_no("waybill", "ПЛ-", 5), date=date, vehicle_id=vehicle_id, driver_id=driver_id,
                                      odo_start=prev.get("odo_end") or v.get("odometer"), fuel_start=prev.get("fuel_end"),
                                      status="open", edo_status="draft"), user and user["id"])


def conflicts(trip):
    """Проверки перед назначением: документы водителя и машины, ремонт, занятость."""
    out = []
    d = trip["date"]
    if trip.get("driver_id"):
        dr = db.get("drivers", trip["driver_id"]) or {}
        if dr.get("status") and dr["status"] != "work":
            out.append(f"водитель: {LBL['drv_status'].get(dr['status'])}")
        for k, lbl in (("license_to", "ВУ"), ("med_to", "медсправка")):
            if dr.get(k) and dr[k] < d:
                out.append(f"у водителя просрочено: {lbl} ({dr[k]})")
    if trip.get("vehicle_id"):
        v = db.get("vehicles", trip["vehicle_id"]) or {}
        if v.get("status") in ("repair", "off"):
            out.append(f"машина {v.get('plate')}: {LBL['veh_status'].get(v['status'])}")
        for k, lbl in (("osago_to", "ОСАГО"), ("insp_to", "техосмотр"), ("tacho_to", "тахограф")):
            if v.get(k) and v[k] < d:
                out.append(f"у машины просрочено: {lbl} ({v[k]})")
        if v.get("capacity_t") and trip.get("plan_qty") and trip["plan_qty"] > v["capacity_t"] * 1.02:
            out.append(f"перегруз: план {trip['plan_qty']} т > {v['capacity_t']} т")
        n = db.val("SELECT COUNT(*) FROM trips WHERE vehicle_id=? AND date=? AND id!=? AND status NOT IN ('canceled','closed')",
                   (trip["vehicle_id"], d, trip.get("id") or 0))
        if n >= S("max_trips_per_day", 4):
            out.append(f"у машины уже {n} рейс(а) на эту дату")
    return out


def assign_trip(trip_id, vehicle_id, driver_id, user, force=False):
    t = db.get("trips", trip_id)
    if t["status"] not in ("plan", "assigned", "accepted"):
        raise ValueError("Рейс уже в работе — переназначить нельзя")
    v = db.get("vehicles", vehicle_id) if vehicle_id else None
    if v and not driver_id:
        dr = db.q1("SELECT id FROM drivers WHERE vehicle_id=? AND (status='work' OR status IS NULL)", (vehicle_id,))
        driver_id = dr and dr["id"]
    probe = {**t, "vehicle_id": vehicle_id, "driver_id": driver_id}
    warn = conflicts(probe)
    if warn and not force:
        return {"ok": False, "warnings": warn}
    wb = ensure_waybill(vehicle_id, driver_id, t["date"], user) if (vehicle_id and driver_id) else None
    db.update("trips", trip_id, dict(vehicle_id=vehicle_id, driver_id=driver_id, status="assigned", waybill_id=wb, ts_assigned=db.now()),
              user and user["id"])
    driver_msg_trip(trip_id)
    recalc_order_status(t["order_id"])
    return {"ok": True, "warnings": warn}


def trip_card(trip_id):
    t = db.get("trips", trip_id)
    o = db.get("orders", t["order_id"]) or {}
    site = db.get("sites", o.get("site_id")) or {}
    src = (db.get("suppliers", t["supplier_id"]) if t.get("supplier_id") else db.get("warehouses", t.get("warehouse_id"))) or {}
    return t, o, site, src


def driver_msg_trip(trip_id):
    t, o, site, src = trip_card(trip_id)
    dr = db.get("drivers", t.get("driver_id")) or {}
    if not dr.get("tg_chat"):
        return
    txt = (f"🚛 Новый рейс {t['number']} на {t['date']}\n"
           f"Погрузка: {src.get('name', '—')}, {src.get('address', '')}\n"
           f"Материал: {name_of('materials', o.get('material_id'))}, {t['plan_qty']:g} т\n"
           f"Выгрузка: {site.get('address', '—')}\n"
           f"Приёмщик: {site.get('contact') or o.get('contact') or '—'} {site.get('phone') or ''}\n"
           f"Окно: {o.get('time_from') or ''}–{o.get('time_to') or ''}  {site.get('access') or ''}")
    outbox(dr["tg_chat"], txt, [[{"text": "✅ Принял", "data": f"tr:{trip_id}:accepted"}, {"text": "❌ Не могу", "data": f"tr:{trip_id}:reject"}]])


NEXT = {"assigned": "accepted", "accepted": "loading", "loading": "loaded", "loaded": "on_way", "on_way": "delivered", "delivered": "closed"}


def set_trip_status(trip_id, status, user=None, qty=None, photo=None, by_driver=False):
    t = db.get("trips", trip_id)
    if not t:
        raise ValueError("Рейс не найден")
    if status == "reject":
        db.update("trips", trip_id, dict(status="plan", driver_id=None, vehicle_id=None, waybill_id=None), user and user["id"])
        notify(f"Водитель отказался от рейса {t['number']} — нужно переназначить", role="dispatcher", link="#/dispatch", kind="trip")
        return
    upd = {"status": status}
    if status == "loaded":
        upd["ts_loaded"] = db.now()
        upd["load_qty"] = qty if qty is not None else (t.get("load_qty") or t["plan_qty"])
    if status == "delivered":
        upd["ts_delivered"] = db.now()
        upd["unload_qty"] = qty if qty is not None else (t.get("unload_qty") or t.get("load_qty") or t["plan_qty"])
        if not t.get("load_qty"):
            upd["load_qty"] = upd["unload_qty"]
    if photo:
        upd["photo"] = photo
    db.update("trips", trip_id, upd, user and user["id"])
    t = db.get("trips", trip_id)
    o = db.get("orders", t["order_id"])
    if status == "loaded":
        _stock_on_load(t, o, user)
        client_msg(o["client_id"], f"Рейс {t['number']} по заявке {o['number']} загружен ({t['load_qty']:g} т) и скоро выедет к вам.")
    if status == "on_way":
        client_msg(o["client_id"], f"Машина по заявке {o['number']} в пути: {name_of('vehicles', t['vehicle_id'], 'plate')}.")
    if status == "delivered":
        make_tn(trip_id, user)
        client_msg(o["client_id"], f"Рейс {t['number']} выгружен: {t['unload_qty']:g} т. Документы — в личном кабинете.")
        if t.get("load_qty") and abs(t["load_qty"] - t["unload_qty"]) > max(0.3, t["load_qty"] * 0.02):
            notify(f"Расхождение веса по {t['number']}: погружено {t['load_qty']} т, принято {t['unload_qty']} т", role="dispatcher",
                   link=f"#/trips/{trip_id}", kind="weight")
    if status == "closed":
        calc_trip(trip_id)
    if status in ("delivered",) and S("auto_close", 1):
        db.update("trips", trip_id, {"status": "closed"})
        calc_trip(trip_id)
    recalc_order_status(t["order_id"])
    if by_driver:
        notify(f"{t['number']}: {LBL['trip_status'].get(db.get('trips', trip_id)['status'])} ({name_of('drivers', t['driver_id'])})",
               role="dispatcher", link="#/dispatch", kind="trip")


def _stock_on_load(t, o, user):
    qty = t["load_qty"] or t["plan_qty"]
    if t["source_kind"] == "warehouse" and t.get("warehouse_id"):
        if not db.q1("SELECT id FROM stock_moves WHERE trip_id=?", (t["id"],)):
            db.insert("stock_moves", dict(date=t["date"], warehouse_id=t["warehouse_id"], material_id=o["material_id"], qty=-qty,
                                          kind="trip", trip_id=t["id"], price=avg_cost(t["warehouse_id"], o["material_id"])), user and user["id"])
    elif t.get("supplier_id"):
        p = db.q1("SELECT id FROM purchases WHERE trip_id=?", (t["id"],))
        price = supplier_price(t["supplier_id"], o["material_id"])
        data = dict(date=t["date"], supplier_id=t["supplier_id"], material_id=o["material_id"], qty=qty, price=price,
                    total=round(price * qty, 2), trip_id=t["id"], paid="no", note=f"Авто: рейс {t['number']}")
        if p:
            db.update("purchases", p["id"], data)
        else:
            db.insert("purchases", data, user and user["id"])


def avg_cost(warehouse_id, material_id):
    r = db.q1("SELECT SUM(qty*price) s, SUM(qty) q FROM stock_moves WHERE warehouse_id=? AND material_id=? AND qty>0", (warehouse_id, material_id))
    return round(r["s"] / r["q"], 2) if r and r["q"] else 0


def driver_pay(dr, t, revenue):
    rate = dr.get("pay_rate") or 0
    k = dr.get("pay_type") or "trip"
    qty = t.get("unload_qty") or t.get("plan_qty") or 0
    km = (t.get("distance_km") or 0) * 2
    return round({"trip": rate, "ton": rate * qty, "km": rate * km, "pct": revenue * rate / 100, "day": 0}.get(k, rate), 2)


def calc_trip(trip_id):
    """Экономика рейса: выручка, материал, водитель, топливо, наёмник, маржа."""
    t = db.get("trips", trip_id)
    o = db.get("orders", t["order_id"])
    m = db.get("materials", o["material_id"]) or {}
    qty = t.get("unload_qty") or t.get("load_qty") or t["plan_qty"]
    ntrips = max(1, db.val("SELECT COUNT(*) FROM trips WHERE order_id=? AND status!='canceled'", (o["id"],)))
    qty_in_unit = qty if o["unit"] != "m3" else qty / (m.get("density") or 1.5)
    revenue = round((o["price"] or 0) * qty_in_unit + (o["delivery"] or 0) / ntrips, 2)
    if t["source_kind"] == "warehouse" and t.get("warehouse_id"):
        cmat = round(avg_cost(t["warehouse_id"], o["material_id"]) * qty, 2)
    else:
        cmat = round(supplier_price(t["supplier_id"], o["material_id"]) * qty, 2) if t.get("supplier_id") else 0
    v = db.get("vehicles", t.get("vehicle_id")) or {}
    dr = db.get("drivers", t.get("driver_id")) or {}
    ccar = 0
    if v.get("owner") == "hired":
        car = db.get("carriers", v.get("carrier_id")) or {}
        ccar = car.get("rate") or 0
        cdrv = cfuel = 0
    else:
        cdrv = driver_pay(dr, t, revenue)
        cfuel = round((t.get("distance_km") or 0) * 2 * (v.get("fuel_norm") or S("fuel_norm", 38.0)) / 100 * S("fuel_price", 72.0), 2)
    margin = round(revenue - cmat - cdrv - cfuel - ccar, 2)
    db.update("trips", trip_id, dict(revenue=revenue, cost_material=cmat, cost_driver=cdrv, cost_fuel=cfuel, cost_carrier=ccar, margin=margin))
    return dict(revenue=revenue, margin=margin)


# ---------------- документы ----------------

def make_doc(kind, user=None, **kw):
    nums = {"tn": ("tn", "ТН-"), "waybill": ("wbdoc", "ПЛ-"), "invoice": ("invdoc", "С-"), "act": ("act", "А-"), "upd": ("upd", "УПД-"), "recon": ("recon", "АС-")}
    c, p = nums[kind]
    kw.setdefault("number", db.next_no(c, p, 5))
    kw.setdefault("date", db.today())
    kw.setdefault("status", "ready")
    return db.insert("documents", dict(kind=kind, **kw), user and user["id"])


def make_tn(trip_id, user=None):
    t = db.get("trips", trip_id)
    if t.get("tn_number"):
        return
    o = db.get("orders", t["order_id"])
    did = make_doc("tn", user, client_id=o["client_id"], order_id=o["id"], trip_id=trip_id, waybill_id=t.get("waybill_id"),
                   total=t.get("revenue"))
    db.update("trips", trip_id, {"tn_number": db.get("documents", did)["number"]})


def close_waybill(wb_id, data, user):
    w = db.get("waybills", wb_id)
    data = db.clean("waybills", data, partial=True)
    data["status"] = "closed"
    db.update("waybills", wb_id, data, user and user["id"])
    w = db.get("waybills", wb_id)
    if w.get("odo_end"):
        db.update("vehicles", w["vehicle_id"], {"odometer": w["odo_end"]})
    if not db.q1("SELECT id FROM documents WHERE kind='waybill' AND waybill_id=?", (wb_id,)):
        make_doc("waybill", user, waybill_id=wb_id, number=w["number"], date=w["date"])
    fleet_checks()


# ---------------- счета и оплаты ----------------

def build_invoice(client_id, date_from, date_to, user, contract_id=None):
    trips = db.q("""SELECT t.*, o.material_id, o.unit, o.price op, o.delivery od, o.number onum, o.id oid
                    FROM trips t JOIN orders o ON o.id=t.order_id
                    WHERE o.client_id=? AND t.status='closed' AND t.invoice_id IS NULL AND t.date BETWEEN ? AND ?
                    ORDER BY t.date, t.id""", (client_id, date_from, date_to))
    if not trips:
        raise ValueError("Нет закрытых рейсов без счёта за этот период")
    c = db.get("clients", client_id) or {}
    vat = S("vat_pct", 20.0)
    with db.tx():
        due = (datetime.date.today() + datetime.timedelta(days=int(c.get("delay_days") or 0))).isoformat()
        inv = db.insert("invoices", dict(number=db.next_no("invoice", "С-", 5), date=db.today(), client_id=client_id, contract_id=contract_id,
                                         period_from=date_from, period_to=date_to, total=0, vat=0, paid=0, due_date=due, status="issued"),
                        user and user["id"])
        total = 0
        for t in trips:
            m = db.get("materials", t["material_id"]) or {}
            qty = t.get("unload_qty") or t["plan_qty"]
            ntr = max(1, db.val("SELECT COUNT(*) FROM trips WHERE order_id=? AND status!='canceled'", (t["oid"],)))
            q_unit = qty if t["unit"] != "m3" else round(qty / (m.get("density") or 1.5), 2)
            s1 = round(q_unit * (t["op"] or 0), 2)
            db.insert("invoice_lines", dict(invoice_id=inv, trip_id=t["id"], name=f"{m.get('name')} (рейс {t['number']}, {t['date']}, ТН {t.get('tn_number') or '—'})",
                                            qty=q_unit, unit=LBL["unit"].get(t["unit"], "т"), price=t["op"], sum=s1))
            total += s1
            if t["od"]:
                d1 = round(t["od"] / ntr, 2)
                db.insert("invoice_lines", dict(invoice_id=inv, trip_id=t["id"], name=f"Доставка, рейс {t['number']}", qty=1, unit="рейс", price=d1, sum=d1))
                total += d1
            db.update("trips", t["id"], {"invoice_id": inv})
        total = round(total, 2)
        db.update("invoices", inv, dict(total=total, vat=round(total * vat / (100 + vat), 2)))
    make_doc("invoice", user, client_id=client_id, invoice_id=inv, number=db.get("invoices", inv)["number"], total=total)
    make_doc("upd" if S("doc_mode_upd", 1) else "act", user, client_id=client_id, invoice_id=inv, total=total)
    client_msg(client_id, f"Выставлен счёт {db.get('invoices', inv)['number']} на {total:,.2f} ₽, оплатить до {due}. Счёт и УПД — в личном кабинете.".replace(",", " "))
    return inv


def apply_payment(pay_id):
    p = db.get("payments", pay_id)
    if p["direction"] != "in" or not p.get("client_id"):
        if p.get("purchase_id"):
            pu = db.get("purchases", p["purchase_id"])
            paid = db.val("SELECT SUM(amount) FROM payments WHERE purchase_id=?", (pu["id"],))
            db.update("purchases", pu["id"], {"paid": "yes" if paid >= (pu["total"] or 0) - 0.01 else "partial"})
        return
    left = p["amount"] - db.val("SELECT 0")
    targets = [db.get("invoices", p["invoice_id"])] if p.get("invoice_id") else \
        db.q("SELECT * FROM invoices WHERE client_id=? AND status IN ('issued','partial') ORDER BY date, id", (p["client_id"],))
    for inv in targets:
        if not inv:
            continue
        paid = db.val("SELECT SUM(amount) FROM payments WHERE invoice_id=?", (inv["id"],))
        if not p.get("invoice_id") and left > 0:
            db.update("payments", pay_id, {"invoice_id": inv["id"]})
            paid += p["amount"]
            left = 0
        st = "paid" if paid >= inv["total"] - 0.01 else ("partial" if paid > 0 else "issued")
        db.update("invoices", inv["id"], {"paid": round(paid, 2), "status": st})
        if p.get("invoice_id") or left == 0:
            break


def parse_bank_1c(text):
    """Выписка в формате 1С:Клиент-банк (kl_to_1c.txt). Возвращает список документов."""
    docs, cur = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("СекцияДокумент"):
            cur = {}
        elif line.startswith("КонецДокумента"):
            if cur is not None:
                docs.append(cur)
            cur = None
        elif cur is not None and "=" in line:
            k, v = line.split("=", 1)
            cur[k] = v
    return docs


def import_bank(text, user):
    own_inn = (db.setting("company_inn") or "").strip()
    res = {"added": 0, "matched": 0, "skipped": 0, "unmatched": []}
    for d in parse_bank_1c(text):
        amount = float((d.get("Сумма") or "0").replace(",", "."))
        payer, recv = d.get("ПлательщикИНН", ""), d.get("ПолучательИНН", "")
        incoming = recv == own_inn if own_inn else payer != own_inn
        inn = payer if incoming else recv
        date = d.get("ДатаПоступило") or d.get("ДатаСписано") or d.get("Дата") or ""
        if re.match(r"\d\d\.\d\d\.\d{4}", date):
            date = f"{date[6:10]}-{date[3:5]}-{date[0:2]}"
        num = d.get("Номер", "")
        if db.q1("SELECT id FROM payments WHERE doc_no=? AND date=? AND amount=? AND source='bank'", (num, date, amount)):
            res["skipped"] += 1
            continue
        purpose = d.get("НазначениеПлатежа", "")
        data = dict(date=date, direction="in" if incoming else "out", amount=amount, doc_no=num, cp_inn=inn, purpose=purpose, source="bank")
        if incoming:
            c = db.q1("SELECT id FROM clients WHERE inn=?", (inn,))
            if c:
                data["client_id"] = c["id"]
                mm = re.search(r"(?:сч[её]т[ау]?|сч\.?)\s*(?:№|N|#)?\s*(С-\d+|\d+)", purpose, re.I)
                if mm:
                    n = mm.group(1)
                    inv = db.q1("SELECT id FROM invoices WHERE client_id=? AND (number=? OR number=?)", (c["id"], n, f"С-{int(n):05d}" if n.isdigit() else n))
                    if inv:
                        data["invoice_id"] = inv["id"]
                res["matched"] += 1
            else:
                res["unmatched"].append(f"{date} {amount:.2f} ИНН {inn}: {purpose[:60]}")
        else:
            s = db.q1("SELECT id FROM suppliers WHERE inn=?", (inn,))
            if s:
                data["supplier_id"] = s["id"]
            ca = db.q1("SELECT id FROM carriers WHERE inn=?", (inn,))
            if ca:
                data["carrier_id"] = ca["id"]
        pid = db.insert("payments", data, user and user["id"])
        apply_payment(pid)
        res["added"] += 1
    return res


def reconciliation(client_id, date_from, date_to):
    opening = db.val("SELECT SUM(total) FROM invoices WHERE client_id=? AND status!='canceled' AND date<?", (client_id, date_from)) - \
        db.val("SELECT SUM(amount) FROM payments WHERE client_id=? AND direction='in' AND date<?", (client_id, date_from))
    rows = [dict(date=i["date"], doc=f"Счёт/УПД {i['number']}", debit=i["total"], credit=0)
            for i in db.q("SELECT * FROM invoices WHERE client_id=? AND status!='canceled' AND date BETWEEN ? AND ?", (client_id, date_from, date_to))]
    rows += [dict(date=p["date"], doc=f"Оплата п/п {p.get('doc_no') or ''}", debit=0, credit=p["amount"])
             for p in db.q("SELECT * FROM payments WHERE client_id=? AND direction='in' AND date BETWEEN ? AND ?", (client_id, date_from, date_to))]
    rows.sort(key=lambda r: r["date"])
    closing = round(opening + sum(r["debit"] for r in rows) - sum(r["credit"] for r in rows), 2)
    return dict(opening=round(opening, 2), rows=rows, closing=closing)


def aging():
    out = []
    for c in db.q("SELECT id,name FROM clients ORDER BY name"):
        b = {"0": 0, "1-15": 0, "16-30": 0, "31-60": 0, "60+": 0}
        for i in db.q("SELECT * FROM invoices WHERE client_id=? AND status IN ('issued','partial')", (c["id"],)):
            rest = (i["total"] or 0) - (i["paid"] or 0)
            days = (datetime.date.today() - datetime.date.fromisoformat(i["due_date"] or i["date"])).days
            key = "0" if days <= 0 else "1-15" if days <= 15 else "16-30" if days <= 30 else "31-60" if days <= 60 else "60+"
            b[key] += rest
        bal = client_balance(c["id"])
        if any(b.values()) or bal["uninvoiced"]:
            out.append(dict(client_id=c["id"], client=c["name"], **{k: round(v, 2) for k, v in b.items()},
                            total=round(sum(b.values()), 2), uninvoiced=bal["uninvoiced"]))
    return out


# ---------------- зарплата ----------------

def calc_payroll(driver_id, date_from, date_to, user):
    dr = db.get("drivers", driver_id)
    trips = db.q("SELECT * FROM trips WHERE driver_id=? AND status='closed' AND date BETWEEN ? AND ?", (driver_id, date_from, date_to))
    accrued = sum(t.get("cost_driver") or 0 for t in trips)
    if dr.get("pay_type") == "day":
        days = len({t["date"] for t in trips})
        accrued = days * (dr.get("pay_rate") or 0)
    data = dict(driver_id=driver_id, period_from=date_from, period_to=date_to, trips=len(trips),
                tons=round(sum(t.get("unload_qty") or 0 for t in trips), 2),
                km=round(sum((t.get("distance_km") or 0) * 2 for t in trips), 1), accrued=round(accrued, 2))
    ex = db.q1("SELECT * FROM payroll WHERE driver_id=? AND period_from=? AND period_to=?", (driver_id, date_from, date_to))
    if ex:
        if ex["status"] != "draft":
            raise ValueError("Ведомость уже утверждена")
        data["total"] = round(data["accrued"] + (ex.get("bonus") or 0) - (ex.get("deduction") or 0) - (ex.get("advance") or 0), 2)
        db.update("payroll", ex["id"], data, user and user["id"])
        return ex["id"]
    data.update(status="draft", bonus=0, deduction=0, advance=0, total=data["accrued"])
    return db.insert("payroll", data, user and user["id"])


def payroll_total(pid):
    p = db.get("payroll", pid)
    db.update("payroll", pid, {"total": round((p["accrued"] or 0) + (p["bonus"] or 0) - (p["deduction"] or 0) - (p["advance"] or 0), 2)})


# ---------------- склад ----------------

def stock():
    return db.q("""SELECT w.name warehouse, m.name material, s.warehouse_id, s.material_id, ROUND(SUM(s.qty),2) qty,
                   ROUND(SUM(CASE WHEN s.qty>0 THEN s.qty*s.price ELSE 0 END)/NULLIF(SUM(CASE WHEN s.qty>0 THEN s.qty ELSE 0 END),0),2) avg_price
                   FROM stock_moves s JOIN warehouses w ON w.id=s.warehouse_id JOIN materials m ON m.id=s.material_id
                   GROUP BY s.warehouse_id, s.material_id ORDER BY w.name, m.name""")


def purchase_to_stock(pid, user):
    p = db.get("purchases", pid)
    if p.get("warehouse_id") and not db.q1("SELECT id FROM stock_moves WHERE purchase_id=?", (pid,)):
        db.insert("stock_moves", dict(date=p["date"], warehouse_id=p["warehouse_id"], material_id=p["material_id"], qty=p["qty"],
                                      kind="purchase", price=p["price"], purchase_id=pid), user and user["id"])


# ---------------- автопарк ----------------

def fleet_alerts(days=None):
    days = days or S("alert_days", 14)
    lim = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
    out = []
    for v in db.q("SELECT * FROM vehicles WHERE status!='off' OR status IS NULL"):
        for k, lbl in (("osago_to", "ОСАГО"), ("insp_to", "Техосмотр"), ("tacho_to", "Калибровка тахографа"), ("pass_to", "Пропуск в Москву")):
            if v.get(k) and v[k] <= lim:
                out.append(dict(kind="vehicle", id=v["id"], who=v["plate"], what=lbl, date=v[k], overdue=v[k] < db.today()))
        if v.get("to_every_km") and v.get("odometer") is not None:
            nxt = (v.get("to_last_km") or 0) + v["to_every_km"]
            if v["odometer"] >= nxt - 1500:
                out.append(dict(kind="vehicle", id=v["id"], who=v["plate"], what=f"ТО по пробегу (на {nxt} км, сейчас {v['odometer']})",
                                date="", overdue=v["odometer"] >= nxt))
    for d in db.q("SELECT * FROM drivers WHERE status!='fired' OR status IS NULL"):
        for k, lbl in (("license_to", "Водительское удостоверение"), ("med_to", "Медсправка")):
            if d.get(k) and d[k] <= lim:
                out.append(dict(kind="driver", id=d["id"], who=d["name"], what=lbl, date=d[k], overdue=d[k] < db.today()))
    return sorted(out, key=lambda a: (not a["overdue"], a["date"] or "0"))


def fleet_checks():
    for a in fleet_alerts():
        txt = f"{'Просрочено' if a['overdue'] else 'Скоро истекает'}: {a['what']} — {a['who']} {a['date']}"
        if not db.q1("SELECT id FROM notifications WHERE text=? AND ts>=?", (txt, db.today())):
            notify(txt, role="mechanic", link="#/fleet", kind="fleet")


def fuel_report(date_from, date_to):
    out = []
    for v in db.q("SELECT * FROM vehicles WHERE owner='own' OR owner IS NULL ORDER BY plate"):
        lit = db.val("SELECT SUM(liters) FROM fuel WHERE vehicle_id=? AND date BETWEEN ? AND ?", (v["id"], date_from, date_to))
        amt = db.val("SELECT SUM(amount) FROM fuel WHERE vehicle_id=? AND date BETWEEN ? AND ?", (v["id"], date_from, date_to))
        km = db.val("SELECT SUM(odo_end-odo_start) FROM waybills WHERE vehicle_id=? AND status='closed' AND date BETWEEN ? AND ? AND odo_end>odo_start",
                    (v["id"], date_from, date_to))
        if not km:
            km = db.val("SELECT SUM(distance_km*2) FROM trips WHERE vehicle_id=? AND status='closed' AND date BETWEEN ? AND ?", (v["id"], date_from, date_to))
        norm = (v.get("fuel_norm") or 0) * km / 100
        fact100 = round(lit / km * 100, 1) if km else None
        out.append(dict(vehicle_id=v["id"], plate=v["plate"], km=round(km), liters=round(lit, 1), amount=round(amt), norm_l=round(norm, 1),
                        fact_100=fact100, norm_100=v.get("fuel_norm"), over_l=round(lit - norm, 1) if km else None))
    return out


# ---------------- клиентам ----------------

def client_msg(client_id, text):
    c = db.get("clients", client_id) or {}
    if c.get("tg_chat") and S("notify_clients", 1):
        outbox(c["tg_chat"], text)


# ---------------- отчёты ----------------

def dashboard(date=None):
    d = date or db.today()
    m0 = d[:8] + "01"
    r = lambda sql, a=(): db.val(sql, a)
    return dict(
        date=d,
        orders_today=r("SELECT COUNT(*) FROM orders WHERE date=? AND status!='canceled'", (d,)),
        orders_new=r("SELECT COUNT(*) FROM orders WHERE status='new'"),
        trips_today=r("SELECT COUNT(*) FROM trips WHERE date=? AND status!='canceled'", (d,)),
        trips_unassigned=r("SELECT COUNT(*) FROM trips WHERE date<=? AND status='plan'", (d,)),
        trips_active=r("SELECT COUNT(*) FROM trips WHERE status IN ('accepted','loading','loaded','on_way')"),
        trips_done_today=r("SELECT COUNT(*) FROM trips WHERE date=? AND status='closed'", (d,)),
        tons_today=round(r("SELECT SUM(unload_qty) FROM trips WHERE date=? AND status='closed'", (d,)), 1),
        revenue_month=round(r("SELECT SUM(revenue) FROM trips WHERE date>=? AND date<=? AND status='closed'", (m0, d))),
        margin_month=round(r("SELECT SUM(margin) FROM trips WHERE date>=? AND date<=? AND status='closed'", (m0, d))),
        tons_month=round(r("SELECT SUM(unload_qty) FROM trips WHERE date>=? AND date<=? AND status='closed'", (m0, d)), 1),
        debt=round(r("SELECT SUM(total-COALESCE(paid,0)) FROM invoices WHERE status IN ('issued','partial')")),
        overdue=round(r("SELECT SUM(total-COALESCE(paid,0)) FROM invoices WHERE status IN ('issued','partial') AND due_date<?", (d,))),
        uninvoiced=round(r("SELECT SUM(revenue) FROM trips WHERE status='closed' AND invoice_id IS NULL")),
        vehicles_work=r("SELECT COUNT(*) FROM vehicles WHERE status='work'"),
        vehicles_repair=r("SELECT COUNT(*) FROM vehicles WHERE status='repair'"),
        leads_open=r("SELECT COUNT(*) FROM leads WHERE stage NOT IN ('won','lost')"),
        alerts=len(fleet_alerts()),
    )


def report(kind, date_from, date_to):
    a = (date_from, date_to)
    base = """FROM trips t JOIN orders o ON o.id=t.order_id LEFT JOIN clients c ON c.id=o.client_id LEFT JOIN materials m ON m.id=o.material_id
              LEFT JOIN vehicles v ON v.id=t.vehicle_id LEFT JOIN drivers d ON d.id=t.driver_id LEFT JOIN suppliers s ON s.id=t.supplier_id
              WHERE t.status='closed' AND t.date BETWEEN ? AND ?"""
    agg = "COUNT(*) trips, ROUND(SUM(t.unload_qty),1) tons, ROUND(SUM(t.revenue)) revenue, ROUND(SUM(t.cost_material)) material, ROUND(SUM(t.cost_driver+t.cost_fuel+t.cost_carrier)) transport, ROUND(SUM(t.margin)) margin"
    group = {"clients": "c.name", "materials": "m.name", "vehicles": "v.plate", "drivers": "d.name", "suppliers": "s.name", "days": "t.date"}[kind]
    rows = db.q(f"SELECT {group} name, {agg} {base} GROUP BY {group} ORDER BY revenue DESC", a)
    for r in rows:
        r["margin_pct"] = round(r["margin"] / r["revenue"] * 100, 1) if r.get("revenue") else None
    return rows
