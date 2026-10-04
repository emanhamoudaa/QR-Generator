import os
import fitz  # PyMuPDF
import qrcode
from flask import Flask, request, render_template, send_from_directory

app = Flask(__name__)

# تحديد مجلد الحفظ وتأكيده
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DOMAIN_NAME = "https://eportal-fza.ae"


def add_qr_to_pdf(input_pdf_path, output_pdf_path, qr_data_url):
    # إنشاء الـ QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_data_url)
    qr.make(fit_size=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # حفظ الـ QR كصورة PNG مؤقتة
    temp_qr_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp_qr.png")
    img.save(temp_qr_path)

    # فتح الـ PDF وإضافة الـ QR
    doc = fitz.open(input_pdf_path)
    page = doc[0]  # الصفحة الأولى

    # أبعاد ومكان الـ QR Code
    rect = fitz.Rect(40, 40, 120, 120)
    page.insert_image(rect, filename=temp_qr_path)

    doc.save(output_pdf_path)
    doc.close()

    # تنظيف الملف المؤقت
    if os.path.exists(temp_qr_path):
        os.remove(temp_qr_path)


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            # استقبال الملف باسم pdf كما في HTML
            file = request.files.get('pdf') or request.files.get('pdf_file') or request.files.get('file')
            
            if not file or file.filename == '':
                return render_template('upload.html', error="يرجى اختيار ملف PDF أولاً")

            if file and file.filename.lower().endswith('.pdf'):
                filename = file.filename
                input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"qr_{filename}")

                file.save(input_path)

                view_url = f"{DOMAIN_NAME}/view/{filename}"
                add_qr_to_pdf(input_path, output_path, view_url)

                return render_template('upload.html', 
                                       download_url=f"/uploads/qr_{filename}", 
                                       view_url=view_url)

        except Exception as e:
            # إظهار تفاصيل الخطأ مباشرة على الشاشة بدلاً من صفحة 500
            return f"حدث خطأ أثناء معالجة الملف: {str(e)}", 500

    return render_template('upload.html')


@app.route('/view/')
def view_pdf(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"qr_{filename}")
    if not os.path.exists(file_path):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(file_path))
    else:
        return "الملف غير موجود", 404


@app.route('/uploads/')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
