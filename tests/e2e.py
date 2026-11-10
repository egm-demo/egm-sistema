"""Сквозная проверка: справочники → заявка → рейсы → назначение → статусы водителя → ТН/путевой лист →
счёт/УПД → оплата → зарплата → отчёты → кабинет клиента → экспорт/импорт. Запуск:
  python tests/e2e.py http://localhost:8077 <пароль admin>"""
import sys, io, httpx, datetime as dt

BASE, PW = sys.argv[1], sys.argv[2]
c = httpx.Client(base_url=BASE, timeout=30)
ok = fail = 0


def chk(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print("OK  ", name)
    else:
        fail += 1; print("FAIL", name, str(extra)[:400])


def j(r):
    try:
        return r.json()
    except Exception:
        return {"_text": r.text[:300], "_code": r.status_code}


def post(url, body=None, **kw):
    r = c.post(url, json=body, **kw) if "files" not in kw else c.post(url, **kw)
    if r.status_code >= 400:
        print("   !", url, r.status_code, r.text[:300])
    return j(r)


def put(url, body):
    r = c.put(url, json=body)
    if r.status_code >= 400:
        print("   !", url, r.status_code, r.text[:300])
    return j(r)


def get(url):
    r = c.get(url)
    if r.status_code >= 400:
        print("   !", url, r.status_code, r.text[:300])
    return j(r)


today = dt.date.today().isoformat()
chk("вход admin", c.post("/api/login", json={"login": "admin", "password": PW}).status_code == 200)
chk("неверный пароль отклонён", httpx.post(BASE + "/api/login", json={"login": "admin", "password": "x"}).status_code in (400, 401, 403))
me = get("/api/me"); chk("me", me.get("user", {}).get("role") == "admin", me)
meta = get("/api/meta"); chk("meta: сущности", len(meta.get("entities", {})) > 20, list(meta)[:5])

post("/api/settings", {"company_name": "ООО «ЕГМ» (пример)", "company_inn": "7700000000", "vat_pct": "20", "fuel_price": "70"})
mat = post("/api/e/materials", {"name": "Песок карьерный (тест)", "unit": "t", "base_price": 900, "density": 1.5})
chk("материал", mat.get("id"), mat)
sup = post("/api/e/suppliers", {"name": "Карьер Тестовый", "address": "МО, Тестовый р-н"})
chk("карьер", sup.get("id"), sup)
sp = post("/api/e/supplier_prices", {"supplier_id": sup["id"], "material_id": mat["id"], "price": 500})
chk("закупочная цена", sp.get("id"), sp)
z = post("/api/e/zones", {"name": "до 50 км", "km_from": 0, "km_to": 50, "trip_price": 9000})
chk("зона доставки", z.get("id"), z)
cl = post("/api/e/clients", {"name": "ООО Тест-Строй", "inn": "5000000001", "pay_terms": "postpay", "delay_days": 10, "credit_limit": 1000000})
chk("клиент", cl.get("id"), cl)
site = post("/api/e/sites", {"client_id": cl["id"], "name": "Объект 1", "address": "МО, г. Тест, ул. Стройки 1", "distance_km": 40, "contact": "Иван", "phone": "+70000000000"})
chk("объект", site.get("id"), site)
veh = post("/api/e/vehicles", {"plate": "А001АА50", "model": "Shacman", "vtype": "dump", "capacity_t": 25, "owner": "own", "status": "work", "fuel_norm": 40,
                                "osago_to": "2027-10-01", "insp_to": "2027-10-01"})
chk("машина", veh.get("id"), veh)
drv = post("/api/e/drivers", {"name": "Петров П.П.", "phone": "+70000000001", "vehicle_id": veh.get("id"), "pay_type": "ton", "pay_rate": 150,
                               "license_to": "2030-01-01", "med_to": "2027-01-01", "status": "work"})
chk("водитель", drv.get("id"), drv)

q = post("/api/quote", {"client_id": cl["id"], "site_id": site["id"], "material_id": mat["id"], "qty": 50, "unit": "t"})
chk("расчёт цены", q.get("total", 0) > 0, q)
o = post("/api/e/orders", {"client_id": cl["id"], "site_id": site["id"], "material_id": mat["id"], "qty": 50, "unit": "t", "date": today,
                           "price": q.get("price"), "delivery": q.get("delivery"), "status": "new", "source": "phone", "supplier_id": sup["id"]})
chk("заявка", o.get("id"), o)
post(f"/api/orders/{o['id']}/status", {"status": "confirmed"})
plan = post(f"/api/orders/{o['id']}/plan", {"capacity": 25})
trips = plan.get("trips", [])
chk("разбивка на 2 рейса", len(trips) == 2, plan)
tids = [t if isinstance(t, int) else t.get("id") for t in trips]

disp = get(f"/api/dispatch?date={today}")
chk("диспетчерская", "vehicles" in disp and len(disp.get("trips", [])) >= 2, str(disp)[:300])

for k, tid in enumerate(tids):
    a = post(f"/api/trips/{tid}/assign", {"vehicle_id": veh["id"]})
    if not a.get("ok"):
        print("   предупреждения:", a.get("warnings"))
        a = post(f"/api/trips/{tid}/assign", {"vehicle_id": veh["id"], "force": True})
    chk(f"назначение рейса {k+1}", a.get("ok") or a.get("id"), a)
    for st, qty in [("accepted", None), ("loading", None), ("loaded", 25.4), ("on_way", None), ("delivered", 25.2), ("closed", None)]:
        r = post(f"/api/trips/{tid}/status", {"status": st, "qty": qty})
        if r.get("error") or r.get("detail"):
            chk(f"рейс {k+1} → {st}", False, r); break
    t = get(f"/api/e/trips/{tid}")
    chk(f"рейс {k+1} закрыт, ТН и маржа", t.get("status") == "closed" and t.get("tn_number") and t.get("revenue"), {x: t.get(x) for x in ("status", "tn_number", "revenue", "margin", "waybill_id")})

t1 = get(f"/api/e/trips/{tids[0]}")
for path in [f"/doc/tn/{tids[0]}", f"/doc/waybill/{t1.get('waybill_id')}"]:
    r = c.get(path)
    chk(f"печатная форма {path.split('/')[2]}", r.status_code == 200 and len(r.text) > 1000, r.text[:200])

if t1.get("waybill_id"):
    w = post(f"/api/waybills/{t1['waybill_id']}/close", {"odo_end": 100200, "fuel_issued": 60, "fuel_end": 20})
    chk("закрытие путевого листа", not w.get("detail") and not w.get("error"), w)

inv = post("/api/invoices/build", {"date_from": today, "date_to": today, "client_id": cl["id"]})
invs = inv.get("invoices", [])
chk("счёт сформирован", len(invs) == 1, inv)
iid = invs[0] if invs and isinstance(invs[0], int) else (invs[0].get("id") if invs else None)
if iid:
    i = get(f"/api/e/invoices/{iid}")
    chk("сумма счёта > 0", (i.get("total") or 0) > 0, i)
    for path in [f"/doc/invoice/{iid}", f"/doc/upd/{iid}"]:
        r = c.get(path); chk(f"печать {path.split('/')[2]}", r.status_code == 200 and "₽" in r.text or "руб" in r.text, r.text[:200])
    p = post("/api/e/payments", {"date": today, "direction": "in", "amount": i["total"], "client_id": cl["id"], "invoice_id": iid, "source": "manual", "doc_no": "1"})
    chk("оплата", p.get("id"), p)
    i = get(f"/api/e/invoices/{iid}")
    chk("счёт оплачен", i.get("status") == "paid", {x: i.get(x) for x in ("status", "paid", "total")})

b = get(f"/api/balance/{cl['id']}"); chk("баланс клиента = 0", abs(b.get("debt", 1)) < 1, b)
r = c.get(f"/doc/recon/{cl['id']}?date_from={today[:4]}-01-01&date_to={today}"); chk("акт сверки", r.status_code == 200 and len(r.text) > 800, r.text[:200])

pr = post("/api/payroll/build", {"date_from": today, "date_to": today})
rows = pr.get("payroll", [])
chk("зарплата рассчитана", len(rows) >= 1, pr)
pl = get(f"/api/e/payroll?driver_id={drv['id']}").get("rows", [{}])
chk("сдельная = 150 ₽/т × 50.4 т", pl and abs((pl[0].get("accrued") or 0) - 150 * 50.4) < 1, pl[:1])

for rep in ["clients", "materials", "vehicles", "drivers", "days", "aging", "fuel", "stock", "fleet"]:
    r = c.get(f"/api/report/{rep}?date_from={today[:8]}01&date_to={today}")
    chk(f"отчёт {rep}", r.status_code == 200 and isinstance(r.json(), list), r.text[:200])
d = get("/api/dashboard"); chk("сводка", "revenue_month" in d, d)

r = c.get("/api/export/clients.xlsx"); chk("экспорт Excel", r.status_code == 200 and r.content[:2] == b"PK", r.status_code)
r = c.get("/api/export/clients.xlsx?template=1"); chk("шаблон импорта", r.status_code == 200 and r.content[:2] == b"PK", r.status_code)
import openpyxl
wb = openpyxl.Workbook(); ws = wb.active; ws.append(["Название", "ИНН", "Телефон"]); ws.append(["ООО Импорт-1", "5000000002", "+7 900 000-00-02"]); ws.append(["ИП Импорт-2", "500000000003", ""])
bio = io.BytesIO(); wb.save(bio)
r = c.post("/api/import/clients", files={"file": ("c.xlsx", bio.getvalue())}, data={"dry": "0"})
chk("импорт клиентов из Excel", r.status_code == 200 and r.json().get("added") == 2, r.text[:300])

# кабинет клиента
u = post("/api/e/users", {"login": "client1", "name": "Тест-Строй", "role": "client", "client_id": cl["id"], "password": "cl-pass-123", "active": 1})
chk("логин клиента", u.get("id"), u)
cc = httpx.Client(base_url=BASE, timeout=30)
chk("вход клиента", cc.post("/api/login", json={"login": "client1", "password": "cl-pass-123"}).status_code == 200)
cab = cc.get("/api/cabinet").json(); chk("кабинет: заявки и счета", len(cab.get("orders", [])) >= 1 and len(cab.get("invoices", [])) >= 1, str(cab)[:300])
no = cc.post("/api/cabinet/order", json={"material_id": mat["id"], "qty": 30, "unit": "t", "date": today, "site_id": site["id"]}).json()
chk("заявка из кабинета", no.get("id"), no)
chk("клиенту закрыт чужой раздел", cc.get("/api/e/vehicles").status_code in (401, 403))
chk("клиенту закрыт чужой клиент", cc.get(f"/api/balance/{cl['id'] + 1}").status_code in (401, 403, 404))

# приложение водителя
post("/api/e/users", {"login": "drv1", "name": "Петров", "role": "driver", "driver_id": drv["id"], "password": "drv-pass-1", "active": 1})
dc = httpx.Client(base_url=BASE, timeout=30)
chk("вход водителя", dc.post("/api/login", json={"login": "drv1", "password": "drv-pass-1"}).status_code == 200)
dv = dc.get("/api/driver").json(); chk("приложение водителя", dv.get("month", {}).get("trips") == 2, str(dv)[:300])
chk("водителю закрыты финансы", dc.get("/api/e/invoices").status_code in (401, 403))

n = get("/api/notifications"); chk("уведомления", "rows" in n, n)
ob = c.get("/api/e/outbox")
print(f"\nИТОГО: {ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
