"""
Генерация УПД XML формата 5.03 (ФНС, Приказ ЕД-7-26/303@)
Кодировка: windows-1251, совместимо с Контур.Диадок.
"""
import uuid
import datetime
import re
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


def _file_id(seller_inn, seller_kpp, buyer_inn, buyer_kpp):
    now = datetime.datetime.now().strftime('%Y%m%d')
    uid = str(uuid.uuid4())
    return f"ON_NSCHFDOPPR_{buyer_inn}_{buyer_kpp}_{seller_inn}_{seller_kpp}_{now}_{uid}_0_0_0_0_0_00"


def _parse_fio(full_name: str) -> tuple:
    name = re.sub(r'^Индивидуальный предприниматель\s+', '', full_name).strip()
    parts = name.split()
    return (
        parts[0] if len(parts) > 0 else '',
        parts[1] if len(parts) > 1 else '',
        parts[2] if len(parts) > 2 else '',
    )


def generate_xml(data: dict) -> bytes:
    """
    Возвращает байты в кодировке windows-1251.
    """
    now = datetime.datetime.now()
    seller_inn  = data.get('seller_inn', '')
    seller_kpp  = data.get('seller_kpp', '')
    buyer_inn   = data.get('buyer_inn', '')
    buyer_kpp   = data.get('buyer_kpp', '')

    # ── Корень ────────────────────────────────────────────────────────────
    root = Element('Файл')
    root.set('xmlns:xs',  'http://www.w3.org/2001/XMLSchema')
    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    root.set('ИдФайл',    _file_id(seller_inn, seller_kpp, buyer_inn, buyer_kpp))
    root.set('ВерсФорм',  '5.03')
    root.set('ВерсПрог',  'PDF2XML 1.0')

    # ── Документ ──────────────────────────────────────────────────────────
    doc = SubElement(root, 'Документ')
    doc.set('КНД',            '1115131')
    doc.set('Функция',        'ДОП')
    doc.set('ПоФактХЖ',       'Документ об отгрузке товаров (выполнении работ), передаче имущественных прав (документ об оказании услуг)')
    doc.set('НаимДокОпр',     'Документ об отгрузке товаров (выполнении работ), передаче имущественных прав (Документ об оказании услуг)')
    doc.set('ДатаИнфПр',      now.strftime('%d.%m.%Y'))
    doc.set('ВремИнфПр',      now.strftime('%H.%M.%S'))
    doc.set('НаимЭконСубСост', f'{data.get("seller_name", "")}, ИНН/КПП {seller_inn}/{seller_kpp}')

    # ── СвСчФакт ──────────────────────────────────────────────────────────
    sv_sf = SubElement(doc, 'СвСчФакт')
    sv_sf.set('НомерДок', data.get('invoice_number', ''))
    sv_sf.set('ДатаДок',  data.get('invoice_date', ''))

    # Продавец
    sv_prod = SubElement(sv_sf, 'СвПрод')
    if data.get('seller_okpo'):
        sv_prod.set('ОКПО', data['seller_okpo'])

    id_prod = SubElement(sv_prod, 'ИдСв')
    sv_yul = SubElement(id_prod, 'СвЮЛУч')
    sv_yul.set('НаимОрг', data.get('seller_name', ''))
    sv_yul.set('ИННЮЛ',   seller_inn)
    sv_yul.set('КПП',     seller_kpp)

    addr_prod = SubElement(sv_prod, 'Адрес')
    adr1 = SubElement(addr_prod, 'АдрИнф')
    adr1.set('КодСтр',   '643')
    adr1.set('НаимСтран', 'РОССИЯ')
    adr1.set('АдрТекст',  data.get('seller_address', ''))

    # Банковские реквизиты продавца (если заполнены)
    if data.get('seller_bank_account'):
        bank_rekv = SubElement(sv_prod, 'БанкРекв')
        bank_rekv.set('НомерСчета', data.get('seller_bank_account', ''))
        sv_bank = SubElement(bank_rekv, 'СвБанк')
        sv_bank.set('НаимБанк', data.get('seller_bank_name', ''))
        sv_bank.set('БИК',      data.get('seller_bank_bik', ''))
        if data.get('seller_bank_korr'):
            sv_bank.set('КорСчет', data.get('seller_bank_korr', ''))

    # Документ-основание отгрузки
    if data.get('shipment_doc_number'):
        dok = SubElement(sv_sf, 'ДокПодтвОтгрНом')
        dok.set('РеквНаимДок',  data.get('shipment_doc_name', 'Универсальный передаточный документ'))
        dok.set('РеквНомерДок', data.get('shipment_doc_number', ''))
        dok.set('РеквДатаДок',  data.get('shipment_doc_date', data.get('invoice_date', '')))

    # Покупатель
    sv_pokup = SubElement(sv_sf, 'СвПокуп')
    if data.get('buyer_okpo'):
        sv_pokup.set('ОКПО', data['buyer_okpo'])

    id_pokup = SubElement(sv_pokup, 'ИдСв')

    if len(buyer_inn) == 12 and not buyer_kpp:
        # ИП
        sv_ip = SubElement(id_pokup, 'СвИП')
        sv_ip.set('ИННФЛ', buyer_inn)
        fam, ima, otch = _parse_fio(data.get('buyer_name', ''))
        fio = SubElement(sv_ip, 'ФИО')
        fio.set('Фамилия', fam)
        fio.set('Имя',     ima)
        if otch:
            fio.set('Отчество', otch)
    else:
        sv_yul2 = SubElement(id_pokup, 'СвЮЛУч')
        sv_yul2.set('НаимОрг', data.get('buyer_name', ''))
        sv_yul2.set('ИННЮЛ',   buyer_inn)
        if buyer_kpp:
            sv_yul2.set('КПП', buyer_kpp)

    addr_pokup = SubElement(sv_pokup, 'Адрес')
    adr2 = SubElement(addr_pokup, 'АдрИнф')
    adr2.set('КодСтр',    '643')
    adr2.set('НаимСтран', 'РОССИЯ')
    adr2.set('АдрТекст',  data.get('buyer_address', ''))

    # Валюта
    den_izm = SubElement(sv_sf, 'ДенИзм')
    den_izm.set('КодОКВ',  data.get('currency_code', '643'))
    den_izm.set('НаимОКВ', 'Российский рубль')
    den_izm.set('КурсВал', '1.00')

    # ── ТаблСчФакт ────────────────────────────────────────────────────────
    tabl = SubElement(doc, 'ТаблСчФакт')

    for item in data.get('items', []):
        sv_tov = SubElement(tabl, 'СведТов')
        sv_tov.set('НомСтр',      str(item.get('num', '1')))
        sv_tov.set('НаимТов',     item.get('name', ''))
        sv_tov.set('ОКЕИ_Тов',    item.get('unit_code', ''))
        sv_tov.set('НаимЕдИзм',   item.get('unit_name', ''))
        sv_tov.set('КолТов',      item.get('qty', ''))
        sv_tov.set('ЦенаТов',     item.get('price', ''))
        sv_tov.set('СтТовБезНДС', item.get('amount_no_vat', ''))
        sv_tov.set('НалСт',       item.get('vat_rate', ''))
        sv_tov.set('СтТовУчНал',  item.get('amount_with_vat', ''))

        # Акциз
        akciz = SubElement(sv_tov, 'Акциз')
        bez = SubElement(akciz, 'БезАкциз')
        bez.text = 'без акциза'

        # СумНал — вложенный элемент
        sum_nal_outer = SubElement(sv_tov, 'СумНал')
        sum_nal_inner = SubElement(sum_nal_outer, 'СумНал')
        sum_nal_inner.text = item.get('vat_amount', '')

    # ВсегоОпл
    vsego = SubElement(tabl, 'ВсегоОпл')
    vsego.set('СтТовБезНДСВсего',  data.get('total_no_vat', ''))
    vsego.set('СтТовУчНалВсего',   data.get('total_with_vat', ''))
    vsego.set('КолНеттоВс',        _sum_qty(data.get('items', [])))
    sum_nal_vsego = SubElement(vsego, 'СумНалВсего')
    sn = SubElement(sum_nal_vsego, 'СумНал')
    sn.text = data.get('total_vat', '')

    # ── СвПродПер ────────────────────────────────────────────────────────
    sv_prod_per = SubElement(doc, 'СвПродПер')
    sv_per = SubElement(sv_prod_per, 'СвПер')
    sv_per.set('СодОпер',  data.get('transfer_content', 'Услуги оказаны в полном объеме'))
    sv_per.set('ВидОпер',  data.get('transfer_type', 'Продажа'))
    sv_per.set('ДатаПер',  data.get('invoice_date', ''))

    # Основание передачи (договор)
    if data.get('basis_doc_number'):
        osn = SubElement(sv_per, 'ОснПер')
        osn.set('РеквНаимДок',  data.get('basis_doc_name', ''))
        osn.set('РеквНомерДок', data.get('basis_doc_number', ''))
        osn.set('РеквДатаДок',  data.get('basis_doc_date', ''))

    # Подписант со стороны продавца
    signer_name = data.get('signer_name', '')
    if signer_name:
        sv_lic = SubElement(sv_per, 'СвЛицПер')
        rab = SubElement(sv_lic, 'РабОргПрод')
        rab.set('Должность', data.get('signer_position', 'Генеральный директор'))
        fam, ima, otch = _parse_fio(signer_name)
        fio = SubElement(rab, 'ФИО')
        fio.set('Фамилия', fam)
        fio.set('Имя',     ima)
        if otch:
            fio.set('Отчество', otch)

    # ── Подписант ─────────────────────────────────────────────────────────
    podpisant = SubElement(doc, 'Подписант')
    podpisant.set('ТипПодпис', '2')
    podpisant.set('СпосПодтПолном', '1')
    fio_podp = SubElement(podpisant, 'ФИО')
    fam, ima, otch = _parse_fio(signer_name) if signer_name else ('-', '-', '')
    fio_podp.set('Фамилия', fam)
    fio_podp.set('Имя',     ima)
    if otch:
        fio_podp.set('Отчество', otch)

    # ── Сериализация в windows-1251 ───────────────────────────────────────
    raw = tostring(root, encoding='unicode')
    dom = minidom.parseString(raw)
    pretty = dom.toprettyxml(indent='\t', encoding=None)
    # Убираем лишнюю декларацию minidom
    lines = pretty.split('\n')
    if lines[0].startswith('<?xml'):
        lines = lines[1:]
    xml_str = '<?xml version="1.0" encoding="windows-1251"?>\n' + '\n'.join(lines)
    return xml_str.encode('windows-1251')


def _sum_qty(items: list) -> str:
    total = sum(float(i.get('qty', 0)) for i in items)
    return str(int(total)) if total == int(total) else str(total)
