import os
import fitz  # PyMuPDF
import qrcode
from flask import Flask, request, render_template, send_from_directory, abort

app = Flask(__name__)

# إنشاء مجلد رفع الملفات تلقائياً إذا لم يكن موجوداً
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# اسم الدومين الرئيسي المربوط بالمشروع
DOMAIN_NAME = "https://eportal-fza.ae"


def add_qr_to_pdf(input_pdf_path, output_pdf_path, qr_data_url):
    # إنشاء صورة الـ QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_data_url)
    qr.make(fit_size=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # حفظ الـ QR كصورة مؤقتة
    temp_qr_path = "temp_qr.png"
    img.save(temp_qr_path)

    # فتح ملف الـ PDF واضافة الـ QR في الصفحة الأولى
    doc = fitz.open(input_pdf_path)
    page = doc[0]  # الصفحة الأولى

    # تحديد موقع وأبعاد الـ QR Code (أعلى اليسار مثلاً)
    rect = fitz.Rect(40, 40, 120, 120)
    page.insert_image(rect, filename=temp_qr_path)

    # حفظ الملف الناتج وإغلاق المستند
    doc.save(output_pdf_path)
    doc.close()

    # حذف صورة الـ QR المؤقتة
    if os.path.exists(temp_qr_path):
        os.remove(temp_qr_path)


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # التحقق من وجود الملف في الطلب
        if 'file' not in request.files and 'pdf_file' not in request.files:
            return "لم يتم اختيار أي ملف", 400
        
        file = request.files.get('file') or request.files.get('pdf_file')
        
        if file.filename == '':
            return "لم يتم اختيار أي ملف", 400

        if file and file.filename.lower().endswith('.pdf'):
            filename = file.filename
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"qr_{filename}")

            # حفظ الملف المرفوع الأصلي
            file.save(input_path)

            # رابط العرض النهائي الذي سيرتبط بالـ QR Code
            view_url = f"{DOMAIN_NAME}/view/{filename}"

            # إضافة الـ QR إلى الـ PDF
            add_qr_to_pdf(input_path, output_path, view_url)

            # إرجاع صفحة النجاح مع رابط التحميل والمعاينة
            return render_template('upload.html', 
                                   download_url=f"/uploads/qr_{filename}", 
                                   view_url=view_url)

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
