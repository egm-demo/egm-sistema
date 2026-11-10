"""Экран руководителя, утренняя сводка и разбор голосовых заявок.
Идея: один экран, светофор, крупные проблемы со ссылками; сотрудникам ничего не нужно вводить вручную."""
import calendar, datetime, re
from . import db, logic

S = logic.S


def _r(sql, a=()):
    return db.val(sql, a)


# ---------------- экран руководителя ----------------

def panel(date=None):
    d = date or db.today()
    dd = datetime.date.fromisoformat(d)
    m0 = d[:8] + "01"
    days_in = calendar.monthrange(dd.year, dd.month)[1]
    rev = _r("SELECT SUM(revenue) FROM trips WHERE date BETWEEN ? AND ? AND status='closed'", (m0, d))
    margin = _r("SELECT SUM(margin) FROM trips WHERE date BETWEEN ? AND ? AND status='closed'", (m0, d))
    tons = _r("SELECT SUM(unload_qty) FROM trips WHERE date BETWEEN ? AND ? AND status='closed'", (m0, d))
    plan = S("plan_month_revenue", 0.0)
    forecast = rev / dd.day * days_in if dd.day else 0
    leads = _r("SELECT COUNT(*) FROM leads WHERE substr(created_at,1,10) BETWEEN ? AND ?", (m0, d))
    orders = _r("SELECT COUNT(*) FROM orders WHERE substr(created_at,1,10) BETWEEN ? AND ? AND status!='canceled'", (m0, d))
    won = _r("SELECT COUNT(*) FROM leads WHERE substr(created_at,1,10) BETWEEN ? AND ? AND stage='won'", (m0, d))
    sales = dict(leads=leads, orders=orders, won=won, conv=round(won / leads * 100) if leads else None,
                 revenue=round(rev), margin=round(margin), margin_pct=round(margin / rev * 100) if rev else None,
                 tons=round(tons, 1), plan=plan, plan_pct=round(rev / plan * 100) if plan else None,
                 forecast=round(forecast), forecast_pct=round(forecast / plan * 100) if plan else None,
                 day=dd.day, days=days_in)

    # менеджеры: выручка закрытых рейсов по их заявкам
    mans = []
    for u in db.q("SELECT id,name FROM users WHERE role='manager' AND active=1 ORDER BY name"):
        mrev = _r("""SELECT SUM(t.revenue) FROM trips t JOIN orders o ON o.id=t.order_id
                     WHERE o.manager_id=? AND t.status='closed' AND t.date BETWEEN ? AND ?""", (u["id"], m0, d))
        mans.append(dict(id=u["id"], name=u["name"], revenue=round(mrev),
                         orders=_r("SELECT COUNT(*) FROM orders WHERE manager_id=? AND substr(created_at,1,10) BETWEEN ? AND ? AND status!='canceled'", (u["id"], m0, d)),
                         leads=_r("SELECT COUNT(*) FROM leads WHERE manager_id=? AND stage NOT IN ('won','lost')", (u["id"],)),
                         overdue_calls=_r("SELECT COUNT(*) FROM leads WHERE manager_id=? AND next_date<? AND stage NOT IN ('won','lost')", (u["id"], d))))
    if len(mans) > 1:
        lo = min(m["revenue"] for m in mans)
        hi = max(m["revenue"] for m in mans)
        for m in mans:
            m["light"] = "r" if m["revenue"] == lo and hi > lo else ("g" if m["revenue"] == hi else "y")
    else:
        for m in mans:
            m["light"] = "g"

    # техника: светофор
    alerts = logic.fleet_alerts()
    stuck_h = S("stuck_hours", 4.0)
    lim = (datetime.datetime.now() - datetime.timedelta(hours=stuck_h)).strftime("%Y-%m-%d %H:%M:%S")
    fleet = []
    for v in db.q("SELECT * FROM vehicles WHERE status!='off' OR status IS NULL ORDER BY plate"):
        trips = db.q("SELECT * FROM trips WHERE vehicle_id=? AND date=? AND status!='canceled'", (v["id"], d))
        active = [t for t in trips if t["status"] in ("assigned", "accepted", "loading", "loaded", "on_way")]
        done = [t for t in trips if t["status"] in ("delivered", "closed")]
        va = [a for a in alerts if a["kind"] == "vehicle" and a["id"] == v["id"]]
        why = []
        light = "g"
        if v.get("status") == "repair":
            light, why = "r", ["в ремонте"]
        if any(a["overdue"] for a in va):
            light = "r"
            why += [a["what"] + " просрочен" for a in va if a["overdue"]]
        st = [t for t in active if max(t.get("ts_loaded") or "", t.get("ts_assigned") or "") and max(t.get("ts_loaded") or "", t.get("ts_assigned") or "") < lim]
        if st:
            light = "r"
            why.append(f"рейс {st[0]['number']} без движения больше {stuck_h:g} ч")
        if light == "g" and not trips and v.get("status") == "work":
            light = "y"
            why.append("сегодня без рейсов")
        if light == "g" and va:
            light = "y"
            why += [a["what"] + " скоро истекает" for a in va]
        fleet.append(dict(id=v["id"], plate=v["plate"], model=v.get("model") or "", light=light, why=why,
                          trips=len(trips), done=len(done), active=len(active),
                          tons=round(sum((t.get("unload_qty") or 0) for t in done), 1),
                          revenue=round(sum((t.get("revenue") or 0) for t in done))))
    fleet.sort(key=lambda x: {"r": 0, "y": 1, "g": 2}[x["light"]])

    # проблемы: что требует реакции, по убыванию важности
    debtors = []
    for c in db.q("SELECT id,name,credit_limit FROM clients WHERE credit_limit>0"):
        b = logic.client_balance(c["id"])
        if b["exposure"] > c["credit_limit"]:
            debtors.append(c["name"])
    pr = []

    def p(n, title, href, sev="r", sub=""):
        if n:
            pr.append(dict(n=n, title=title, href=href, sev=sev, sub=sub))

    overdue_sum = _r("SELECT SUM(total-COALESCE(paid,0)) FROM invoices WHERE status IN ('issued','partial') AND due_date<?", (d,))
    p(len(logic.overdue()), "просроченных счетов", "#/reports/aging", "r", logic_rub(overdue_sum))
    p(len(debtors), "клиентов сверх кредитного лимита", "#/reports/aging", "r", ", ".join(debtors[:3]))
    p(_r("SELECT COUNT(*) FROM trips WHERE date<=? AND status='plan'", (d,)), "рейсов без машины", "#/dispatch", "r")
    p(sum(1 for f in fleet if any("без движения" in w for w in f["why"])), "машин без движения по рейсу", "#/dispatch", "r")
    uninv_n = _r("SELECT COUNT(*) FROM trips WHERE status='closed' AND invoice_id IS NULL")
    p(uninv_n, "закрытых рейсов без счёта", "#/invoices", "y", logic_rub(_r("SELECT SUM(revenue) FROM trips WHERE status='closed' AND invoice_id IS NULL")) + " можно выставить")
    p(_r("SELECT COUNT(*) FROM orders WHERE status='new'"), "заявок ждут подтверждения", "#/orders?status=new", "y")
    p(_r("SELECT COUNT(*) FROM trips WHERE date BETWEEN ? AND ? AND status IN ('delivered','closed') AND (photo IS NULL OR photo='')", (m0, d)),
      "рейсов без фото накладной", "#/trips", "y", "за месяц")
    p(_r("SELECT COUNT(*) FROM notifications WHERE kind='weight' AND substr(ts,1,10) BETWEEN ? AND ?", (m0, d)), "расхождений веса", "#/trips", "y", "за месяц")
    p(_r("SELECT COUNT(*) FROM leads WHERE next_date<? AND stage NOT IN ('won','lost')", (d,)), "клиентам не перезвонили в срок", "#/leads", "y")
    p(_r("SELECT COUNT(*) FROM trips WHERE date BETWEEN ? AND ? AND status='closed' AND margin<0", (m0, d)), "рейсов в минус", "#/reports", "r", "за месяц")
    p(sum(1 for a in alerts if a["overdue"]), "просроченных документов (ОСАГО, ТО, ВУ…)", "#/fleet", "r")
    pr.sort(key=lambda x: x["sev"] != "r")

    money = dict(uninvoiced=round(_r("SELECT SUM(revenue) FROM trips WHERE status='closed' AND invoice_id IS NULL")),
                 debt=round(_r("SELECT SUM(total-COALESCE(paid,0)) FROM invoices WHERE status IN ('issued','partial')")),
                 overdue=round(overdue_sum),
                 paid_month=round(_r("SELECT SUM(amount) FROM payments WHERE direction='in' AND date BETWEEN ? AND ?", (m0, d))))
    today = dict(trips=_r("SELECT COUNT(*) FROM trips WHERE date=? AND status!='canceled'", (d,)),
                 done=_r("SELECT COUNT(*) FROM trips WHERE date=? AND status IN ('delivered','closed')", (d,)),
                 tons=round(_r("SELECT SUM(unload_qty) FROM trips WHERE date=? AND status IN ('delivered','closed')", (d,)), 1),
                 green=sum(1 for f in fleet if f["light"] == "g"), yellow=sum(1 for f in fleet if f["light"] == "y"),
                 red=sum(1 for f in fleet if f["light"] == "r"))
    return dict(date=d, sales=sales, managers=mans, fleet=fleet, problems=pr, money=money, today=today)


def logic_rub(v):
    return f"{round(v or 0):,}".replace(",", " ") + " ₽"


def digest(date=None):
    """Короткая сводка руководителю в Telegram."""
    x = panel(date)
    s, m, t = x["sales"], x["money"], x["today"]
    y = (datetime.date.fromisoformat(x["date"]) - datetime.timedelta(days=1)).isoformat()
    yt = _r("SELECT COUNT(*) FROM trips WHERE date=? AND status IN ('delivered','closed')", (y,))
    ytons = _r("SELECT SUM(unload_qty) FROM trips WHERE date=? AND status IN ('delivered','closed')", (y,))
    yrev = _r("SELECT SUM(revenue) FROM trips WHERE date=? AND status='closed'", (y,))
    lines = [f"☀️ ЕГМ, сводка на {x['date'][8:10]}.{x['date'][5:7]}",
             f"Вчера: {yt} рейсов, {ytons:g} т, выручка {logic_rub(yrev)}",
             f"Месяц: {logic_rub(s['revenue'])}" + (f" ({s['plan_pct']}% плана)" if s["plan_pct"] is not None else "") +
             f", прогноз {logic_rub(s['forecast'])}" + (f", маржа {s['margin_pct']}%" if s["margin_pct"] is not None else ""),
             f"Сегодня в плане: {t['trips']} рейсов. Машины: 🟢{t['green']} 🟡{t['yellow']} 🔴{t['red']}",
             f"Деньги: можно выставить {logic_rub(m['uninvoiced'])}, долг {logic_rub(m['debt'])}, просрочено {logic_rub(m['overdue'])}"]
    if x["problems"]:
        lines.append("")
        lines.append("Требует внимания:")
        for p_ in x["problems"][:7]:
            lines.append(f"{'🔴' if p_['sev'] == 'r' else '🟡'} {p_['n']} — {p_['title']}" + (f" ({p_['sub']})" if p_["sub"] else ""))
    else:
        lines.append("Проблем нет 👍")
    return "\n".join(lines)


def send_digest(force=False):
    """Раз в день после часа digest_hour. Возвращает число получателей."""
    d = db.today()
    if not force:
        if db.setting("digest_last") == d or datetime.datetime.now().hour < S("digest_hour", 8) or S("digest_on", 1) != 1:
            return 0
    db.set_setting("digest_last", d)
    txt = digest(d)
    n = 0
    for u in db.q("SELECT tg_chat FROM users WHERE role IN ('director','admin') AND active=1 AND tg_chat IS NOT NULL AND tg_chat!=''"):
        logic.outbox(u["tg_chat"], txt)
        n += 1
    return n


# ---------------- голос -> заявка ----------------

_MODEL = None


def transcribe(path):
    """Расшифровка речи локально (faster-whisper). Аудио никуда не отправляется."""
    global _MODEL
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("Распознавание речи не установлено (pip install faster-whisper)")
    if _MODEL is None:
        _MODEL = WhisperModel(db.setting("voice_model") or "small", device="cpu", compute_type="int8")
    segs, _ = _MODEL.transcribe(path, language="ru", beam_size=5)
    return " ".join(s.text.strip() for s in segs).strip()


NUMW = {"одну": 1, "одна": 1, "один": 1, "две": 2, "два": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8,
        "девять": 9, "десять": 10, "пятнадцать": 15, "двадцать": 20, "двадцать пять": 25, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
        "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90, "сто": 100, "двести": 200, "триста": 300, "пятьсот": 500}
UNITS = [(r"т(?:онн[аы]?|он|\.|\b)", "t"), (r"(?:куб(?:ов|а|ометр\w*)?|м3|м³)", "m3"), (r"(?:машин\w*|рейс\w*|камаз\w*|самосвал\w*)", "trip")]


def _stem(w):
    w = w.lower().replace("ё", "е")
    return w[:max(4, len(w) - 2)] if len(w) > 4 else w


def parse(text):
    """Правила, без внешнего ИИ: материал, количество, единица, дата, клиент, объект, телефон.
    Результат — черновик; человек проверяет и подтверждает."""
    t = " " + (text or "").lower().replace("ё", "е") + " "
    for w, n in sorted(NUMW.items(), key=lambda x: -len(x[0])):
        t = re.sub(rf"\b{w}\b", str(n), t)
    out = dict(text=text, material_id=None, material="", qty=None, unit="t", date=None, client_id=None, client="",
               site_id=None, site="", address="", phone="")
    words = set(_stem(w) for w in re.findall(r"[а-яa-z0-9]+", t) if len(w) > 2)
    best = (0, None)
    for m in db.q("SELECT id,name FROM materials WHERE active=1 OR active IS NULL"):
        mw = [_stem(w) for w in re.findall(r"[а-яa-z0-9]+", m["name"].lower().replace("ё", "е")) if len(w) > 2]
        score = sum(2 if i == 0 else 1 for i, w in enumerate(mw) if w in words)
        fr = re.findall(r"\d+\s*[-–]\s*\d+", m["name"])
        if fr and re.search(fr[0].replace(" ", r"\s*").replace("-", r"\s*[-–на ]+\s*"), t):
            score += 2
        if mw and mw[0] in words and score > best[0]:
            best = (score, m)
    if best[1]:
        out["material_id"], out["material"] = best[1]["id"], best[1]["name"]
    for rx, u in UNITS:
        mm = re.search(r"(\d+(?:[.,]\d+)?)\s*" + rx, t)
        if mm:
            out["qty"], out["unit"] = float(mm.group(1).replace(",", ".")), u
            break
    if out["unit"] == "trip" and out["qty"]:
        out["trips"] = out["qty"]
        out["qty"], out["unit"] = out["qty"] * S("default_capacity_t", 25.0), "t"
    today = datetime.date.today()
    if "послезавтра" in t:
        out["date"] = (today + datetime.timedelta(days=2)).isoformat()
    elif "завтра" in t:
        out["date"] = (today + datetime.timedelta(days=1)).isoformat()
    elif "сегодня" in t:
        out["date"] = today.isoformat()
    else:
        mm = re.search(r"\b(\d{1,2})[./](\d{1,2})\b", t)
        if mm:
            try:
                out["date"] = datetime.date(today.year, int(mm.group(2)), int(mm.group(1))).isoformat()
            except ValueError:
                pass
    ph = re.search(r"\+?[78][\d\-\s()]{9,}\d", text or "")
    out["phone"] = ph.group(0).strip() if ph else ""
    for c in db.q("SELECT id,name FROM clients"):
        core = re.sub(r"(ооо|ао|пао|ип|зао)\s*", "", c["name"].lower().replace("ё", "е")).strip(" «»\"'")
        cw = [_stem(w) for w in re.findall(r"[а-яa-z0-9]+", core) if len(w) > 2]
        if cw and all(w in words for w in cw):
            out["client_id"], out["client"] = c["id"], c["name"]
            break
    if out["client_id"]:
        sites = db.q("SELECT id,name,address FROM sites WHERE client_id=?", (out["client_id"],))
        for s in sites:
            sw = [_stem(w) for w in re.findall(r"[а-яa-z0-9]+", f"{s['name']} {s['address']}".lower()) if len(w) > 3]
            if any(w in words for w in sw):
                out["site_id"], out["site"] = s["id"], s["name"]
                break
        if not out["site_id"] and len(sites) == 1:
            out["site_id"], out["site"] = sites[0]["id"], sites[0]["name"]
    mm = re.search(r"\b(?:в|на|до|адрес)\s+((?:г\.?\s*)?[а-я][а-я\-]+(?:\s+[а-я0-9][а-я0-9\-]+){0,3})", t)
    if mm and not re.match(r"(завтра|сегодня|послезавтра|объект|утро|утра|вечер|\d)", mm.group(1)):
        out["address"] = mm.group(1).strip()
    out["ready"] = bool(out["material_id"] and out["qty"] and out["client_id"] and out["site_id"])
    out["missing"] = [n for k, n in (("client_id", "клиент"), ("site_id", "объект"), ("material_id", "материал"), ("qty", "количество")) if not out[k]]
    return out


def draft_text(p_):
    u = logic.LBL["unit"].get(p_["unit"], "")
    rows = [f"Клиент: {p_['client'] or '—'}", f"Объект: {p_['site'] or p_['address'] or '—'}",
            f"Материал: {p_['material'] or '—'}", f"Количество: {p_['qty']:g} {u}" if p_["qty"] else "Количество: —",
            f"Дата: {p_['date'] or 'завтра'}"]
    if p_["missing"]:
        rows.append("Не понял: " + ", ".join(p_["missing"]))
    return "\n".join(rows)


def order_from(p_, user, source="tg"):
    d = dict(client_id=p_["client_id"], site_id=p_["site_id"], material_id=p_["material_id"], qty=p_["qty"], unit=p_["unit"],
             date=p_["date"] or (datetime.date.today() + datetime.timedelta(days=1)).isoformat(), source=source,
             comment="Голосом: " + (p_["text"] or "")[:500])
    return logic.create_order(d, user)


def lead_from(p_, name, source="tg"):
    lid = db.insert("leads", dict(name=name or p_["client"] or "Голосовая заявка", phone=p_["phone"] or None, source=source, stage="new",
                                  material=p_["material"][:80], qty=(f"{p_['qty']:g} {logic.LBL['unit'].get(p_['unit'], '')}" if p_["qty"] else ""),
                                  address=p_["address"] or p_["site"], note="Голосом: " + (p_["text"] or "")[:1000],
                                  created_at=db.now(), next_date=db.today()))
    logic.notify(f"Голосовая заявка: {name or ''} — {(p_['text'] or '')[:120]}", role="manager", link=f"#/leads/{lid}", kind="lead")
    return lid
