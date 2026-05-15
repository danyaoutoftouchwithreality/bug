"""
Generates ФНС-compatible УПД XML (СЧФДОП, format 5.01)
suitable for upload to Контур.Диадок.

Schema reference: Приказ ФНС России от 19.12.2018 №ММВ-7-15/820@
"""

import uuid
import datetime
import re
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


def _file_id(seller_inn: str, buyer_inn: str, date_str: str) -> str:
    date_compact = date_str.replace('.', '')
    uid = uuid.uuid4().hex.upper()
    return f"ON_NSCHFDOPPR_{seller_inn}_{buyer_inn}_{date_compact}_{uid}"


def _parse_fio(full_name: str) -> tuple[str, str, str]:
    """'Сердюк Наталья Алексеевна' → (фамилия, имя, отчество)"""
    parts = full_name.split()
    fam = parts[0] if len(parts) > 0 else ''
    ima = parts[1] if len(parts) > 1 else ''
    otch = parts[2] if len(parts) > 2 else ''
    return fam, ima, otch


def generate_xml(data: dict) -> str:
    """
    data keys (all str, required unless marked optional):
        invoice_number, invoice_date (DD.MM.YYYY),
        seller_name, seller_inn, seller_kpp, seller_address,
        buyer_name, buyer_inn, buyer_kpp (optional), buyer_address,
        currency_code,
        shipment_doc_name (optional), shipment_doc_number (optional), shipment_doc_date (optional),
        items: list of dicts with keys:
            num, name, description (optional), unit_code, unit_name,
            qty, price, amount_no_vat, vat_rate, vat_amount, amount_with_vat
        total_no_vat, total_vat, total_with_vat,
        signer_name (optional)
    """
    seller_inn = data.get('seller_inn', '')
    buyer_inn = data.get('buyer_inn', '')
    invoice_date = data.get('invoice_date', '')

    # ── Корень ────────────────────────────────────────────────────────────
    root = Element('Файл')
    root.set('ИдФайл', _file_id(seller_inn, buyer_inn, invoice_date))
    root.set('ВерсПрог', '1.0')
    root.set('ВерсФорм', '5.01')

    # ── Документ ──────────────────────────────────────────────────────────
    now = datetime.datetime.now()
    doc = SubElement(root, 'Документ')
    doc.set('КНД', '1115131')
    # СЧФДОП = счёт-фактура + передаточный документ (акт)
    doc.set('Функция', 'СЧФДОП')
    doc.set('ПоВидОпер', '01')
    doc.set('ДатаИнфПр', now.strftime('%d.%m.%Y'))
    doc.set('ВремИнфПр', now.strftime('%H.%M.%S'))
    doc.set('НаимЭконСубСост', data.get('seller_name', ''))

    # ── СвСчФакт ──────────────────────────────────────────────────────────
    sv_sf = SubElement(doc, 'СвСчФакт')
    sv_sf.set('НомерСчФ', data.get('invoice_number', ''))
    sv_sf.set('ДатаСчФ', invoice_date)
    sv_sf.set('КодОКВ', data.get('currency_code', '643'))

    # Продавец
    sv_prod = SubElement(sv_sf, 'СвПрод')
    id_prod = SubElement(sv_prod, 'ИдСв')
    seller_kpp = data.get('seller_kpp', '')
    sv_yul = SubElement(id_prod, 'СвЮЛ')
    sv_yul.set('НаимОрг', data.get('seller_name', ''))
    sv_yul.set('ИННЮЛ', seller_inn)
    if seller_kpp:
        sv_yul.set('КПП', seller_kpp)
    addr_prod = SubElement(sv_prod, 'Адрес')
    adr1 = SubElement(addr_prod, 'АдрИнф')
    adr1.set('КодСтр', '643')
    adr1.set('АдрТекст', data.get('seller_address', ''))

    # Покупатель
    sv_pokup = SubElement(sv_sf, 'СвПокуп')
    id_pokup = SubElement(sv_pokup, 'ИдСв')
    buyer_kpp = data.get('buyer_kpp', '')
    buyer_name = data.get('buyer_name', '')

    if len(buyer_inn) == 12 and not buyer_kpp:
        # ИП — используем СвИП + ФИО
        sv_ip = SubElement(id_pokup, 'СвИП')
        sv_ip.set('ИННФЛ', buyer_inn)
        raw_fio = re.sub(r'^Индивидуальный предприниматель\s+', '', buyer_name).strip()
        fam, ima, otch = _parse_fio(raw_fio)
        fio = SubElement(sv_ip, 'ФИО')
        fio.set('Фамилия', fam)
        fio.set('Имя', ima)
        if otch:
            fio.set('Отчество', otch)
    else:
        sv_yul2 = SubElement(id_pokup, 'СвЮЛ')
        sv_yul2.set('НаимОрг', buyer_name)
        sv_yul2.set('ИННЮЛ', buyer_inn)
        if buyer_kpp:
            sv_yul2.set('КПП', buyer_kpp)

    addr_pokup = SubElement(sv_pokup, 'Адрес')
    adr2 = SubElement(addr_pokup, 'АдрИнф')
    adr2.set('КодСтр', '643')
    adr2.set('АдрТекст', data.get('buyer_address', ''))

    # Документ об отгрузке
    sdoc_num = data.get('shipment_doc_number', '')
    if sdoc_num:
        dok = SubElement(sv_sf, 'ДокПодтвОтгр')
        dok.set('НаимДокОтгр', data.get('shipment_doc_name', 'АКТ ОКАЗАННЫХ УСЛУГ'))
        dok.set('НомДокОтгр', sdoc_num)
        dok.set('ДатаДокОтгр', data.get('shipment_doc_date', invoice_date))

    # ── ТаблСчФакт ────────────────────────────────────────────────────────
    tabl = SubElement(doc, 'ТаблСчФакт')

    for item in data.get('items', []):
        sv_tov = SubElement(tabl, 'СведТов')
        sv_tov.set('НомСтр', str(item.get('num', '1')))
        # Если есть описание контракта — включаем в наименование
        name = item.get('name', '')
        desc = item.get('description', '')
        sv_tov.set('НаимТов', f"{name}. {desc}" if desc else name)
        sv_tov.set('ОКЕИ_Тов', item.get('unit_code', ''))
        sv_tov.set('КолТов', item.get('qty', ''))
        sv_tov.set('ЦенаТов', item.get('price', ''))
        sv_tov.set('СтТовБезНДС', item.get('amount_no_vat', ''))

        vat_rate = item.get('vat_rate', '')
        if vat_rate.upper() in ('БЕЗ НДС', 'БЕЗ_НДС'):
            sv_tov.set('НалСт', 'без НДС')
        else:
            sv_tov.set('НалСт', vat_rate)

        sv_tov.set('СумНал', item.get('vat_amount', ''))
        sv_tov.set('СтТовУчНал', item.get('amount_with_vat', ''))

        akciz = SubElement(sv_tov, 'АкцизТов')
        SubElement(akciz, 'НеАкциз')

        SubElement(sv_tov, 'СведПроисх')

    vsego = SubElement(tabl, 'ВсегоОпл')
    vsego.set('СтТовБезНДСВсего', data.get('total_no_vat', ''))
    vsego.set('СумНалВсего', data.get('total_vat', ''))
    vsego.set('СтТовУчНалВсего', data.get('total_with_vat', ''))

    # ── СвПродПод ────────────────────────────────────────────────────────
    sv_pod = SubElement(doc, 'СвПродПод')
    podp = SubElement(sv_pod, 'ПодпПрод')
    podp.set('ДолжПодп', 'Руководитель организации')
    signer = data.get('signer_name', '')
    if signer:
        podp.set('ФИОПодп', signer)

    # ── Форматируем ───────────────────────────────────────────────────────
    raw = tostring(root, encoding='unicode')
    dom = minidom.parseString(raw)
    pretty = dom.toprettyxml(indent='  ', encoding=None)
    # minidom добавляет лишнюю строку декларации — заменим на нашу
    lines = pretty.split('\n')
    if lines[0].startswith('<?xml'):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    return '\n'.join(lines)
