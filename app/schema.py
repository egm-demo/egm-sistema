"""Справочник сущностей ЕГМ: одна схема -> таблицы SQLite, API и формы интерфейса.
Тип поля: s строка, t текст, i целое, n число, m деньги, d дата, dt дата-время, b да/нет,
ph телефон, ref:<сущность>, enum:<список>, pw пароль (не отдаётся наружу).
"""

ENUMS = {
    "role": [("admin", "Администратор"), ("director", "Руководитель"), ("dispatcher", "Диспетчер"),
             ("manager", "Менеджер продаж"), ("accountant", "Бухгалтер"), ("mechanic", "Механик"),
             ("driver", "Водитель"), ("client", "Клиент")],
    "pay_terms": [("prepay", "Предоплата"), ("postpay", "Отсрочка"), ("cash", "Наличные / на месте")],
    "unit": [("t", "т"), ("m3", "м³"), ("trip", "рейс"), ("h", "час"), ("pcs", "шт")],
    "supplier_kind": [("quarry", "Карьер"), ("plant", "Завод / ДСК"), ("trader", "Перекупщик"), ("other", "Прочее")],
    "veh_type": [("dump", "Самосвал"), ("semi", "Полуприцеп-самосвал"), ("loader", "Погрузчик"),
                 ("excavator", "Экскаватор"), ("other", "Другая техника")],
    "veh_status": [("work", "В работе"), ("repair", "В ремонте"), ("idle", "Простой"), ("off", "Списана")],
    "owner": [("own", "Своя"), ("hired", "Наёмная")],
    "drv_pay": [("trip", "За рейс"), ("ton", "За тонну"), ("km", "За км"), ("pct", "% от выручки рейса"), ("day", "За смену")],
    "drv_status": [("work", "Работает"), ("vacation", "Отпуск"), ("sick", "Больничный"), ("fired", "Уволен")],
    "order_status": [("new", "Новая"), ("confirmed", "Подтверждена"), ("planned", "Рейсы созданы"),
                     ("in_work", "Выполняется"), ("done", "Выполнена"), ("canceled", "Отменена")],
    "order_source": [("phone", "Звонок"), ("site", "Сайт"), ("cabinet", "Кабинет клиента"), ("tg", "Telegram"),
                     ("max", "MAX"), ("crm", "Из CRM"), ("import", "Импорт")],
    "trip_status": [("plan", "Запланирован"), ("assigned", "Назначен"), ("accepted", "Принят водителем"),
                    ("loading", "На погрузке"), ("loaded", "Загружен"), ("on_way", "В пути"),
                    ("delivered", "Выгружен"), ("closed", "Закрыт"), ("canceled", "Отменён")],
    "source_kind": [("supplier", "С карьера / поставщика"), ("warehouse", "Со своего склада")],
    "wb_status": [("open", "Открыт"), ("closed", "Закрыт")],
    "doc_kind": [("tn", "Транспортная накладная"), ("waybill", "Путевой лист"), ("invoice", "Счёт"),
                 ("act", "Акт"), ("upd", "УПД"), ("recon", "Акт сверки")],
    "doc_status": [("draft", "Черновик"), ("ready", "Готов к подписи"), ("sent", "Отправлен в ЭДО"),
                   ("signed", "Подписан"), ("rejected", "Отклонён"), ("canceled", "Аннулирован")],
    "inv_status": [("draft", "Черновик"), ("issued", "Выставлен"), ("partial", "Оплачен частично"),
                   ("paid", "Оплачен"), ("canceled", "Аннулирован")],
    "direction": [("in", "Поступление"), ("out", "Списание")],
    "pay_source": [("manual", "Вручную"), ("bank", "Выписка банка"), ("cash", "Касса")],
    "move_kind": [("purchase", "Приход от поставщика"), ("trip", "Отгрузка рейсом"), ("adjust", "Корректировка / инвентаризация")],
    "mnt_kind": [("to", "ТО"), ("repair", "Ремонт"), ("tires", "Шины"), ("insp", "Техосмотр"), ("other", "Прочее")],
    "plan_done": [("plan", "Запланировано"), ("done", "Выполнено")],
    "payroll_status": [("draft", "Черновик"), ("approved", "Утверждена"), ("paid", "Выплачена")],
    "lead_stage": [("new", "Новый"), ("contacted", "Связались"), ("kp", "КП отправлено"),
                   ("nego", "Переговоры"), ("won", "Клиент"), ("lost", "Отказ")],
    "lead_source": [("site", "Сайт"), ("call", "Входящий звонок"), ("cold", "Холодный обзвон"), ("tg", "Telegram"),
                    ("max", "MAX"), ("avito", "Авито"), ("recommend", "Рекомендация"), ("other", "Другое")],
    "purch_paid": [("no", "Не оплачено"), ("partial", "Частично"), ("yes", "Оплачено")],
}

# group -> (иконка, порядок) для меню
E = {}


def ent(name, title, group, fields, title_field="name", order="id DESC", roles_r=None, roles_w=None, hidden=False):
    E[name] = dict(name=name, title=title, group=group, title_field=title_field, order=order,
                   roles_r=roles_r or ["admin", "director"], roles_w=roles_w or ["admin"], hidden=hidden,
                   fields=[dict(zip(("name", "type", "label", "opt"), (f.split("|") + [""])[:4])) for f in fields])


ALL_STAFF = ["admin", "director", "dispatcher", "manager", "accountant", "mechanic"]
OFFICE = ["admin", "director", "dispatcher", "manager", "accountant"]

# ---------- Справочники ----------
ent("clients", "Клиенты", "Продажи", [
    "name|s|Название|req", "inn|s|ИНН", "kpp|s|КПП", "ogrn|s|ОГРН", "legal_addr|s|Юр. адрес",
    "contact|s|Контактное лицо", "phone|ph|Телефон", "email|s|E-mail", "pay_terms|enum:pay_terms|Оплата",
    "delay_days|i|Отсрочка, дней", "credit_limit|m|Кредитный лимит, ₽", "discount_pct|n|Скидка, %",
    "manager_id|ref:users|Менеджер", "tg_chat|s|Telegram chat id|hide", "bank|s|Банк, р/с", "note|t|Примечание"],
    roles_r=OFFICE, roles_w=["admin", "manager", "accountant", "director"])
ent("sites", "Объекты доставки", "Продажи", [
    "client_id|ref:clients|Клиент|req", "name|s|Объект|req", "address|s|Адрес|req", "lat|n|Широта", "lon|n|Долгота",
    "distance_km|n|Плечо от карьера, км", "zone_id|ref:zones|Зона доставки", "contact|s|Приёмщик", "phone|ph|Телефон приёмщика",
    "access|s|Пропуск / подъезд (МКАД, ТТК, СК, ограничения)", "note|t|Примечание"],
    roles_r=OFFICE, roles_w=["admin", "manager", "dispatcher", "director"])
ent("contracts", "Договоры", "Продажи", [
    "client_id|ref:clients|Клиент|req", "number|s|Номер|req", "date|d|Дата", "valid_to|d|Действует до",
    "kind|s|Предмет (поставка, перевозка, услуги)", "delay_days|i|Отсрочка, дней", "credit_limit|m|Лимит, ₽", "note|t|Условия"],
    title_field="number", roles_r=OFFICE, roles_w=["admin", "manager", "accountant", "director"])
ent("materials", "Номенклатура", "Справочники", [
    "name|s|Материал / услуга|req", "unit|enum:unit|Ед. изм.", "density|n|Насыпная плотность, т/м³",
    "base_price|m|Цена продажи за ед., ₽", "vat_pct|n|НДС, %", "is_service|b|Это услуга (вывоз, аренда)", "active|b|Активен"],
    order="name", roles_r=ALL_STAFF, roles_w=["admin", "director", "manager"])
ent("client_prices", "Индивидуальные цены", "Продажи", [
    "client_id|ref:clients|Клиент|req", "material_id|ref:materials|Материал|req", "price|m|Цена за ед., ₽|req", "valid_to|d|Действует до"],
    title_field="price", roles_r=OFFICE, roles_w=["admin", "director", "manager"])
ent("zones", "Зоны доставки", "Справочники", [
    "name|s|Зона|req", "trip_price|m|Доставка за рейс, ₽", "km_price|m|Доставка за км, ₽", "km_from|n|От, км", "km_to|n|До, км", "note|t|Примечание"],
    order="km_from", roles_r=ALL_STAFF, roles_w=["admin", "director"])
ent("suppliers", "Карьеры и поставщики", "Склад и закупки", [
    "name|s|Название|req", "kind|enum:supplier_kind|Тип", "inn|s|ИНН", "address|s|Адрес погрузки", "lat|n|Широта", "lon|n|Долгота",
    "contact|s|Контакт", "phone|ph|Телефон", "hours|s|Режим работы", "delay_days|i|Наша отсрочка, дней", "note|t|Примечание"],
    order="name", roles_r=ALL_STAFF, roles_w=["admin", "director", "accountant", "dispatcher"])
ent("supplier_prices", "Закупочные цены", "Склад и закупки", [
    "supplier_id|ref:suppliers|Поставщик|req", "material_id|ref:materials|Материал|req", "price|m|Цена закупки за т, ₽|req", "valid_from|d|С даты"],
    title_field="price", roles_r=["admin", "director", "accountant", "dispatcher"], roles_w=["admin", "director", "accountant"])
ent("warehouses", "Склады / площадки", "Склад и закупки", [
    "name|s|Название|req", "address|s|Адрес", "lat|n|Широта", "lon|n|Долгота", "note|t|Примечание"],
    order="name", roles_r=ALL_STAFF, roles_w=["admin", "director"])
ent("carriers", "Наёмные перевозчики", "Автопарк", [
    "name|s|Название / ИП|req", "inn|s|ИНН", "phone|ph|Телефон", "rate|m|Ставка за рейс, ₽", "note|t|Примечание"],
    order="name", roles_r=ALL_STAFF, roles_w=["admin", "director", "dispatcher"])
ent("vehicles", "Техника", "Автопарк", [
    "plate|s|Госномер|req", "model|s|Марка, модель", "vtype|enum:veh_type|Тип", "capacity_t|n|Грузоподъёмность, т",
    "volume_m3|n|Объём кузова, м³", "fuel_norm|n|Норма расхода, л/100 км", "year|i|Год", "vin|s|VIN", "sts|s|СТС",
    "owner|enum:owner|Принадлежность", "carrier_id|ref:carriers|Перевозчик (если наёмная)", "status|enum:veh_status|Состояние",
    "odometer|i|Пробег, км", "osago_to|d|ОСАГО до", "insp_to|d|Техосмотр до", "tacho_to|d|Тахограф (калибровка) до",
    "pass_to|d|Пропуск в Москву до", "to_every_km|i|ТО каждые, км", "to_last_km|i|Последнее ТО, км",
    "glonass_id|s|ID трекера ГЛОНАСС/GPS", "note|t|Примечание"],
    title_field="plate", order="plate", roles_r=ALL_STAFF, roles_w=["admin", "director", "mechanic"])
ent("drivers", "Водители", "Автопарк", [
    "name|s|ФИО|req", "phone|ph|Телефон", "license_no|s|ВУ номер", "license_to|d|ВУ до", "med_to|d|Медсправка до",
    "vehicle_id|ref:vehicles|Закреплённая машина", "pay_type|enum:drv_pay|Оплата", "pay_rate|n|Ставка (₽ или %)",
    "status|enum:drv_status|Статус", "tg_chat|s|Telegram chat id|hide", "link_code|s|Код привязки бота|ro", "note|t|Примечание"],
    order="name", roles_r=ALL_STAFF, roles_w=["admin", "director", "dispatcher", "mechanic"])

# ---------- Работа ----------
ent("orders", "Заявки", "Логистика", [
    "number|s|№|ro", "date|d|Дата доставки|req", "time_from|s|Окно с", "time_to|s|Окно до",
    "client_id|ref:clients|Клиент|req", "site_id|ref:sites|Объект|req", "material_id|ref:materials|Материал|req",
    "qty|n|Количество|req", "unit|enum:unit|Ед.", "price|m|Цена за ед., ₽", "delivery|m|Доставка всего, ₽",
    "total|m|Сумма заявки, ₽|ro", "supplier_id|ref:suppliers|Карьер (если задан)", "warehouse_id|ref:warehouses|Склад (если со склада)",
    "status|enum:order_status|Статус", "source|enum:order_source|Источник", "manager_id|ref:users|Менеджер",
    "credit_flag|s|Проверка лимита|ro", "contact|s|Контакт на объекте", "comment|t|Комментарий", "created_at|dt|Создана|ro"],
    title_field="number", order="date DESC, id DESC", roles_r=OFFICE, roles_w=["admin", "director", "dispatcher", "manager"])
ent("trips", "Рейсы", "Логистика", [
    "number|s|№ рейса|ro", "order_id|ref:orders|Заявка|req", "date|d|Дата|req", "vehicle_id|ref:vehicles|Машина",
    "driver_id|ref:drivers|Водитель", "source_kind|enum:source_kind|Откуда", "supplier_id|ref:suppliers|Карьер",
    "warehouse_id|ref:warehouses|Склад", "plan_qty|n|План, т|req", "load_qty|n|Погружено, т", "unload_qty|n|Принято, т",
    "status|enum:trip_status|Статус", "distance_km|n|Расстояние, км", "tn_number|s|№ ТН|ro", "waybill_id|ref:waybills|Путевой лист|ro",
    "revenue|m|Выручка, ₽|ro", "cost_material|m|Материал, ₽|ro", "cost_driver|m|Водитель, ₽|ro", "cost_fuel|m|Топливо, ₽|ro",
    "cost_carrier|m|Наёмный перевозчик, ₽|ro", "margin|m|Маржа, ₽|ro", "ts_assigned|dt|Назначен|ro", "ts_loaded|dt|Загружен|ro",
    "ts_delivered|dt|Выгружен|ro", "photo|s|Фото накладной|ro", "invoice_id|ref:invoices|Счёт|ro", "note|t|Примечание"],
    title_field="number", order="date DESC, id DESC", roles_r=ALL_STAFF, roles_w=["admin", "director", "dispatcher"])
ent("waybills", "Путевые листы", "Логистика", [
    "number|s|№|ro", "date|d|Дата|req", "vehicle_id|ref:vehicles|Машина|req", "driver_id|ref:drivers|Водитель|req",
    "odo_start|i|Одометр при выезде", "odo_end|i|Одометр при возврате", "fuel_start|n|Топливо при выезде, л",
    "fuel_issued|n|Выдано топлива, л", "fuel_end|n|Топливо при возврате, л", "med_pre|s|Предрейсовый медосмотр (кто, время)",
    "med_post|s|Послерейсовый медосмотр", "tech_check|s|Предрейсовый техконтроль (кто, время)", "status|enum:wb_status|Статус",
    "edo_status|enum:doc_status|ЭПЛ / ЭДО", "note|t|Примечание"],
    title_field="number", order="date DESC, id DESC", roles_r=["admin", "director", "dispatcher", "mechanic", "accountant"],
    roles_w=["admin", "director", "dispatcher", "mechanic"])
ent("documents", "Документы", "Документы", [
    "kind|enum:doc_kind|Вид|req", "number|s|№", "date|d|Дата", "client_id|ref:clients|Контрагент", "order_id|ref:orders|Заявка",
    "trip_id|ref:trips|Рейс", "invoice_id|ref:invoices|Счёт", "waybill_id|ref:waybills|Путевой лист", "total|m|Сумма, ₽",
    "status|enum:doc_status|Статус", "edo_id|s|ID в ЭДО|ro", "note|t|Примечание"],
    title_field="number", order="date DESC, id DESC", roles_r=OFFICE, roles_w=["admin", "director", "accountant", "dispatcher"])

# ---------- Финансы ----------
ent("invoices", "Счета", "Финансы", [
    "number|s|№|ro", "date|d|Дата|req", "client_id|ref:clients|Клиент|req", "contract_id|ref:contracts|Договор",
    "period_from|d|Период с", "period_to|d|Период по", "total|m|Сумма, ₽|ro", "vat|m|В т.ч. НДС, ₽|ro", "paid|m|Оплачено, ₽|ro",
    "due_date|d|Оплатить до", "status|enum:inv_status|Статус", "note|t|Примечание"],
    title_field="number", order="date DESC, id DESC", roles_r=["admin", "director", "accountant", "manager"], roles_w=["admin", "director", "accountant"])
ent("invoice_lines", "Строки счёта", "Финансы", [
    "invoice_id|ref:invoices|Счёт|req", "trip_id|ref:trips|Рейс", "name|s|Наименование|req", "qty|n|Кол-во", "unit|s|Ед.",
    "price|m|Цена, ₽", "sum|m|Сумма, ₽"], title_field="name", order="id", hidden=True,
    roles_r=["admin", "director", "accountant", "manager"], roles_w=["admin", "director", "accountant"])
ent("payments", "Платежи", "Финансы", [
    "date|d|Дата|req", "direction|enum:direction|Направление|req", "amount|m|Сумма, ₽|req", "client_id|ref:clients|Клиент",
    "supplier_id|ref:suppliers|Поставщик", "carrier_id|ref:carriers|Перевозчик", "invoice_id|ref:invoices|Счёт", "purchase_id|ref:purchases|Закупка",
    "doc_no|s|№ платёжки", "cp_inn|s|ИНН плательщика/получателя", "purpose|t|Назначение платежа", "source|enum:pay_source|Источник"],
    title_field="doc_no", order="date DESC, id DESC", roles_r=["admin", "director", "accountant"], roles_w=["admin", "director", "accountant"])
ent("purchases", "Закупки материала", "Склад и закупки", [
    "date|d|Дата|req", "supplier_id|ref:suppliers|Поставщик|req", "material_id|ref:materials|Материал|req", "qty|n|Кол-во, т|req",
    "price|m|Цена за т, ₽", "total|m|Сумма, ₽|ro", "warehouse_id|ref:warehouses|На склад (пусто — сразу в рейс)",
    "trip_id|ref:trips|Рейс|ro", "paid|enum:purch_paid|Оплата", "doc_no|s|№ документа поставщика", "note|t|Примечание"],
    title_field="doc_no", order="date DESC, id DESC", roles_r=["admin", "director", "accountant", "dispatcher"], roles_w=["admin", "director", "accountant"])
ent("stock_moves", "Движение по складу", "Склад и закупки", [
    "date|d|Дата|req", "warehouse_id|ref:warehouses|Склад|req", "material_id|ref:materials|Материал|req", "qty|n|Кол-во, т (+ приход, − расход)|req",
    "kind|enum:move_kind|Операция", "price|m|Цена за т, ₽", "purchase_id|ref:purchases|Закупка|ro", "trip_id|ref:trips|Рейс|ro", "note|t|Примечание"],
    title_field="qty", order="date DESC, id DESC", roles_r=["admin", "director", "accountant", "dispatcher"], roles_w=["admin", "director", "accountant"])

# ---------- Автопарк ----------
ent("fuel", "Заправки", "Автопарк", [
    "date|d|Дата|req", "vehicle_id|ref:vehicles|Машина|req", "driver_id|ref:drivers|Водитель", "liters|n|Литры|req", "amount|m|Сумма, ₽",
    "odometer|i|Пробег, км", "station|s|АЗС", "card|s|Топливная карта", "source|s|Источник (вручную / выгрузка карты)"],
    title_field="liters", order="date DESC, id DESC", roles_r=["admin", "director", "mechanic", "accountant", "dispatcher"], roles_w=["admin", "director", "mechanic", "accountant"])
ent("maintenance", "ТО и ремонты", "Автопарк", [
    "vehicle_id|ref:vehicles|Машина|req", "date|d|Дата|req", "kind|enum:mnt_kind|Вид", "status|enum:plan_done|Статус",
    "odometer|i|Пробег, км", "cost|m|Стоимость, ₽", "service|s|Где делали", "works|t|Работы и запчасти", "idle_days|n|Простой, дней"],
    title_field="date", order="date DESC, id DESC", roles_r=["admin", "director", "mechanic", "accountant", "dispatcher"], roles_w=["admin", "director", "mechanic"])
ent("payroll", "Зарплата водителей", "Финансы", [
    "driver_id|ref:drivers|Водитель|req", "period_from|d|С|req", "period_to|d|По|req", "trips|i|Рейсов|ro", "tons|n|Тонн|ro",
    "km|n|Км|ro", "accrued|m|Начислено сдельно, ₽|ro", "bonus|m|Премия, ₽", "deduction|m|Удержания (штрафы, ГСМ), ₽",
    "advance|m|Аванс выдан, ₽", "total|m|К выплате, ₽|ro", "status|enum:payroll_status|Статус", "note|t|Примечание"],
    title_field="period_to", order="period_to DESC, id DESC", roles_r=["admin", "director", "accountant"], roles_w=["admin", "director", "accountant"])
ent("gps_points", "Координаты", "Автопарк", [
    "vehicle_id|ref:vehicles|Машина", "driver_id|ref:drivers|Водитель", "ts|dt|Время", "lat|n|Широта", "lon|n|Долгота", "speed|n|Скорость", "source|s|Источник"],
    title_field="ts", order="ts DESC", hidden=True, roles_r=ALL_STAFF, roles_w=["admin"])

# ---------- CRM ----------
ent("leads", "Лиды и сделки", "Продажи", [
    "name|s|Имя / компания|req", "phone|ph|Телефон", "email|s|E-mail", "inn|s|ИНН", "source|enum:lead_source|Источник",
    "stage|enum:lead_stage|Этап", "material|s|Что нужно", "qty|s|Объём", "address|s|Куда", "amount|m|Потенциал, ₽",
    "manager_id|ref:users|Менеджер", "next_date|d|Следующий контакт", "client_id|ref:clients|Стал клиентом|ro", "note|t|Комментарий",
    "created_at|dt|Создан|ro"], order="id DESC", roles_r=["admin", "director", "manager"], roles_w=["admin", "director", "manager"])
ent("tasks", "Задачи", "Продажи", [
    "title|s|Задача|req", "due|d|Срок", "user_id|ref:users|Ответственный", "entity|s|Связано с|hide", "entity_id|i|ID|hide",
    "done|b|Сделано", "note|t|Подробности"], title_field="title", order="done, due", roles_r=ALL_STAFF, roles_w=ALL_STAFF)

# ---------- Система ----------
ent("users", "Пользователи", "Настройки", [
    "login|s|Логин|req", "name|s|Имя|req", "role|enum:role|Роль|req", "password|pw|Пароль", "phone|ph|Телефон",
    "client_id|ref:clients|Клиент (для роли «Клиент»)", "driver_id|ref:drivers|Водитель (для роли «Водитель»)",
    "tg_chat|s|Telegram chat id|hide", "active|b|Активен"], order="name", roles_r=["admin", "director"], roles_w=["admin"])

SYS_TABLES = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, created TEXT, last TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT, user_id INTEGER, action TEXT, entity TEXT, entity_id INTEGER, data TEXT);
CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY, ts TEXT, user_id INTEGER, entity TEXT, entity_id INTEGER, kind TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, ts TEXT, role TEXT, user_id INTEGER, text TEXT, link TEXT, read INTEGER DEFAULT 0, sent_tg INTEGER DEFAULT 0, kind TEXT);
CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, n INTEGER);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, ts TEXT, channel TEXT, chat TEXT, text TEXT, buttons TEXT, sent INTEGER DEFAULT 0, err TEXT);
"""

SQLT = {"i": "INTEGER", "n": "REAL", "m": "REAL", "b": "INTEGER"}


def col_sql(f):
    t = f["type"]
    if t.startswith("ref:"):
        return "INTEGER"
    return SQLT.get(t, "TEXT")


def ddl():
    out = [SYS_TABLES]
    for e in E.values():
        cols = ", ".join(f'"{f["name"]}" {col_sql(f)}' for f in e["fields"])
        out.append(f'CREATE TABLE IF NOT EXISTS {e["name"]}(id INTEGER PRIMARY KEY, {cols}, _upd TEXT);')
        for f in e["fields"]:
            if f["type"].startswith("ref:") or f["name"] in ("date", "status", "number"):
                out.append(f'CREATE INDEX IF NOT EXISTS ix_{e["name"]}_{f["name"]} ON {e["name"]}("{f["name"]}");')
    return "\n".join(out)


def meta_public():
    return {"enums": {k: v for k, v in ENUMS.items()},
            "entities": {k: {kk: vv for kk, vv in e.items()} for k, e in E.items()}}
