import os
import io
import uuid
import pymupdf
import qrcode
import cv2
import numpy as np
from flask import Flask, request, render_template, send_from_directory, abort
app = Flask(__name__)

# تحديد مجلد الحفظ في المسار الرئيسي للبرنامج
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DOMAIN_NAME = "https://eportal-fza.ae"

def _redact_rect(page, rect, pad=6):
    page.add_redact_annot(
        pymupdf.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad),
        fill=(1, 1, 1),
    )


def remove_existing_qr(page):
    """يمسح أي باركود في الجزء اليمين-تحت من الصفحة (3 طبقات للكشف)."""
    r = page.rect

    # المنطقة المفحوصة: النص اليمين، من 55% من ارتفاع الصفحة لتحت
    zone = pymupdf.Rect(r.x0 + r.width * 0.5, r.y0 + r.height * 0.55, r.x1, r.y1)
    found_any = False

    # --- الطبقة 1: كشف QR بصرياً (بأكتر من تكبير) ---
    detector = cv2.QRCodeDetector()
    for zoom in (3, 4, 6):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=zone, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        # نزوّد هامش أبيض حوالين الصورة عشان الكاشف يلقط الباركود اللي على الحافة
        img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))

        ok, points = detector.detectMulti(img)
        if ok and points is not None:
            for quad in points:
                xs = (quad[:, 0] - 40) / zoom + zone.x0
                ys = (quad[:, 1] - 40) / zoom + zone.y0
                _redact_rect(page, pymupdf.Rect(xs.min(), ys.min(), xs.max(), ys.max()), pad=8)
                found_any = True
            break

    # --- الطبقة 2: لو الباركود صورة جوه الـ PDF ---
    for info in page.get_image_info():
        b = pymupdf.Rect(info["bbox"])
        if not b.intersects(zone):
            continue
        w, h = b.width, b.height
        # صورة شبه مربعة وحجمها منطقي لباركود (مش خلفية الصفحة)
        if 25 < w < 160 and 25 < h < 160 and 0.8 < w / h < 1.25:
            _redact_rect(page, b, pad=4)
            found_any = True

    # --- الطبقة 3: لو الباركود مرسوم كمربعات vector ---
    if not found_any:
        blocks = []
        for d in page.get_drawings():
            rc = d.get("rect")
            if rc is None or not rc.intersects(zone):
                continue
            # مربعات سودا صغيرة (وحدات الباركود)
            fill = d.get("fill")
            if fill is not None and sum(fill) < 0.6 and rc.width < 12 and rc.height < 12:
                blocks.append(rc)
        if len(blocks) > 40:  # باركود فيه عشرات المربعات الصغيرة
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

    qr_size = 63     # حجم الباركود
    margin_x = 45    # المسافة من الحافة اليمين
    margin_y = 58    # المسافة من الحافة تحت

    for page in doc:
        # 1) امسحي أي QR قديم
        remove_existing_qr(page)

        # 2) حطي الجديد تحت يمين
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

            if file and file.filename.lower().endswith('.pdf'):
                # توليد معرف فريد للملف لتجنب مشاكل الأسماء والرموز
                file_id = uuid.uuid4().hex[:10]
                filename = f"doc_{file_id}.pdf"
                
                input_path = os.path.join(UPLOAD_FOLDER, f"raw_{filename}")
                output_path = os.path.join(UPLOAD_FOLDER, filename)

                file.save(input_path)

                # رابط المعاينة والـ QR
                view_url = f"{DOMAIN_NAME}/view/{filename}"
                add_qr_to_pdf(input_path, output_path, view_url)

                if os.path.exists(input_path):
                    os.remove(input_path)

                return render_template('upload.html', 
                                       download_url=f"/view/{filename}", 
                                       view_url=view_url)

        except Exception as e:
            return f"حدث خطأ أثناء معالجة الملف: {str(e)}", 500

    return render_template('upload.html')


@app.route('/view/<filename>')
def view_pdf(filename):
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        abort(404)
    return render_template('view.html', doc_id=filename)


@app.route('/files/<filename>')
def raw_pdf(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
