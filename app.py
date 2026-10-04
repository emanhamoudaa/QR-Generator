import os
import uuid
import io
import fitz  # PyMuPDF
import qrcode
from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__)

# إعداد مجلد الرفع
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# اسم الدومين
DOMAIN_NAME = os.getenv('DOMAIN_NAME', 'https://eportal-fza.ae')


def add_qr_to_pdf(input_pdf_path, output_pdf_path, qr_data):
    # توليد صورة الـ QR Code في الذاكرة (Memory Buffer)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=1,
    )
    qr.add_data(qr_data)
    qr.make(fit_size=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # تحويل الصورة إلى bytes لعدم الحاجة لحفظ ملف مؤقت
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    # فتح الـ PDF وإضافة الـ QR
    doc = fitz.open(input_pdf_path)
    page = doc[0]

    # تحديد موقع وأبعاد الـ QR Code في الصفحة الأولى
    rect = fitz.Rect(450, 20, 550, 120)
    page.insert_image(rect, stream=img_bytes)

    doc.save(output_pdf_path)
    doc.close()


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'pdf' not in request.files:
            return render_template('upload.html', doc_id=None, view_url=None)

        file = request.files['pdf']
        if file.filename == '' or not file.filename.endswith('.pdf'):
            return render_template('upload.html', doc_id=None, view_url=None)

        doc_id = str(uuid.uuid4())[:8]
        temp_input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{doc_id}.pdf")
        final_output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{doc_id}.pdf")

        # حفظ الملف المرفوع
        file.save(temp_input_path)

        view_url = f"{DOMAIN_NAME}/view/{doc_id}"

        try:
            add_qr_to_pdf(temp_input_path, final_output_path, view_url)
        finally:
            # حذف الملف المؤقت بعد المعالجة
            if os.path.exists(temp_input_path):
                os.remove(temp_input_path)

        return render_template('upload.html', doc_id=doc_id, view_url=view_url)

    return render_template('upload.html', doc_id=None, view_url=None)


@app.route('/view/')
def view_doc(doc_id):
    pdf_filename = f"{doc_id}.pdf"
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)

    if not os.path.exists(pdf_path):
        return "المستند غير موجود أو انتهت صلاحيته", 404

    return render_template('view.html', doc_id=doc_id)


@app.route('/pdf/')
def get_pdf(doc_id):
    pdf_filename = f"{doc_id}.pdf"
    return send_from_directory(app.config['UPLOAD_FOLDER'], pdf_filename)


if __name__ == '__main__':
    app.run(debug=True)
