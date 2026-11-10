"""Панель руководителя, сводка, заявка голосом (текст и аудио), бот: черновик → кнопка → заявка.
Запуск на тестовой базе после e2e:
  EGM_DATA=<папка> python tests/owner_test.py http://localhost:8077 <пароль admin> [аудиофайл.wav]"""
import sys, os, httpx
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE, PW = sys.argv[1], sys.argv[2]
AUDIO = sys.argv[3] if len(sys.argv) > 3 else None
c = httpx.Client(base_url=BASE, timeout=300)
ok = fail = 0


def chk(n, cond, x=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print("OK  " if cond else "FAIL", n, "" if cond else str(x)[:400])


c.post("/api/login", json={"login": "admin", "password": PW})
p = c.get("/api/owner").json()
chk("панель: продажи, деньги, техника, проблемы", all(k in p for k in ("sales", "money", "fleet", "problems", "managers")), p)
chk("панель: прогноз месяца посчитан", isinstance(p["sales"]["forecast"], (int, float)), p["sales"])
chk("панель: светофор у каждой машины", p["fleet"] and all(v["light"] in "ryg" for v in p["fleet"]), p["fleet"][:2])
d = c.get("/api/owner/digest").json()
chk("утренняя сводка", "сводка" in d["text"] and "Месяц" in d["text"], d)

st = c.get("/api/e/sites?limit=50").json()["rows"][0]
cl = c.get(f"/api/e/clients/{st['client_id']}").json()
mt = c.get("/api/e/materials?limit=50").json()["rows"]
m = next(x for x in mt if not x.get("is_service"))
phrase = f"{cl['name']}, {st['name']}, {m['name']}, три машины на завтра"
r = c.post("/api/voice/parse", json={"text": phrase}).json()
chk("разбор фразы: клиент", r.get("client_id") == cl["id"], r)
chk("разбор фразы: материал", r.get("material_id") == m["id"], r)
chk("разбор фразы: 3 машины → тонны", r.get("qty") and r["unit"] == "t" and r.get("trips") == 3, r)
chk("разбор фразы: завтра", bool(r.get("date")), r)
r2 = c.post("/api/voice/parse", json={"text": f"{m['name']} 40 кубов послезавтра"}).json()
chk("разбор: кубы, без клиента → не готово", r2.get("unit") == "m3" and r2.get("qty") == 40 and not r2["ready"] and "клиент" in r2["missing"], r2)
o = c.post("/api/voice/order", json={"text": phrase, "site_id": st["id"]}).json()
chk("голосом → заявка создана", o.get("id"), o)
oo = c.get(f"/api/e/orders/{o['id']}").json()
chk("заявка: источник и комментарий", "Голосом" in (oo.get("comment") or ""), oo)
bad = c.post("/api/voice/order", json={"text": "просто привет"})
chk("неполная заявка не создаётся", bad.status_code == 400, bad.text)

# права: диспетчеру панель руководителя закрыта
c2 = httpx.Client(base_url=BASE, timeout=30)
users = c.get("/api/e/users?limit=100").json()["rows"]
disp = next((u for u in users if u["role"] == "dispatcher"), None)
if disp:
    c.put(f"/api/e/users/{disp['id']}", json={"password": "Test-Disp-123"})
    c2.post("/api/login", json={"login": disp["login"], "password": "Test-Disp-123"})
    chk("диспетчер не видит панель руководителя", c2.get("/api/owner").status_code == 403)
    chk("диспетчер может голосовую заявку", c2.post("/api/voice/parse", json={"text": "песок"}).status_code == 200)

if AUDIO:
    with open(AUDIO, "rb") as f:
        a = c.post("/api/voice/audio", files={"file": ("v.wav", f, "audio/wav")})
    chk("аудио → текст (локальное распознавание)", a.status_code == 200 and len(a.json().get("text", "")) > 20, a.text[:300])
    print("   расслышано:", a.json().get("text", "")[:120])

# бот: сотрудник пишет/говорит заявку -> черновик -> кнопка
from app import db, bot
SENT = []
bot.api = lambda cc, method, **kw: (SENT.append((method, kw)), {"ok": True, "result": {}})[1]
adm = db.q1("SELECT * FROM users WHERE role='admin'")
db.update("users", adm["id"], {"tg_chat": "777001"})
n0 = db.val("SELECT COUNT(*) FROM orders")
bot.handle_message(None, {"chat": {"id": 777001}, "from": {}, "text": phrase.replace(cl["name"], cl["name"] + " " + st["name"])})
chk("бот: черновик с кнопкой", SENT and "Черновик" in SENT[-1][1].get("text", "") and SENT[-1][1].get("reply_markup"), SENT[-1:])
bot.handle_callback(None, {"id": "z", "message": {"chat": {"id": 777001}}, "data": "vo:ok"})
chk("бот: кнопка → заявка", db.val("SELECT COUNT(*) FROM orders") == n0 + 1 and "создана" in SENT[-1][1]["text"], SENT[-1:])
bot.handle_message(None, {"chat": {"id": 777001}, "from": {}, "text": "/svodka"})
chk("бот: /svodka руководителю", "сводка" in SENT[-1][1]["text"], SENT[-1:])
bot.voice_text = lambda cc, msg: "Машина сломалась на Каширке, нужен эвакуатор"
drv = db.q1("SELECT * FROM drivers WHERE tg_chat IS NOT NULL AND tg_chat!='' LIMIT 1")
if drv:
    bot.handle_message(None, {"chat": {"id": int(drv["tg_chat"])}, "from": {}, "voice": {"file_id": "x"}})
    chk("бот: голосовое водителя → диспетчеру", db.q1("SELECT id FROM notifications WHERE text LIKE '%эвакуатор%'"), SENT[-1:])
print(f"\nИТОГО: {ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
