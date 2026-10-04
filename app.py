import os
import pymupdf
import qrcode
from urllib.parse import quote
from werkzeug.utils import secure_filename
from flask import Flask, request, render_template, send_from_directory

app = Flask(__name__)

# إعداد مجلد الحفظ
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DOMAIN_NAME = "https://eportal-fza.ae"


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
    
    temp_qr_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp_qr.png")
    img.save(temp_qr_path)

    doc = pymupdf.open(input_pdf_path)
    page = doc[0]

    rect = pymupdf.Rect(40, 40, 120, 120)
    page.insert_image(rect, filename=temp_qr_path)

    doc.save(output_pdf_path)
    doc.close()

    if os.path.exists(temp_qr_path):
        os.remove(temp_qr_path)


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            file = request.files.get('pdf') or request.files.get('pdf_file') or request.files.get('file')
            
            if not file or file.filename == '':
                return render_template('upload.html', error="يرجى اختيار ملف PDF أولاً")

            if file and file.filename.lower().endswith('.pdf'):
                raw_filename = file.filename
                safe_name = secure_filename(raw_filename)
                
                if not safe_name or not safe_name.endswith('.pdf'):
                    safe_name = f"doc_{os.urandom(4).hex()}.pdf"

                # اسم الملف مع الـ QR
                final_filename = f"qr_{safe_name}"

                input_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                output_path = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)

                file.save(input_path)

                # الرابط الذي سيتم تضمينه داخل الـ QR وتوجيه زر المعاينة إليه
                view_url = f"{DOMAIN_NAME}/view/{final_filename}"
                add_qr_to_pdf(input_path, output_path, view_url)

                return render_template('upload.html', 
                                       download_url=f"/uploads/{final_filename}", 
                                       view_url=view_url)

        except Exception as e:
            return f"حدث خطأ أثناء معالجة الملف: {str(e)}", 500

    return render_template('upload.html')


@app.route('/view/')
def view_pdf(filename):
    safe_name = secure_filename(filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)

    # إذا لم يجد الملف بالاسم المباشر، يبحث بإضافة qr_
    if not os.path.exists(file_path):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"qr_{safe_name}")

    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(file_path))
    else:
        return f"الملف غير موجود: {safe_name}", 404


@app.route('/uploads/')
def download_file(filename):
    safe_name = secure_filename(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_name)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
