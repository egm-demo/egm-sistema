"""SQLite-хранилище: подключение, общий CRUD, журнал, счётчики, пароли, резервные копии."""
import sqlite3, json, os, hashlib, secrets, datetime, threading, shutil
from . import schema

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("EGM_DATA", os.path.join(BASE, "data"))
DB_PATH = os.path.join(DATA, "egm.db")
_lock = threading.RLock()
_conn = None


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.date.today().isoformat()


def conn():
    global _conn
    if _conn is None:
        os.makedirs(DATA, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=OFF")
        _conn.executescript(schema.ddl())
        _migrate(_conn)
    return _conn


def _migrate(c):
    """Добавляет новые колонки, если схема расширилась после первого запуска."""
    for e in schema.E.values():
        have = {r[1] for r in c.execute(f"PRAGMA table_info({e['name']})")}
        for f in e["fields"]:
            if f["name"] not in have:
                c.execute(f'ALTER TABLE {e["name"]} ADD COLUMN "{f["name"]}" {schema.col_sql(f)}')


def q(sql, args=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def q1(sql, args=()):
    r = q(sql, args)
    return r[0] if r else None


def val(sql, args=(), default=0):
    r = q1(sql, args)
    if not r:
        return default
    v = list(r.values())[0]
    return default if v is None else v


def ex(sql, args=()):
    with _lock:
        cur = conn().execute(sql, args)
        return cur.lastrowid


class tx:
    def __enter__(self):
        _lock.acquire()
        conn().execute("BEGIN")
        return self

    def __exit__(self, et, ev, tb):
        try:
            conn().execute("ROLLBACK" if et else "COMMIT")
        finally:
            _lock.release()


def fields(ent):
    return schema.E[ent]["fields"]


def clean(ent, data, partial=False):
    out = {}
    for f in fields(ent):
        n, t = f["name"], f["type"]
        if n not in data:
            continue
        v = data[n]
        if t == "pw":
            continue
        if v == "" or v is None:
            out[n] = None
            continue
        try:
            if t in ("i",) or t.startswith("ref:"):
                v = int(float(v))
            elif t in ("n", "m"):
                v = round(float(str(v).replace(" ", "").replace(",", ".")), 3)
            elif t == "b":
                v = 1 if v in (1, True, "1", "true", "on", "да", "Да") else 0
            else:
                v = str(v).strip()
        except (ValueError, TypeError):
            raise ValueError(f"Поле «{f['label']}»: неверное значение «{v}»")
        if t.startswith("enum:"):
            allowed = [k for k, _ in schema.ENUMS[t[5:]]]
            if v not in allowed:
                lbl = {l: k for k, l in schema.ENUMS[t[5:]]}
                if v in lbl:
                    v = lbl[v]
                else:
                    raise ValueError(f"Поле «{f['label']}»: значение «{v}» не из списка")
        out[n] = v
    if not partial:
        for f in fields(ent):
            if "req" in f["opt"] and out.get(f["name"]) in (None, ""):
                raise ValueError(f"Заполните поле «{f['label']}»")
    return out


def get(ent, id_):
    return q1(f"SELECT * FROM {ent} WHERE id=?", (id_,))


def insert(ent, data, user_id=None):
    data = {k: v for k, v in data.items() if k in {f["name"] for f in fields(ent)}}
    data["_upd"] = now()
    cols = ", ".join(f'"{k}"' for k in data)
    id_ = ex(f"INSERT INTO {ent}({cols}) VALUES({', '.join('?' * len(data))})", tuple(data.values()))
    audit(user_id, "create", ent, id_, data)
    return id_


def update(ent, id_, data, user_id=None):
    data = {k: v for k, v in data.items() if k in {f["name"] for f in fields(ent)}}
    if not data:
        return
    old = get(ent, id_)
    data["_upd"] = now()
    ex(f"UPDATE {ent} SET {', '.join(f'\"{k}\"=?' for k in data)} WHERE id=?", tuple(data.values()) + (id_,))
    diff = {k: [old.get(k) if old else None, v] for k, v in data.items() if k != "_upd" and (not old or old.get(k) != v)}
    if diff:
        audit(user_id, "update", ent, id_, diff)


def delete(ent, id_, user_id=None):
    old = get(ent, id_)
    ex(f"DELETE FROM {ent} WHERE id=?", (id_,))
    audit(user_id, "delete", ent, id_, old)


def audit(user_id, action, ent, id_, data):
    if ent == "gps_points":
        return
    ex("INSERT INTO audit(ts,user_id,action,entity,entity_id,data) VALUES(?,?,?,?,?,?)",
       (now(), user_id, action, ent, id_, json.dumps(data, ensure_ascii=False, default=str)[:4000]))


def next_no(name, prefix, width=5):
    with _lock:
        c = conn()
        r = c.execute("SELECT n FROM counters WHERE name=?", (name,)).fetchone()
        n = (r[0] if r else 0) + 1
        c.execute("INSERT OR REPLACE INTO counters(name,n) VALUES(?,?)", (name, n))
    return f"{prefix}{n:0{width}d}"


def setting(key, default=None):
    r = q1("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default


def set_setting(key, value):
    ex("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120_000).hex()
    return f"{salt}${h}"


def check_pw(pw, stored):
    if not stored or "$" not in stored:
        return False
    salt = stored.split("$", 1)[0]
    return secrets.compare_digest(hash_pw(pw, salt), stored)


def backup(tag="auto"):
    d = os.path.join(DATA, "backups")
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, f"egm_{datetime.datetime.now():%Y%m%d_%H%M%S}_{tag}.db")
    with _lock:
        dst = sqlite3.connect(fn)
        conn().backup(dst)
        dst.close()
    files = sorted(f for f in os.listdir(d) if f.endswith(".db"))
    for old in files[:-30]:
        os.remove(os.path.join(d, old))
    return fn
