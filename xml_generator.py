"""
Генерация УПД XML формата 5.03 (ФНС, Приказ ЕД-7-26/303@)
Кодировка: windows-1251, совместимо с Контур.Диадок.
"""
import uuid
import datetime
import re
from xml.etree.ElementTree import Element, SubElement, tostring


# ── Вспомогательные функции ───────────────────────────────────────────────

def _new_uuid() -> str:
    return str(uuid.uuid4())


def _file_id(seller_inn, seller_kpp, buyer_inn, buyer_kpp):
    now = datetime.datetime.now().strftime('%Y%m%d')
    uid = _new_uuid()
    buyer_part = f"{buyer_inn}_{buyer_kpp}" if buyer_kpp else buyer_inn
    seller_part = f"{seller_inn}_{seller_kpp}" if seller_kpp else seller_inn
    return f"ON_NSCHFDOPPR_{buyer_part}_{seller_part}_{now}_{uid}_0_0_0_0_0_00"


def _parse_fio(full_name: str) -> tuple:
    name = re.sub(r'^Индивидуальный предприниматель\s+', '', full_name).strip()
    parts = name.split()
    return (
        parts[0] if len(parts) > 0 else '',
        parts[1] if len(parts) > 1 else '',
        parts[2] if len(parts) > 2 else '',
    )


def _vat_number(vat_rate: str) -> str:
    """'22%' → '22'"""
    return re.sub(r'[^0-9]', '', vat_rate)


def _sum_qty(items: list) -> str:
    try:
        total = sum(float(i.get('qty', 0)) for i in items)
        return str(int(total)) if total == int(total) else str(total)
    except Exception:
        return '1'


# ── Адрес через АдрГАР (структурированный) ───────────────────────────────

def _build_adr_gar(parent: Element, addr: dict):
    """
    addr keys (все опциональны):
        fias_id, zip, region_code, region_name,
        munitsip_vid_kod, munitsip_naim,
        nasel_vid, nasel_naim,
        street_tip, street_naim,
        house_tip, house_num,
        room_tip, room_num
    """
    gar = SubElement(parent, 'АдрГАР')
    if addr.get('fias_id'):
        gar.set('ИдНом', addr['fias_id'])
    if addr.get('zip'):
        gar.set('Индекс', addr['zip'])

    if addr.get('region_code'):
        reg = SubElement(gar, 'Регион')
        reg.text = addr['region_code']

    if addr.get('region_name'):
        naim = SubElement(gar, 'НаимРегион')
        naim.text = addr['region_name']

    if addr.get('munitsip_naim'):
        mr = SubElement(gar, 'МуниципРайон')
        mr.set('ВидКод', addr.get('munitsip_vid_kod', '2'))
        mr.set('Наим', addr['munitsip_naim'])

    if addr.get('nasel_naim'):
        np_ = SubElement(gar, 'НаселенПункт')
        np_.set('Вид', addr.get('nasel_vid', 'г.'))
        np_.set('Наим', addr['nasel_naim'])

    if addr.get('street_naim'):
        ul = SubElement(gar, 'ЭлУлДорСети')
        ul.set('Тип', addr.get('street_tip', 'ул.'))
        ul.set('Наим', addr['street_naim'])

    if addr.get('house_num'):
        zd = SubElement(gar, 'Здание')
        zd.set('Тип', addr.get('house_tip', 'д.'))
        zd.set('Номер', addr['house_num'])

    if addr.get('room_num'):
        rm = SubElement(gar, 'ПомещКвартиры')
        rm.set('Тип', addr.get('room_tip', 'помещ.'))
        rm.set('Номер', addr['room_num'])


def _has_gar(addr: dict) -> bool:
    return bool(addr and (addr.get('region_code') or addr.get('nasel_naim') or addr.get('zip')))


# ── Основная функция генерации ────────────────────────────────────────────

def generate_xml(data: dict) -> tuple[bytes, str]:
    """Returns (xml_bytes, file_id)."""
    now = datetime.datetime.now()
    seller_inn = data.get('seller_inn', '')
    seller_kpp = data.get('seller_kpp', '')
    buyer_inn  = data.get('buyer_inn', '')
    buyer_kpp  = data.get('buyer_kpp', '')

    # ── Корень ────────────────────────────────────────────────────────────
    root = Element('Файл')
    root.set('xmlns:xs',  'http://www.w3.org/2001/XMLSchema')
    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    file_id = _file_id(seller_inn, seller_kpp, buyer_inn, buyer_kpp)
    root.set('ИдФайл',    file_id)
    root.set('ВерсФорм',  '5.03')
    root.set('ВерсПрог',  'PDF2XML 1.0')

    # ── Документ ──────────────────────────────────────────────────────────
    doc_name = 'Счет-фактура и передаточный документ (акт)'

    doc = SubElement(root, 'Документ')
    doc.set('КНД',            '1115131')
    doc.set('Функция',        'СЧФДОП')
    doc.set('ПоФактХЖ',       doc_name)
    doc.set('НаимДокОпр',     doc_name)
    doc.set('ДатаИнфПр',      now.strftime('%d.%m.%Y'))
    doc.set('ВремИнфПр',      now.strftime('%H.%M.%S'))
    doc.set('НаимЭконСубСост', data.get('naim_ekon_sub_sost', f'{data.get("seller_name", "")}, ИНН/КПП {seller_inn}/{seller_kpp}'))

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
    adr1.set('КодСтр',    '643')
    adr1.set('НаимСтран', 'РОССИЯ')
    adr1.set('АдрТекст',  data.get('seller_address', ''))

    # Банковские реквизиты продавца
    if data.get('seller_bank_account'):
        bank_rekv = SubElement(sv_prod, 'БанкРекв')
        bank_rekv.set('НомерСчета', data['seller_bank_account'])
        sv_bank = SubElement(bank_rekv, 'СвБанк')
        if data.get('seller_bank_name'):
            sv_bank.set('НаимБанк', data['seller_bank_name'])
        if data.get('seller_bank_bik'):
            sv_bank.set('БИК', data['seller_bank_bik'])
        if data.get('seller_bank_korr'):
            sv_bank.set('КорСчет', data['seller_bank_korr'])

    # Документ-основание отгрузки (позиция: после СвПрод, до СвПокуп — по схеме ФНС 5.03)
    if data.get('shipment_doc_number'):
        dok = SubElement(sv_sf, 'ДокПодтвОтгрНом')
        dok.set('РеквНаимДок',  doc_name)
        dok.set('РеквНомерДок', data['shipment_doc_number'])
        dok.set('РеквДатаДок',  data.get('shipment_doc_date', data.get('invoice_date', '')))

    # Покупатель
    sv_pokup = SubElement(sv_sf, 'СвПокуп')
    if data.get('buyer_okpo'):
        sv_pokup.set('ОКПО', data['buyer_okpo'])

    id_pokup = SubElement(sv_pokup, 'ИдСв')
    if len(buyer_inn) == 12 and not buyer_kpp:
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

    # Адрес покупателя: АдрГАР (если заполнен) или АдрИнф
    addr_pokup = SubElement(sv_pokup, 'Адрес')
    buyer_gar = data.get('buyer_gar', {})
    if _has_gar(buyer_gar):
        _build_adr_gar(addr_pokup, buyer_gar)
    else:
        adr2 = SubElement(addr_pokup, 'АдрИнф')
        adr2.set('КодСтр',    '643')
        adr2.set('НаимСтран', 'РОССИЯ')
        adr2.set('АдрТекст',  data.get('buyer_address', ''))

    # Валюта
    den_izm = SubElement(sv_sf, 'ДенИзм')
    den_izm.set('КодОКВ',  data.get('currency_code', '643'))
    den_izm.set('НаимОКВ', 'Российский рубль')
    den_izm.set('КурсВал', '1.00')

    # ── ИнфПолФХЖ1 ────────────────────────────────────────────────────────
    inf1 = SubElement(sv_sf, 'ИнфПолФХЖ1')
    doc_basis_uid = data.get('doc_basis_uid') or _new_uuid()

    def _txt(parent, identif, znachen):
        el = SubElement(parent, 'ТекстИнф')
        el.set('Идентиф', identif)
        el.set('Значен',  znachen)

    _txt(inf1, 'ИдентификаторДокументаОснования', doc_basis_uid)
    _txt(inf1, 'ВидСчетаФактуры',                 'Реализация')
    _txt(inf1, 'ТолькоУслуги',                     'true')

    sdoc_num  = data.get('shipment_doc_number', '')
    sdoc_date = data.get('shipment_doc_date', data.get('invoice_date', ''))
    if sdoc_num:
        _txt(inf1, 'ДокументОбОтгрузке', f'№ п/п 1 № {sdoc_num} от {sdoc_date} г.')

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

        # ДопСведТов
        dop = SubElement(sv_tov, 'ДопСведТов')
        dop.set('ПрТовРаб', item.get('pr_tov_rab', '3'))  # 3 = услуга
        if item.get('kod_tov'):
            dop.set('КодТов', item['kod_tov'])

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
    vsego.set('СтТовБезНДСВсего', data.get('total_no_vat', ''))
    vsego.set('СтТовУчНалВсего',  data.get('total_with_vat', ''))
    vsego.set('КолНеттоВс',       _sum_qty(data.get('items', [])))
    sum_nal_vsego = SubElement(vsego, 'СумНалВсего')
    sn = SubElement(sum_nal_vsego, 'СумНал')
    sn.text = data.get('total_vat', '')

    # ── СвПродПер ────────────────────────────────────────────────────────
    sv_prod_per = SubElement(doc, 'СвПродПер')
    sv_per = SubElement(sv_prod_per, 'СвПер')
    sv_per.set('СодОпер', data.get('transfer_content', 'Услуги оказаны в полном объеме'))
    sv_per.set('ВидОпер', data.get('transfer_type',   'Продажа'))
    sv_per.set('ДатаПер', data.get('invoice_date', ''))

    if data.get('basis_doc_number'):
        osn = SubElement(sv_per, 'ОснПер')
        basis_label = data.get('basis_doc_name', '')
        basis_num   = data.get('basis_doc_number', '')
        basis_date  = data.get('basis_doc_date', '')
        osn.set('РеквНаимДок',  f'{basis_label} от {basis_date}' if basis_date else basis_label)
        osn.set('РеквНомерДок', basis_num)
        osn.set('РеквДатаДок',  basis_date)

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
    podpisant.set('ТипПодпис',      '2')
    podpisant.set('СпосПодтПолном', '1')
    fio_podp = SubElement(podpisant, 'ФИО')
    fam, ima, otch = _parse_fio(signer_name) if signer_name else ('-', '-', '')
    fio_podp.set('Фамилия', fam)
    fio_podp.set('Имя',     ima)
    if otch:
        fio_podp.set('Отчество', otch)

    # ── Сериализация в windows-1251 ───────────────────────────────────────
    xml_bytes = tostring(root, encoding='windows-1251', xml_declaration=True)
    return xml_bytes, file_id
