"""Печатные формы: ТН (ПП РФ №2200, прил. 4), путевой лист (приказ Минтранса №390), счёт, УПД, акт сверки.
HTML для печати / «Сохранить как PDF». Юридическую силу электронному документу даёт только подпись через оператора ЭДО."""
import html, datetime
from . import db, logic

CSS = """<style>
@page{size:A4;margin:12mm}body{font:11px/1.35 Arial,sans-serif;color:#000;margin:0}
h1{font-size:15px;margin:4px 0 8px;text-align:center}h2{font-size:12px;margin:10px 0 4px;background:#eee;padding:3px 5px}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #000;padding:3px 4px;vertical-align:top}th{background:#f2f2f2;font-weight:600}
.nb td{border:none;padding:2px 0}.r{text-align:right}.c{text-align:center}.sm{font-size:9px;color:#333}.sig{height:28px}
.bar{position:sticky;top:0;background:#141518;color:#fff;padding:8px 12px;font:13px Arial;display:flex;gap:10px;align-items:center}
.bar button{background:#E3120B;color:#fff;border:0;padding:6px 14px;border-radius:6px;font-weight:600;cursor:pointer}
.note{border:1px dashed #E3120B;padding:6px;margin:8px 0;font-size:10px}
.pg{padding:10px 14px}@media print{.bar{display:none}.pg{padding:0}}
</style>"""


def e(v):
    return html.escape("" if v is None else str(v))


def money(v):
    return f"{(v or 0):,.2f}".replace(",", " ").replace(".", ",")


def dru(d):
    return f"{d[8:10]}.{d[5:7]}.{d[0:4]}" if d and len(d) >= 10 else (d or "")


def company():
    g = db.setting
    return dict(name=g("company_name", "ООО «ЕГМ»"), inn=g("company_inn", ""), kpp=g("company_kpp", ""), ogrn=g("company_ogrn", ""),
                addr=g("company_addr", "проверить: юр. адрес"), bank=g("company_bank", "проверить: банк и р/с"),
                phone=g("company_phone", ""), director=g("company_director", "проверить: ФИО директора"),
                accountant=g("company_accountant", ""))


def party(c):
    if not c:
        return ""
    return ", ".join(x for x in [c.get("name"), c.get("inn") and f"ИНН {c['inn']}", c.get("kpp") and f"КПП {c['kpp']}",
                                 c.get("legal_addr") or c.get("addr")] if x)


def page(title, body, note=True):
    n = ('<div class="note">Документ сформирован системой ЕГМ. Для юридически значимого электронного документооборота '
         '(ЭТрН, ЭПЛ, УПД) файл подписывается КЭП и отправляется через оператора ЭДО, который подключается отдельно.</div>') if note else ""
    return (f"<!doctype html><html lang=ru><meta charset=utf-8><title>{e(title)}</title>{CSS}"
            f"<div class=bar><b>{e(title)}</b><button onclick='print()'>Печать / PDF</button></div><div class=pg>{body}{n}</div></html>")


def tn(trip_id):
    t, o, site, src = logic.trip_card(trip_id)
    co = company()
    c = db.get("clients", o["client_id"]) or {}
    m = db.get("materials", o["material_id"]) or {}
    v = db.get("vehicles", t.get("vehicle_id")) or {}
    d = db.get("drivers", t.get("driver_id")) or {}
    doc = db.q1("SELECT * FROM documents WHERE kind='tn' AND trip_id=?", (trip_id,)) or {}
    carrier = co
    if v.get("owner") == "hired" and v.get("carrier_id"):
        ca = db.get("carriers", v["carrier_id"]) or {}
        carrier = dict(name=ca.get("name"), inn=ca.get("inn"), addr="", phone=ca.get("phone"))

    def row(n, title, content):
        return f"<h2>{n}. {title}</h2><table><tr><td>{content}</td></tr></table>"
    b = f"""<table class=nb><tr><td>Транспортная накладная</td><td class=r>Дата {dru(doc.get('date') or t['date'])} &nbsp; № {e(t.get('tn_number') or doc.get('number'))}</td></tr>
    <tr><td class=sm colspan=2>Форма по Постановлению Правительства РФ от 21.12.2020 №2200 (приложение 4)</td></tr></table>
    {row(1, 'Грузоотправитель', e(party(dict(name=co['name'], inn=co['inn'], kpp=co['kpp'], addr=co['addr']))) + ' тел. ' + e(co['phone']))}
    {row(2, 'Грузополучатель', e(party(c)) + '<br>' + e(site.get('contact') or '') + ' ' + e(site.get('phone') or ''))}
    {row(3, 'Наименование груза', f"{e(m.get('name'))}, навалом. Масса брутто {t.get('load_qty') or t['plan_qty']} т. Класс опасности: не опасный")}
    {row(4, 'Сопроводительные документы на груз', 'Заявка ' + e(o['number']) + (', документ поставщика' if t.get('supplier_id') else ''))}
    {row(5, 'Указания грузоотправителя', 'Перевозка навалом в кузове самосвала. Взвешивание при погрузке.')}
    {row(6, 'Приём груза', f"Адрес погрузки: {e(src.get('address') or src.get('name'))}<br>Дата и время подачи: {dru(t['date'])} {e((t.get('ts_loaded') or '')[11:16])}<br>Масса груза: {t.get('load_qty') or t['plan_qty']} т")}
    {row(7, 'Сдача груза', f"Адрес выгрузки: {e(site.get('address'))}<br>Дата и время: {e((t.get('ts_delivered') or '')[:16])}<br>Масса принятого груза: {e(t.get('unload_qty') or '')} т")}
    {row(8, 'Условия перевозки', 'Сроки — по заявке ' + e(o['number']) + (f", окно {e(o.get('time_from'))}–{e(o.get('time_to'))}" if o.get('time_from') else ''))}
    {row(9, 'Информация о принятии заказа к исполнению', 'Принят: ' + e(carrier.get('name')))}
    {row(10, 'Перевозчик', e(party(carrier)) + '<br>Водитель: ' + e(d.get('name')) + ', ВУ ' + e(d.get('license_no')) + ', тел. ' + e(d.get('phone')))}
    {row(11, 'Транспортное средство', f"{e(v.get('model'))}, рег. номер {e(v.get('plate'))}, тип: самосвал, грузоподъёмность {e(v.get('capacity_t'))} т. Принадлежность: {'собственность' if v.get('owner')!='hired' else 'наёмное'}")}
    {row(12, 'Оговорки и замечания перевозчика', '&nbsp;')}
    {row(13, 'Прочие условия', '&nbsp;')}
    {row(14, 'Переадресовка', '&nbsp;')}
    {row(15, 'Стоимость услуг перевозчика и порядок расчёта', 'По договору с грузополучателем')}
    {row(16, 'Дата составления, подписи сторон', '<table class=nb><tr><td>Грузоотправитель ______________</td><td>Перевозчик (водитель) ______________</td><td>Грузополучатель ______________</td></tr></table>')}
    {row(17, 'Отметки грузоотправителей, грузополучателей, перевозчиков', '&nbsp;')}"""
    return page(f"ТН {t.get('tn_number') or ''}", b)


def waybill(wb_id):
    w = db.get("waybills", wb_id)
    co = company()
    v = db.get("vehicles", w["vehicle_id"]) or {}
    d = db.get("drivers", w["driver_id"]) or {}
    trips = db.q("SELECT t.*, o.number onum FROM trips t JOIN orders o ON o.id=t.order_id WHERE t.waybill_id=? ORDER BY t.id", (wb_id,))
    rows = "".join(f"<tr><td>{e(t['number'])}</td><td>{e(t['onum'])}</td><td>{e(logic.trip_card(t['id'])[3].get('name'))}</td>"
                   f"<td>{e(logic.trip_card(t['id'])[2].get('address'))}</td><td class=r>{e(t.get('unload_qty') or t['plan_qty'])}</td>"
                   f"<td>{e(t.get('tn_number'))}</td></tr>" for t in trips)
    b = f"""<h1>ПУТЕВОЙ ЛИСТ № {e(w['number'])}</h1>
    <p class=c>Срок действия: {dru(w['date'])} (одна смена). Состав реквизитов — приказ Минтранса России от 05.05.2023 №390</p>
    <table><tr><th style="width:34%">Собственник (владелец) ТС</th><td>{e(party(dict(name=co['name'], inn=co['inn'], addr=co['addr'])))}, ОГРН {e(co['ogrn'])}, тел. {e(co['phone'])}</td></tr>
    <tr><th>Транспортное средство</th><td>{e(v.get('model'))}, тип: грузовой самосвал, гос. рег. знак <b>{e(v.get('plate'))}</b></td></tr>
    <tr><th>Водитель</th><td>{e(d.get('name'))}, ВУ № {e(d.get('license_no'))}</td></tr>
    <tr><th>Вид перевозки</th><td>Перевозка грузов для собственных нужд / коммерческая перевозка (по договору)</td></tr></table>
    <h2>Показания одометра и топливо</h2>
    <table><tr><th></th><th>Дата, время</th><th>Одометр, км</th><th>Топливо, л</th></tr>
    <tr><td>Выезд с парковки</td><td>{dru(w['date'])} ____:____</td><td class=r>{e(w.get('odo_start'))}</td><td class=r>{e(w.get('fuel_start'))}</td></tr>
    <tr><td>Выдано топлива</td><td></td><td></td><td class=r>{e(w.get('fuel_issued'))}</td></tr>
    <tr><td>Заезд на парковку</td><td>{dru(w['date'])} ____:____</td><td class=r>{e(w.get('odo_end'))}</td><td class=r>{e(w.get('fuel_end'))}</td></tr></table>
    <h2>Медицинские осмотры и техконтроль</h2>
    <table><tr><th>Предрейсовый медосмотр</th><td class=sig>{e(w.get('med_pre')) or 'Допущен к исполнению трудовых обязанностей. Дата, время, ФИО, подпись медработника: ____________________'}</td></tr>
    <tr><th>Послерейсовый медосмотр</th><td class=sig>{e(w.get('med_post')) or 'Прошёл. Дата, время, ФИО, подпись: ____________________'}</td></tr>
    <tr><th>Предрейсовый контроль технического состояния</th><td class=sig>{e(w.get('tech_check')) or 'Выпуск на линию разрешён. Дата, время, ФИО контролёра, подпись: ____________________'}</td></tr></table>
    <h2>Задание водителю</h2>
    <table><tr><th>Рейс</th><th>Заявка</th><th>Погрузка</th><th>Выгрузка</th><th>Тонн</th><th>ТН</th></tr>{rows or '<tr><td colspan=6>—</td></tr>'}</table>
    <p style="margin-top:16px">Диспетчер ______________ &nbsp;&nbsp; Водитель ______________ &nbsp;&nbsp; Механик ______________</p>"""
    return page(f"Путевой лист {w['number']}", b)


def invoice(inv_id, kind="invoice"):
    i = db.get("invoices", inv_id)
    co = company()
    c = db.get("clients", i["client_id"]) or {}
    lines = db.q("SELECT * FROM invoice_lines WHERE invoice_id=? ORDER BY id", (inv_id,))
    vat = logic.S("vat_pct", 20.0)
    trs = "".join(f"<tr><td class=c>{n}</td><td>{e(l['name'])}</td><td class=r>{l['qty']:g}</td><td class=c>{e(l['unit'])}</td>"
                  f"<td class=r>{money(l['price'])}</td><td class=r>{money(l['sum'])}</td></tr>" for n, l in enumerate(lines, 1))
    if kind == "upd":
        title = f"Универсальный передаточный документ № {i['number']} от {dru(i['date'])}"
        head = f"""<table class=nb><tr><td style="width:120px"><b>Статус: 1</b><br><span class=sm>1 — счёт-фактура и передаточный документ (акт)</span></td><td>
        <b>{e(title)}</b><br>Продавец: {e(co['name'])}<br>Адрес: {e(co['addr'])}<br>ИНН/КПП продавца: {e(co['inn'])}/{e(co['kpp'])}<br>
        Грузоотправитель: он же<br>Грузополучатель: {e(party(c))}<br>Покупатель: {e(c.get('name'))}<br>Адрес: {e(c.get('legal_addr'))}<br>
        ИНН/КПП покупателя: {e(c.get('inn'))}/{e(c.get('kpp'))}<br>Валюта: российский рубль, 643</td></tr></table>"""
        foot = f"""<table class=nb style="margin-top:14px"><tr><td>Товар (груз) передал / услуги, результаты работ сдал<br>Руководитель ______ {e(co['director'])}<br>Дата отгрузки: {dru(i['period_to'])}</td>
        <td>Товар (груз) получил / услуги, результаты работ принял<br>______________________<br>Дата получения: __________</td></tr></table>"""
    else:
        title = f"Счёт на оплату № {i['number']} от {dru(i['date'])}"
        head = f"""<table><tr><td colspan=2>{e(co['bank'])}<br><span class=sm>Банк получателя</span></td></tr>
        <tr><td>ИНН {e(co['inn'])} &nbsp; КПП {e(co['kpp'])}</td><td>{e(co['name'])}<br><span class=sm>Получатель</span></td></tr></table>
        <h1>{e(title)}</h1><table class=nb><tr><td style="width:90px">Поставщик:</td><td><b>{e(party(dict(name=co['name'], inn=co['inn'], kpp=co['kpp'], addr=co['addr'])))}</b></td></tr>
        <tr><td>Покупатель:</td><td><b>{e(party(c))}</b></td></tr><tr><td>Основание:</td><td>{e(name_contract(i.get('contract_id')))}</td></tr></table>"""
        foot = f"""<p>Оплатить до {dru(i['due_date'])}. Период поставки: {dru(i['period_from'])} — {dru(i['period_to'])}.</p>
        <p style="margin-top:18px">Руководитель ______________ {e(co['director'])} &nbsp;&nbsp;&nbsp; Бухгалтер ______________ {e(co['accountant'])}</p>"""
    b = f"""{head}<table style="margin-top:8px"><tr><th>№</th><th>Товары (работы, услуги)</th><th>Кол-во</th><th>Ед.</th><th>Цена, ₽</th><th>Сумма, ₽</th></tr>{trs}
    <tr><td colspan=5 class=r><b>Итого:</b></td><td class=r><b>{money(i['total'])}</b></td></tr>
    <tr><td colspan=5 class=r>В том числе НДС ({vat:g}%):</td><td class=r>{money(i['vat'])}</td></tr></table>
    <p>Всего наименований {len(lines)}, на сумму {money(i['total'])} ₽</p>{foot}"""
    return page(title, b, note=(kind == "upd"))


def name_contract(cid):
    if not cid:
        return "Основной договор"
    c = db.get("contracts", cid) or {}
    return f"Договор № {c.get('number')} от {dru(c.get('date'))}"


def recon(client_id, date_from, date_to):
    co = company()
    c = db.get("clients", client_id) or {}
    r = logic.reconciliation(client_id, date_from, date_to)
    trs = "".join(f"<tr><td>{dru(x['date'])}</td><td>{e(x['doc'])}</td><td class=r>{money(x['debit']) if x['debit'] else ''}</td>"
                  f"<td class=r>{money(x['credit']) if x['credit'] else ''}</td></tr>" for x in r["rows"])
    sd, sc = sum(x["debit"] for x in r["rows"]), sum(x["credit"] for x in r["rows"])
    b = f"""<h1>Акт сверки взаимных расчётов</h1><p class=c>за период {dru(date_from)} — {dru(date_to)}<br>между {e(co['name'])} и {e(c.get('name'))}</p>
    <table><tr><th>Дата</th><th>Документ</th><th>Дебет, ₽</th><th>Кредит, ₽</th></tr>
    <tr><td colspan=2><b>Сальдо начальное</b></td><td class=r>{money(max(r['opening'], 0))}</td><td class=r>{money(max(-r['opening'], 0))}</td></tr>{trs}
    <tr><td colspan=2><b>Обороты за период</b></td><td class=r>{money(sd)}</td><td class=r>{money(sc)}</td></tr>
    <tr><td colspan=2><b>Сальдо конечное</b></td><td class=r>{money(max(r['closing'], 0))}</td><td class=r>{money(max(-r['closing'], 0))}</td></tr></table>
    <p>На {dru(date_to)} задолженность {'в пользу ' + e(co['name']) if r['closing'] >= 0 else 'в пользу ' + e(c.get('name'))}: <b>{money(abs(r['closing']))} ₽</b></p>
    <table class=nb style="margin-top:20px"><tr><td>От {e(co['name'])}<br><br>______________ {e(co['director'])}</td><td>От {e(c.get('name'))}<br><br>______________</td></tr></table>"""
    return page("Акт сверки", b, note=False)


def payroll_sheet(pid):
    p = db.get("payroll", pid)
    d = db.get("drivers", p["driver_id"]) or {}
    trips = db.q("SELECT * FROM trips WHERE driver_id=? AND status='closed' AND date BETWEEN ? AND ? ORDER BY date", (p["driver_id"], p["period_from"], p["period_to"]))
    trs = "".join(f"<tr><td>{dru(t['date'])}</td><td>{e(t['number'])}</td><td class=r>{e(t.get('unload_qty'))}</td><td class=r>{e(round((t.get('distance_km') or 0)*2))}</td><td class=r>{money(t.get('cost_driver'))}</td></tr>" for t in trips)
    b = f"""<h1>Расчёт оплаты водителя</h1><p class=c>{e(d.get('name'))}, период {dru(p['period_from'])} — {dru(p['period_to'])}</p>
    <table><tr><th>Дата</th><th>Рейс</th><th>Тонн</th><th>Км</th><th>Начислено, ₽</th></tr>{trs}</table>
    <table style="margin-top:8px;width:50%"><tr><td>Начислено сдельно</td><td class=r>{money(p['accrued'])}</td></tr><tr><td>Премия</td><td class=r>{money(p['bonus'])}</td></tr>
    <tr><td>Удержания</td><td class=r>−{money(p['deduction'])}</td></tr><tr><td>Аванс</td><td class=r>−{money(p['advance'])}</td></tr>
    <tr><th>К выплате</th><th class=r>{money(p['total'])}</th></tr></table>
    <p class=sm>Внутренний расчёт. НДФЛ и взносы считаются в бухгалтерии/зарплатной программе.</p>"""
    return page("Расчёт водителя", b, note=False)
