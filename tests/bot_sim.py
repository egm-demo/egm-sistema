"""Офлайн-проверка Telegram-бота: Telegram API подменён заглушкой. Запуск на копии базы:
  EGM_DATA=<папка> python tests/bot_sim.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import db, logic, bot
from app.main import bot_code

SENT = []
bot.api = lambda c, method, **kw: (SENT.append((method, kw)), {"ok": True, "result": {}})[1]
ok = fail = 0


def chk(n, cond, x=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print("OK  " if cond else "FAIL", n, "" if cond else str(x)[:300])


drv = db.q1("SELECT * FROM drivers ORDER BY id LIMIT 1")
o = db.q1("SELECT * FROM orders ORDER BY id DESC LIMIT 1")
CHAT = 555001
# привязка водителя по коду
bot.handle_message(None, {"chat": {"id": CHAT}, "from": {"first_name": "Петров"}, "text": "/start " + bot_code("d", drv["id"])})
chk("привязка водителя /start", (db.get("drivers", drv["id"]) or {}).get("tg_chat") == str(CHAT), SENT[-1:])
# новый рейс и назначение -> сообщение водителю в outbox
ADMIN = db.q1("SELECT * FROM users WHERE role='admin'")
tid = logic.plan_trips(o["id"], ADMIN, 30)[0]
tid = tid if isinstance(tid, int) else tid.get("id")
r = logic.assign_trip(tid, drv["vehicle_id"], drv["id"], ADMIN, force=True)
out = db.q("SELECT * FROM outbox WHERE chat=? ORDER BY id DESC", (str(CHAT),))
chk("задание водителю ушло в очередь", len(out) >= 1, out[:1])
# кнопки
def press(st):
    bot.handle_callback(None, {"id": "x", "message": {"chat": {"id": CHAT}}, "data": f"tr:{tid}:{st}"})
press("accepted"); chk("кнопка «Принял»", db.get("trips", tid)["status"] == "accepted")
press("loading"); press("loaded")
bot.handle_message(None, {"chat": {"id": CHAT}, "from": {}, "text": "24,8"})
chk("ввод веса погрузки", db.get("trips", tid)["status"] == "loaded" and db.get("trips", tid)["load_qty"] == 24.8, db.get("trips", tid))
press("on_way"); press("delivered")
bot.handle_message(None, {"chat": {"id": CHAT}, "from": {}, "text": "24.6"})
t = db.get("trips", tid)
chk("выгрузка → ТН", t["status"] in ("delivered", "closed") and t["unload_qty"] == 24.6 and t.get("tn_number"), t)
bot.handle_message(None, {"chat": {"id": CHAT}, "from": {}, "location": {"latitude": 55.7, "longitude": 37.6}})
chk("геопозиция записана", db.q1("SELECT id FROM gps_points WHERE driver_id=?", (drv["id"],)))
# чужой человек -> лид
n0 = db.q1("SELECT COUNT(*) n FROM leads")["n"]
bot.handle_message(None, {"chat": {"id": 999}, "from": {"first_name": "Аноним"}, "text": "Нужно 3 машины щебня в Подольск, +7 916 000-00-00"})
chk("сообщение незнакомца → лид", db.q1("SELECT COUNT(*) n FROM leads")["n"] == n0 + 1)
# чужой рейс
bot.handle_callback(None, {"id": "y", "message": {"chat": {"id": 999}}, "data": f"tr:{tid}:accepted"})
chk("посторонний не может менять рейс", db.get("trips", tid)["status"] in ("delivered", "closed"))
print(f"\nИТОГО: {ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
