import os
import io
import uuid
import tempfile
import requests
import pymupdf
import qrcode
import cv2
import numpy as np
from flask import Flask, request, render_template, abort, Response

app = Flask(__name__)

DOMAIN_NAME = "https://eportal-fza.ae"

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "pdfs")
SB_HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def _object_url(filename):
    return f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{filename}"


def storage_upload(filename, data):
    r = requests.post(
        _object_url(filename),
        headers={**SB_HEADERS, "Content-Type": "application/pdf", "x-upsert": "true"},
        data=data,
        timeout=60,
    )
    r.raise_for_status()


def storage_exists(filename):
    r = requests.get(_object_url(filename), headers=SB_HEADERS, stream=True, timeout=30)
    ok = r.status_code == 200
    r.close()
    return ok


def storage_download(filename):
    r = requests.get(_object_url(filename), headers=SB_HEADERS, timeout=60)
    return r.content if r.status_code == 200 else None


def _redact_rect(page, rect, pad=6):
    page.add_redact_annot(
        pymupdf.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad),
        fill=(1, 1, 1),
    )


def remove_existing_qr(page):
    """يمسح أي باركود في الجزء اليمين-تحت من الصفحة (3 طبقات للكشف)."""
    r = page.rect
    zone = pymupdf.Rect(r.x0 + r.width * 0.5, r.y0 + r.height * 0.55, r.x1, r.y1)
    found_any = False

    # الطبقة 1: كشف QR بصرياً
    detector = cv2.QRCodeDetector()
    for zoom in (3, 4, 6):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=zone, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))

        ok, points = detector.detectMulti(img)
        if ok and points is not None:
            for quad in points:
                xs = (quad[:, 0] - 40) / zoom + zone.x0
                ys = (quad[:, 1] - 40) / zoom + zone.y0
                _redact_rect(page, pymupdf.Rect(xs.min(), ys.min(), xs.max(), ys.max()), pad=8)
                found_any = True
            break

    # الطبقة 2: الباركود صورة جوه الـ PDF
    for info in page.get_image_info():
        b = pymupdf.Rect(info["bbox"])
        if not b.intersects(zone):
            continue
        w, h = b.width, b.height
        if 25 < w < 160 and 25 < h < 160 and 0.8 < w / h < 1.25:
            _redact_rect(page, b, pad=4)
            found_any = True

    # الطبقة 3: الباركود مرسوم كمربعات vector
    if not found_any:
        blocks = []
        for d in page.get_drawings():
            rc = d.get("rect")
            if rc is None or not rc.intersects(zone):
                continue
            fill = d.get("fill")
            if fill is not None and sum(fill) < 0.6 and rc.width < 12 and rc.height < 12:
                blocks.append(rc)
        if len(blocks) > 40:
            united = pymupdf.Rect(blocks[0])
            for rc in blocks[1:]:
                united |= rc
            _redact_rect(page, united, pad=6)
            found_any = True

    if found_any:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)


def add_qr_to_pdf(input_pdf_path, output_pdf_path, qr_data_url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_bytes = buf.getvalue()

    doc = pymupdf.open(input_pdf_path)

    qr_size = 63
    margin_x = 45
    margin_y = 58

    for page in doc:
        remove_existing_qr(page)
        r = page.rect
        rect = pymupdf.Rect(r.x1 - margin_x - qr_size, r.y1 - margin_y - qr_size,
                            r.x1 - margin_x, r.y1 - margin_y)
        page.insert_image(rect, stream=qr_bytes)

    doc.save(output_pdf_path)
    doc.close()


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            file = request.files.get('pdf') or request.files.get('pdf_file') or request.files.get('file')

            if not file or file.filename == '':
                return render_template('upload.html', error="يرجى اختيار ملف PDF أولاً")

            if file.filename.lower().endswith('.pdf'):
                filename = f"doc_{uuid.uuid4().hex[:10]}.pdf"
                view_url = f"{DOMAIN_NAME}/view/{filename}"

                # المعالجة في فولدر مؤقت، والنتيجة النهائية بتتخزن في Supabase
                with tempfile.TemporaryDirectory() as tmp:
                    input_path = os.path.join(tmp, "raw.pdf")
                    output_path = os.path.join(tmp, filename)
                    file.save(input_path)
                    add_qr_to_pdf(input_path, output_path, view_url)
                    with open(output_path, "rb") as f:
                        storage_upload(filename, f.read())

                return render_template('upload.html',
                                       download_url=f"/view/{filename}",
                                       view_url=view_url)

        except Exception as e:
            return f"حدث خطأ أثناء معالجة الملف: {str(e)}", 500

    return render_template('upload.html')


@app.route('/view/<filename>')
def view_pdf(filename):
    if not filename.lower().endswith('.pdf') or not storage_exists(filename):
        abort(404)
    return render_template('view.html', doc_id=filename)


@app.route('/files/<filename>')
def raw_pdf(filename):
    data = storage_download(filename) if filename.lower().endswith('.pdf') else None
    if data is None:
        abort(404)
    return Response(data, mimetype='application/pdf',
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
