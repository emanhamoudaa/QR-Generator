import os
import uuid
import fitz  # PyMuPDF
import qrcode
from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__)

# إعداد المجلدات
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# اسم الدومين
DOMAIN_NAME = os.getenv('DOMAIN_NAME', 'https://eportal-fza.ae')


def add_qr_to_pdf(input_pdf, output_pdf, qr_data):
    # توليد صورة الـ QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=1,
    )
    qr.add_data(qr_data)
    qr.make(fit_size=True)
    img = qr.make_image(fill_color="black", back_color="white")

    temp_qr_path = "temp_qr.png"
    img.save(temp_qr_path)

    # إضافة الـ QR إلى أعلى الصفحة الأولى في الـ PDF
    doc = fitz.open(input_pdf)
    page = doc[0]

    # أبعاد وموقع الـ QR Code
    rect = fitz.Rect(450, 20, 550, 120)
    page.insert_image(rect, filename=temp_qr_path)

    doc.save(output_pdf)
    doc.close()

    if os.path.exists(temp_qr_path):
        os.remove(temp_qr_path)


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

        file.save(temp_input_path)

        view_url = f"{DOMAIN_NAME}/view/{doc_id}"
        add_qr_to_pdf(temp_input_path, final_output_path, view_url)

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
