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

def remove_existing_qr(page):
    """يدوّر على أي QR في الجزء اليمين من الصفحة بس ويمسحه."""
    zoom = 2
    r = page.rect

    # الجزء اللي هيتفحص: من منتصف الصفحة لحد الحافة اليمين
    clip = pymupdf.Rect(r.x0 + r.width * 0.5, r.y0, r.x1, r.y1)

    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    detector = cv2.QRCodeDetector()
    found, points = detector.detectMulti(img)
    if not found or points is None:
        return

    for quad in points:
        # نرجّع الإحداثيات لمكانها الأصلي في الصفحة (نضيف إزاحة الـ clip)
        xs = quad[:, 0] / zoom + clip.x0
        ys = quad[:, 1] / zoom + clip.y0
        pad = 6
        rect = pymupdf.Rect(xs.min() - pad, ys.min() - pad,
                            xs.max() + pad, ys.max() + pad)
        page.add_redact_annot(rect, fill=(1, 1, 1))

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

    qr_size = 70   # حجم الـ QR
    margin = 20    # المسافة من حافة الصفحة

    for page in doc:
        # 1) امسحي أي QR قديم
        remove_existing_qr(page)

        # 2) حطي الجديد تحت يمين
        r = page.rect
        rect = pymupdf.Rect(r.x1 - margin - qr_size, r.y1 - margin - qr_size,
                            r.x1 - margin, r.y1 - margin)
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
