"""Telegram-бот ЕГМ (long polling, без внешних библиотек кроме httpx).
Водитель: получает рейсы, жмёт кнопки статусов, вводит вес, шлёт фото накладной и геопозицию.
Клиент: получает статусы заявок и счета; может оставить заявку текстом.
Токен и прокси — в Настройках (tg_token, tg_proxy). Без токена бот спит, сообщения копятся в outbox."""
import json, time, os, re
from . import db, logic

STATE = {}  # chat -> ожидаемое действие


def _client():
    import httpx
    proxy = db.setting("tg_proxy") or None
    return httpx.Client(timeout=40, proxy=proxy) if proxy else httpx.Client(timeout=40)


def api(c, method, **kw):
    tok = db.setting("tg_token")
    r = c.post(f"https://api.telegram.org/bot{tok}/{method}", json=kw)
    return r.json()


def kb(buttons):
    if not buttons:
        return None
    return {"inline_keyboard": [[{"text": b["text"], "callback_data": b["data"]} for b in row] for row in buttons]}


def driver_buttons(trip_id, status):
    nxt = logic.NEXT.get(status)
    if not nxt or nxt == "closed":
        return []
    lbl = {"accepted": "✅ Принял", "loading": "📍 Приехал на погрузку", "loaded": "⚖️ Загружен (ввести вес)", "on_way": "🚚 Выехал к клиенту",
           "delivered": "🏁 Выгрузился (ввести вес)"}[nxt]
    return [[{"text": lbl, "data": f"tr:{trip_id}:{nxt}"}]]


def who(chat):
    d = db.q1("SELECT * FROM drivers WHERE tg_chat=?", (str(chat),))
    if d:
        return "driver", d
    c = db.q1("SELECT * FROM clients WHERE tg_chat=?", (str(chat),))
    if c:
        return "client", c
    u = db.q1("SELECT * FROM users WHERE tg_chat=?", (str(chat),))
    if u:
        return "staff", u
    return None, None


def check_code(code):
    m = re.match(r"^(d|c|u)(\d+)_([0-9a-f]{6})$", code or "")
    if not m:
        return None
    from .main import bot_code
    if bot_code(m.group(1), int(m.group(2))) != code:
        return None
    return m.group(1), int(m.group(2))


def handle_message(c, msg):
    chat = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    role, rec = who(chat)
    if text.startswith("/start"):
        code = text[6:].strip()
        r = check_code(code)
        if r:
            ent = {"d": "drivers", "c": "clients", "u": "users"}[r[0]]
            db.update(ent, r[1], {"tg_chat": str(chat)})
            name = (db.get(ent, r[1]) or {}).get("name")
            api(c, "sendMessage", chat_id=chat, text=f"Готово, {name}! Бот ЕГМ подключён." +
                ("\nСюда будут приходить рейсы. Команды: /reisy — мои рейсы." if r[0] == "d" else
                 "\nСюда будут приходить статусы заявок и счета. Чтобы заказать — просто напишите, что и куда привезти." if r[0] == "c" else ""))
        else:
            api(c, "sendMessage", chat_id=chat, text="Здравствуйте! Это бот ЕГМ.\nЧтобы заказать песок, щебень или вывоз грунта — напишите сюда: что нужно, объём, адрес и телефон. Менеджер перезвонит.")
        return
    if role == "driver":
        st = STATE.get(chat)
        if msg.get("location"):
            loc = msg["location"]
            t = db.q1("SELECT vehicle_id FROM trips WHERE driver_id=? AND status NOT IN ('closed','canceled','plan') ORDER BY id DESC", (rec["id"],))
            db.ex("INSERT INTO gps_points(vehicle_id,driver_id,ts,lat,lon,source) VALUES(?,?,?,?,?,?)",
                  ((t or {}).get("vehicle_id") or rec.get("vehicle_id"), rec["id"], db.now(), loc["latitude"], loc["longitude"], "tg"))
            return
        if msg.get("photo"):
            t = db.q1("SELECT id FROM trips WHERE driver_id=? AND status NOT IN ('closed','canceled','plan') ORDER BY id DESC", (rec["id"],)) or \
                db.q1("SELECT id FROM trips WHERE driver_id=? ORDER BY ts_delivered DESC, id DESC", (rec["id"],))
            if t:
                fid = msg["photo"][-1]["file_id"]
                f = api(c, "getFile", file_id=fid)
                if f.get("ok"):
                    tok = db.setting("tg_token")
                    data = c.get(f"https://api.telegram.org/file/bot{tok}/{f['result']['file_path']}").content
                    from .main import UPL
                    os.makedirs(UPL, exist_ok=True)
                    fn = f"trip{t['id']}_{int(time.time())}.jpg"
                    open(os.path.join(UPL, fn), "wb").write(data)
                    db.update("trips", t["id"], {"photo": fn})
                    api(c, "sendMessage", chat_id=chat, text="Фото накладной сохранено ✅")
            return
        if st and st[0] == "qty":
            try:
                q = float(text.replace(",", "."))
            except ValueError:
                api(c, "sendMessage", chat_id=chat, text="Напишите вес числом, например 24,5")
                return
            STATE.pop(chat, None)
            logic.set_trip_status(st[1], st[2], qty=q, by_driver=True)
            t = db.get("trips", st[1])
            api(c, "sendMessage", chat_id=chat, text=f"Записал: {q:g} т. Статус: {logic.LBL['trip_status'][t['status']]}",
                reply_markup=kb(driver_buttons(t["id"], t["status"])))
            return
        if text.startswith("/reisy") or text.lower() in ("рейсы", "мои рейсы"):
            rows = db.q("SELECT id FROM trips WHERE driver_id=? AND status NOT IN ('closed','canceled','plan') ORDER BY date, id", (rec["id"],))
            if not rows:
                api(c, "sendMessage", chat_id=chat, text="Активных рейсов нет.")
            for r in rows:
                t, o, site, src = logic.trip_card(r["id"])
                api(c, "sendMessage", chat_id=chat, text=f"{t['number']} ({t['date']}) — {logic.LBL['trip_status'][t['status']]}\n{src.get('name', '')} → {site.get('address', '')}\n{t['plan_qty']:g} т",
                    reply_markup=kb(driver_buttons(t["id"], t["status"])))
            return
        api(c, "sendMessage", chat_id=chat, text="Команды: /reisy — мои рейсы. Можно прислать фото накладной или геопозицию.")
        return
    # клиент или незнакомец -> лид
    if text:
        name = (rec or {}).get("name") or " ".join(x for x in [msg["from"].get("first_name"), msg["from"].get("last_name")] if x)
        if role == "client":
            logic.notify(f"Сообщение клиента {name} в Telegram: {text[:200]}", role="manager", kind="lead")
        else:
            lid = db.insert("leads", dict(name=name or "Telegram", source="tg", stage="new", note=text[:1000], created_at=db.now(), next_date=db.today(),
                                          phone=(re.search(r"\+?[78][\d\-\s()]{9,}", text) or [None])[0]))
            logic.notify(f"Заявка из Telegram: {name}: {text[:120]}", role="manager", link=f"#/leads/{lid}", kind="lead")
        api(c, "sendMessage", chat_id=chat, text="Приняли! Менеджер свяжется с вами в рабочее время.")


def handle_callback(c, cb):
    chat = cb["message"]["chat"]["id"]
    role, rec = who(chat)
    data = cb.get("data") or ""
    api(c, "answerCallbackQuery", callback_query_id=cb["id"])
    m = re.match(r"tr:(\d+):(\w+)", data)
    if not m or role != "driver":
        return
    tid, st = int(m.group(1)), m.group(2)
    t = db.get("trips", tid)
    if not t or t.get("driver_id") != rec["id"]:
        api(c, "sendMessage", chat_id=chat, text="Этот рейс назначен не вам.")
        return
    if st in ("loaded", "delivered"):
        STATE[chat] = ("qty", tid, st)
        api(c, "sendMessage", chat_id=chat, text=f"Сколько тонн {'погрузили' if st == 'loaded' else 'приняли на объекте'}? Напишите число (например 24,5).")
        return
    logic.set_trip_status(tid, st, by_driver=True)
    t = db.get("trips", tid)
    txt = "Отказ принят, диспетчер переназначит рейс." if st == "reject" else f"{t['number']}: {logic.LBL['trip_status'][t['status']]}"
    api(c, "sendMessage", chat_id=chat, text=txt, reply_markup=kb(driver_buttons(tid, t["status"])) if st != "reject" else None)


def flush_outbox(c):
    for m in db.q("SELECT * FROM outbox WHERE sent=0 AND channel='tg' AND (err IS NULL OR err='') ORDER BY id LIMIT 20"):
        try:
            kw = dict(chat_id=m["chat"], text=m["text"])
            k = kb(json.loads(m["buttons"] or "[]"))
            if k:
                kw["reply_markup"] = k
            r = api(c, "sendMessage", **kw)
            db.ex("UPDATE outbox SET sent=?, err=? WHERE id=?", (1 if r.get("ok") else 0, "" if r.get("ok") else str(r)[:200], m["id"]))
        except Exception as ex:
            db.ex("UPDATE outbox SET err=? WHERE id=?", (str(ex)[:200], m["id"]))


def run():
    offset = 0
    while True:
        if not db.setting("tg_token") or db.setting("tg_enabled", "1") != "1":
            time.sleep(15)
            continue
        try:
            with _client() as c:
                me = api(c, "getMe")
                if me.get("ok"):
                    db.set_setting("tg_bot_username", me["result"]["username"])
                while db.setting("tg_token"):
                    flush_outbox(c)
                    r = api(c, "getUpdates", offset=offset, timeout=20, allowed_updates=["message", "callback_query"])
                    for u in r.get("result", []):
                        offset = u["update_id"] + 1
                        try:
                            if "message" in u:
                                handle_message(c, u["message"])
                            elif "callback_query" in u:
                                handle_callback(c, u["callback_query"])
                        except Exception as ex:
                            print("bot handler error:", ex)
                    flush_outbox(c)
        except Exception as ex:
            print("bot error:", ex)
            time.sleep(20)
