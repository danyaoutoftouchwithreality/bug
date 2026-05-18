import re
from typing import Optional

MONTHS_RU = {
    'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
    'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
    'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12',
}


def _parse_date(s: str) -> str:
    """'30 апреля, 2026' → '30.04.2026'"""
    m = re.search(r'(\d{1,2})\s+(\w+),?\s+(\d{4})', s)
    if m:
        day = m.group(1).zfill(2)
        month = MONTHS_RU.get(m.group(2).lower(), '00')
        year = m.group(3)
        return f"{day}.{month}.{year}"
    # Already formatted
    m2 = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', s)
    if m2:
        return m2.group(0)
    return s.strip()


def _clean_amount(s: str) -> str:
    """'9 689.00' → '9689.00'"""
    return re.sub(r'\s', '', s).replace(',', '.').strip()


def _first(pattern: str, text: str, group: int = 1) -> str:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(group).strip() if m else ''


_STREET_TYPES = [
    (r'УЛИЦА|УЛ\.', 'ул.'),
    (r'НАБЕРЕЖНАЯ|НАБ\.', 'наб.'),
    (r'ПЕРЕУЛОК|ПЕР\.?(?=[\s,]|\Z)', 'пер.'),
    (r'ШОССЕ', 'шоссе'),
    (r'ПРОСПЕКТ|ПРОСП\.|ПР-КТ', 'просп.'),
    (r'БУЛЬВАР|БУЛЬВ\.|Б-Р', 'бульв.'),
    (r'ПЛОЩАДЬ|ПЛ\.', 'пл.'),
    (r'АЛЛЕЯ', 'аллея'),
]


def _parse_address_gar(addr: str) -> dict:
    """
    Разбирает сырую строку российского адреса на структурированные поля АдрГАР.
    Если поле не удалось определить надёжно — возвращает пустую строку.
    Никаких захардкоженных fallback-значений.
    """
    g = {k: '' for k in [
        'zip', 'nasel_vid', 'nasel_naim',
        'street_tip', 'street_naim',
        'house_tip', 'house_num',
        'room_tip', 'room_num',
    ]}
    if not addr:
        return g

    # Индекс: первые 6 цифр подряд
    m = re.search(r'\b(\d{6})\b', addr)
    if m:
        g['zip'] = m.group(1)

    # Дом: «Д. 39», «д.19»
    m = re.search(r'\bД\.\s*([^\s,]+)', addr, re.IGNORECASE)
    if m:
        g['house_num'] = m.group(1)
        g['house_tip'] = 'д.'

    # Помещение: ПОМЕЩ. → первое вхождение; иначе кв.
    rooms = re.findall(r'ПОМЕЩ\.\s*([^\s,]+)', addr, re.IGNORECASE)
    if rooms:
        g['room_num'] = rooms[0]
        g['room_tip'] = 'помещ.'
    else:
        m = re.search(r'\bкв\.\s*([^\s,]+)', addr, re.IGNORECASE)
        if m:
            g['room_num'] = m.group(1)
            g['room_tip'] = 'кв.'

    # Улица: пробуем «ТИП ИМЯ», потом «ИМЯ ТИП»
    for pat, canonical in _STREET_TYPES:
        m = re.search(
            rf'\b(?:{pat})\s+([А-ЯЁа-яё][А-ЯЁа-яё\s-]*?)(?=\s*,|\s+Д\.|\Z)',
            addr, re.IGNORECASE,
        )
        if m:
            g['street_tip'] = canonical
            g['street_naim'] = m.group(1).strip().title()
            break
        m = re.search(
            rf'([А-ЯЁа-яё][А-ЯЁа-яё-]*)\s+(?:{pat})',
            addr, re.IGNORECASE,
        )
        if m:
            g['street_tip'] = canonical
            g['street_naim'] = m.group(1).strip().title()
            break

    # Город: «ГОРОД МОСКВА» / «Екатеринбург г» / «САНКТ-ПЕТЕРБУРГ Г.»
    m = re.search(r'\bГОРОД\s+([А-ЯЁа-яё][А-ЯЁа-яё-]+)', addr, re.IGNORECASE)
    if m:
        g['nasel_vid'] = 'г.'
        g['nasel_naim'] = m.group(1).title()
    else:
        m = re.search(r'([А-ЯЁа-яё][А-ЯЁа-яё-]+)\s+[Гг](?:\.|\s|\Z)', addr)
        if m:
            g['nasel_vid'] = 'г.'
            g['nasel_naim'] = m.group(1).title()

    return g


def extract_invoice_data(pdf_path: str) -> dict:
    import pdfplumber  # ленивый импорт — не тормозит старт сервера
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or '')

    # Ищем страницу со СЧЕТ-ФАКТУРОЙ по ключевому слову, а не по фиксированному индексу
    sf_idx = next(
        (i for i, p in enumerate(pages) if re.search(r'СЧЕТ-ФАКТУРА', p, re.IGNORECASE)),
        1 if len(pages) > 1 else 0
    )
    sf = pages[sf_idx]
    # АКТ — следующая страница после счёт-фактуры
    act = pages[sf_idx + 1] if sf_idx + 1 < len(pages) else ''

    data = {}

    # ── Номер и дата счёт-фактуры ──────────────────────────────────────────
    m = re.search(r'СЧЕТ-ФАКТУРА\s*№\s*(\S+)\s+от\s+(.+)', sf)
    if m:
        data['invoice_number'] = m.group(1).strip()
        data['invoice_date'] = _parse_date(m.group(2))
    else:
        data['invoice_number'] = ''
        data['invoice_date'] = ''

    # ── Продавец ───────────────────────────────────────────────────────────
    # Name: line after "СЧЕТ-ФАКТУРА" that has ООО / ОАО / ЗАО / ИП
    m = re.search(
        r'(?:Общество с ограниченной ответственностью|ООО|ОАО|ЗАО)[:\s]*["«]?([^"»\n]+)["»]?',
        sf,
    )
    if m:
        data['seller_name'] = m.group(0).strip().rstrip(',').rstrip('.')
    else:
        data['seller_name'] = ''

    # Seller address: first 6-digit postal code line after seller INN block
    # The seller address is on the line right after the org name
    lines = sf.split('\n')
    seller_addr = ''
    for i, line in enumerate(lines):
        if re.search(r'Оранж Бизнес|НОВАТЕЛ|продавец', line, re.IGNORECASE):
            # look forward for address-like line
            for j in range(i + 1, min(i + 4, len(lines))):
                if re.search(r'\d{5,6}', lines[j]):
                    seller_addr = lines[j].strip()
                    break
            if seller_addr:
                break
    # Fallback: find Moscow address
    if not seller_addr:
        m = re.search(r'(107031[^\n]+)', sf)
        seller_addr = m.group(1).strip() if m else ''
    data['seller_address'] = seller_addr

    # Seller INN/KPP: 10-digit / 9-digit pair
    seller_inn_kpp = re.findall(r'(\d{10})/(\d{9})', sf)
    if seller_inn_kpp:
        data['seller_inn'] = seller_inn_kpp[0][0]
        data['seller_kpp'] = seller_inn_kpp[0][1]
    else:
        data['seller_inn'] = ''
        data['seller_kpp'] = ''

    # ── Покупатель: имя ────────────────────────────────────────────────────
    # Источник 1 (приоритет): акт — покупатель стоит между «Сервисез"), и» и
    # «(именуемым в дальнейшем "Клиент")». Полное название без обрезания.
    buyer_name = ''
    m = re.search(
        r'именуемой в дальнейшем[^)]+\),\s*и\s*\n(.+?)\s*\n\s*\(именуемым',
        act,
        re.DOTALL,
    )
    if m:
        buyer_name = m.group(1).strip()

    # Источник 2: «Покупатель: ИМЯ» на любой странице, кроме строки
    # «Покупатель: Юридический адрес:» (это двухколоночный заголовок стр. 1).
    if not buyer_name:
        all_pages_text = '\n'.join(pages)
        m = re.search(r'Покупатель:\s+(?!Юридический)(.+)', all_pages_text)
        if m:
            buyer_name = m.group(1).strip()

    # Источник 3 (запасной): блок счёт-фактуры — после ИНН/КПП продавца и двух
    # строк «-» до ИНН покупателя. Попутно извлекает адрес.
    buyer_address = ''
    m = re.search(
        r'\d{10}/\d{9}\s*\n-\s*\n-\s*\n(.+?)(?=\n(?:\d{12}/-|\d{10}/\d{9}))',
        sf,
        re.DOTALL,
    )
    if m:
        buyer_block = m.group(1).strip()
        buyer_lines = [l.strip() for l in buyer_block.split('\n') if l.strip()]
        if not buyer_name:
            buyer_name = buyer_lines[0] if buyer_lines else ''
        buyer_address = ' '.join(buyer_lines[1:]) if len(buyer_lines) > 1 else ''

    data['buyer_name'] = buyer_name
    data['buyer_address'] = buyer_address
    data['buyer_gar'] = _parse_address_gar(buyer_address)

    # Buyer INN: 12-digit (ИП) or 10-digit (ЮЛ)
    m = re.search(r'(\d{12})/-', sf)
    if m:
        data['buyer_inn'] = m.group(1)
        data['buyer_kpp'] = ''
    else:
        buyer_inn_kpp = re.findall(r'(\d{10})/(\d{9})', sf)
        if len(buyer_inn_kpp) > 1:
            data['buyer_inn'] = buyer_inn_kpp[1][0]
            data['buyer_kpp'] = buyer_inn_kpp[1][1]
        else:
            data['buyer_inn'] = ''
            data['buyer_kpp'] = ''

    # ── Валюта ────────────────────────────────────────────────────────────
    m = re.search(r'(Российский рубль),\s*(\d+)', sf)
    if m:
        data['currency_name'] = m.group(1)
        data['currency_code'] = m.group(2)
    else:
        data['currency_name'] = 'Российский рубль'
        data['currency_code'] = '643'

    # ── Документ об отгрузке ──────────────────────────────────────────────
    m = re.search(r'АКТ ОКАЗАННЫХ УСЛУГ\s*№\s*(\S+)\s+от\s+(.+?)(?:\s*\(|$)', sf)
    if m:
        data['shipment_doc_name'] = 'Счет-фактура и передаточный документ'
        data['shipment_doc_number'] = m.group(1).strip()
        data['shipment_doc_date'] = _parse_date(m.group(2))
    else:
        data['shipment_doc_name'] = ''
        data['shipment_doc_number'] = ''
        data['shipment_doc_date'] = ''

    # ── Договор ───────────────────────────────────────────────────────────
    m = re.search(r'контракту\s+(\S+)', sf)
    data['contract_number'] = m.group(1).strip() if m else ''

    # Дата договора — ищем на странице акта: "Заключенным 01 октября 2019 между"
    m = re.search(r'[Зз]аключен\w*\s+(\d{1,2}\s+\w+\s+\d{4})', act)
    if m:
        data['contract_date'] = _parse_date(m.group(1))
    else:
        data['contract_date'] = ''

    # ── Строки товаров/услуг ──────────────────────────────────────────────
    # Try page 2 first: "1 Интеллектуальный номер - 362 МЕС 1 9689.00 9 689.00 без акциза 22% 2 131.58 11 820.58"
    items = []
    m = re.search(
        r'(\d+)\s+(Интеллектуальный номер)\s+-\s+(\d+)\s+(\w+)\s+(\d+)\s+([\d.]+)\s+([\d\s]+\.?\d{2})'
        r'\s+без\s+акциза\s+(\d+%)\s+([\d\s]+\.?\d{2})\s+([\d\s]+\.?\d{2})',
        sf,
    )
    if m:
        contract = data["contract_number"]
        items.append({
            'num': m.group(1),
            'name': f'Услуги связи по контракту {contract} - {m.group(2)}' if contract else m.group(2),
            'description': '',
            'unit_code': m.group(3),
            'unit_name': m.group(4),
            'qty': m.group(5),
            'price': _clean_amount(m.group(6)),
            'amount_no_vat': _clean_amount(m.group(7)),
            'vat_rate': m.group(8),
            'vat_amount': _clean_amount(m.group(9)),
            'amount_with_vat': _clean_amount(m.group(10)),
        })

    # Fallback: try act page (cleaner format)
    # "Интеллектуальный номер МЕС 1 9689.00 9 689.00 - 22% 2 131.58 11 820.58"
    if not items and act:
        m = re.search(
            r'(Интеллектуальный номер)\s+(\w+)\s+(\d+)\s+([\d.]+)\s+([\d\s]+\.?\d{2})'
            r'\s+-\s+(\d+%)\s+([\d\s]+\.?\d{2})\s+([\d\s]+\.?\d{2})',
            act,
        )
        if m:
            contract = data["contract_number"]
            items.append({
                'num': '1',
                'name': f'Услуги связи по контракту {contract} - {m.group(1)}' if contract else m.group(1),
                'description': '',
                'unit_code': '362',
                'unit_name': m.group(2),
                'qty': m.group(3),
                'price': _clean_amount(m.group(4)),
                'amount_no_vat': _clean_amount(m.group(5)),
                'vat_rate': m.group(6),
                'vat_amount': _clean_amount(m.group(7)),
                'amount_with_vat': _clean_amount(m.group(8)),
            })

    data['items'] = items

    # ── Итого ─────────────────────────────────────────────────────────────
    # Last "Всего к оплате" line: "9 689.00 2 131.58 11 820.58"
    totals = re.findall(
        r'Всего к оплате.*?([\d\s]+\.\d{2})\s+([\d\s]+\.\d{2})\s+([\d\s]+\.\d{2})',
        sf,
        re.DOTALL,
    )
    if totals:
        t = totals[-1]
        data['total_no_vat'] = _clean_amount(t[0])
        data['total_vat'] = _clean_amount(t[1])
        data['total_with_vat'] = _clean_amount(t[2])
    else:
        data['total_no_vat'] = items[0]['amount_no_vat'] if items else ''
        data['total_vat'] = items[0]['vat_amount'] if items else ''
        data['total_with_vat'] = items[0]['amount_with_vat'] if items else ''

    # ── Подписанты ────────────────────────────────────────────────────────
    # Страница акта (page 3) содержит имя в чистом виде без двухколоночного смешения
    signer_src = act if act else sf
    m = re.search(
        r'(?:уполномоченное лицо\s+)([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)',
        signer_src,
    )
    if not m:
        # Fallback: искать в SF, но брать только три слова без "Главный"
        m = re.search(
            r'Руководитель\s+([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)\s+(?:Главный|$)',
            sf,
        )
    data['signer_name'] = m.group(1).strip() if m else ''

    m = re.search(r'Главный бухгалтер.*?([А-ЯЁ][а-яё]*\.?\s+[А-ЯЁ]\.[А-ЯЁ]\.)', sf)
    data['accountant_name'] = m.group(1).strip() if m else ''

    return data
