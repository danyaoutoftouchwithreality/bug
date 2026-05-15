import io
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from pdf_parser import extract_invoice_data
from xml_generator import generate_xml

app = FastAPI(title="PDF → XML для Диадок")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/parse")
async def parse_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Загрузите PDF-файл")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        data = extract_invoice_data(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Ошибка разбора PDF: {e}")
    finally:
        os.unlink(tmp_path)

    return data


@app.post("/generate")
async def generate(
    # Счёт-фактура
    invoice_number: str = Form(...),
    invoice_date: str = Form(...),
    # Продавец
    seller_name: str = Form(...),
    seller_inn: str = Form(...),
    seller_kpp: str = Form(''),
    seller_address: str = Form(...),
    seller_okpo: str = Form(''),
    seller_bank_account: str = Form(''),
    seller_bank_name: str = Form(''),
    seller_bank_bik: str = Form(''),
    seller_bank_korr: str = Form(''),
    # Покупатель
    buyer_name: str = Form(...),
    buyer_inn: str = Form(...),
    buyer_kpp: str = Form(''),
    buyer_address: str = Form(...),
    buyer_okpo: str = Form(''),
    # Документ-основание
    shipment_doc_name: str = Form(''),
    shipment_doc_number: str = Form(''),
    shipment_doc_date: str = Form(''),
    # Договор
    basis_doc_name: str = Form(''),
    basis_doc_number: str = Form(''),
    basis_doc_date: str = Form(''),
    # Передача
    transfer_content: str = Form('Услуги оказаны в полном объеме'),
    transfer_type: str = Form('Продажа'),
    # Подписант
    signer_name: str = Form(''),
    signer_position: str = Form('Генеральный директор'),
    # Валюта
    currency_code: str = Form('643'),
    # Структурированный адрес покупателя (АдрГАР)
    buyer_fias_id: str = Form(''),
    buyer_zip: str = Form(''),
    buyer_region_code: str = Form(''),
    buyer_region_name: str = Form(''),
    buyer_munitsip_vid_kod: str = Form('2'),
    buyer_munitsip_naim: str = Form(''),
    buyer_nasel_vid: str = Form('г.'),
    buyer_nasel_naim: str = Form(''),
    buyer_street_tip: str = Form('ул.'),
    buyer_street_naim: str = Form(''),
    buyer_house_tip: str = Form('д.'),
    buyer_house_num: str = Form(''),
    buyer_room_tip: str = Form('помещ.'),
    buyer_room_num: str = Form(''),
    # Товар (одна строка)
    item_num: str = Form('1'),
    item_name: str = Form(...),
    item_description: str = Form(''),
    item_unit_code: str = Form(''),
    item_unit_name: str = Form(''),
    item_qty: str = Form(...),
    item_price: str = Form(...),
    item_amount_no_vat: str = Form(...),
    item_vat_rate: str = Form(...),
    item_vat_amount: str = Form(...),
    item_amount_with_vat: str = Form(...),
    item_kod_tov: str = Form(''),
    item_pr_tov_rab: str = Form('3'),
    # Итого
    total_no_vat: str = Form(...),
    total_vat: str = Form(...),
    total_with_vat: str = Form(...),
):
    data = {
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'seller_name': seller_name,
        'seller_inn': seller_inn,
        'seller_kpp': seller_kpp,
        'seller_address': seller_address,
        'seller_okpo': seller_okpo,
        'seller_bank_account': seller_bank_account,
        'seller_bank_name': seller_bank_name,
        'seller_bank_bik': seller_bank_bik,
        'seller_bank_korr': seller_bank_korr,
        'buyer_name': buyer_name,
        'buyer_inn': buyer_inn,
        'buyer_kpp': buyer_kpp,
        'buyer_address': buyer_address,
        'buyer_okpo': buyer_okpo,
        'buyer_gar': {
            'fias_id':          buyer_fias_id,
            'zip':              buyer_zip,
            'region_code':      buyer_region_code,
            'region_name':      buyer_region_name,
            'munitsip_vid_kod': buyer_munitsip_vid_kod,
            'munitsip_naim':    buyer_munitsip_naim,
            'nasel_vid':        buyer_nasel_vid,
            'nasel_naim':       buyer_nasel_naim,
            'street_tip':       buyer_street_tip,
            'street_naim':      buyer_street_naim,
            'house_tip':        buyer_house_tip,
            'house_num':        buyer_house_num,
            'room_tip':         buyer_room_tip,
            'room_num':         buyer_room_num,
        },
        'shipment_doc_name': shipment_doc_name,
        'shipment_doc_number': shipment_doc_number,
        'shipment_doc_date': shipment_doc_date,
        'basis_doc_name': basis_doc_name,
        'basis_doc_number': basis_doc_number,
        'basis_doc_date': basis_doc_date,
        'transfer_content': transfer_content,
        'transfer_type': transfer_type,
        'signer_name': signer_name,
        'signer_position': signer_position,
        'currency_code': currency_code,
        'items': [{
            'num':             item_num,
            'name':            item_name,
            'description':     item_description,
            'unit_code':       item_unit_code,
            'unit_name':       item_unit_name,
            'qty':             item_qty,
            'price':           item_price,
            'amount_no_vat':   item_amount_no_vat,
            'vat_rate':        item_vat_rate,
            'vat_amount':      item_vat_amount,
            'amount_with_vat': item_amount_with_vat,
            'kod_tov':         item_kod_tov,
            'pr_tov_rab':      item_pr_tov_rab,
        }],
        'total_no_vat': total_no_vat,
        'total_vat': total_vat,
        'total_with_vat': total_with_vat,
    }

    try:
        xml_bytes = generate_xml(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации XML: {e}")

    filename = f"ON_NSCHFDOPPR_{buyer_inn}_{seller_inn}_{invoice_date.replace('.', '')}.xml"
    return StreamingResponse(
        io.BytesIO(xml_bytes),
        media_type='application/xml',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
