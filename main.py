import io
import os
import tempfile

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from pdf_parser import extract_invoice_data
from xml_generator import generate_xml

app = FastAPI(title="PDF → XML для Диадок")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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
    invoice_number: str = Form(...),
    invoice_date: str = Form(...),
    seller_name: str = Form(...),
    seller_inn: str = Form(...),
    seller_kpp: str = Form(''),
    seller_address: str = Form(...),
    buyer_name: str = Form(...),
    buyer_inn: str = Form(...),
    buyer_kpp: str = Form(''),
    buyer_address: str = Form(...),
    currency_code: str = Form('643'),
    shipment_doc_name: str = Form(''),
    shipment_doc_number: str = Form(''),
    shipment_doc_date: str = Form(''),
    # item fields (single item for now; extend as needed)
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
    total_no_vat: str = Form(...),
    total_vat: str = Form(...),
    total_with_vat: str = Form(...),
    signer_name: str = Form(''),
):
    data = {
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'seller_name': seller_name,
        'seller_inn': seller_inn,
        'seller_kpp': seller_kpp,
        'seller_address': seller_address,
        'buyer_name': buyer_name,
        'buyer_inn': buyer_inn,
        'buyer_kpp': buyer_kpp,
        'buyer_address': buyer_address,
        'currency_code': currency_code,
        'shipment_doc_name': shipment_doc_name,
        'shipment_doc_number': shipment_doc_number,
        'shipment_doc_date': shipment_doc_date,
        'items': [{
            'num': item_num,
            'name': item_name,
            'description': item_description,
            'unit_code': item_unit_code,
            'unit_name': item_unit_name,
            'qty': item_qty,
            'price': item_price,
            'amount_no_vat': item_amount_no_vat,
            'vat_rate': item_vat_rate,
            'vat_amount': item_vat_amount,
            'amount_with_vat': item_amount_with_vat,
        }],
        'total_no_vat': total_no_vat,
        'total_vat': total_vat,
        'total_with_vat': total_with_vat,
        'signer_name': signer_name,
    }

    try:
        xml_content = generate_xml(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации XML: {e}")

    filename = f"UPD_{invoice_number}_{invoice_date.replace('.', '')}.xml"
    return StreamingResponse(
        io.BytesIO(xml_content.encode('utf-8')),
        media_type='application/xml',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
