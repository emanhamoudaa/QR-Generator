import os
import uuid
import pymupdf
import qrcode
from flask import Flask, request, render_template, send_from_directory

app = Flask(__name__)

# استخدام مجلد tmp الخص بالسيستم لتفادي صلاحيات Render
UPLOAD_FOLDER = '/tmp/pdf_uploads'
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
    
    temp_qr_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{uuid.uuid4().hex}.png")
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
                # اسم فريد وحصري ينتهي بـ .pdf لمنع أي مشاكل ترميز
                file_id = uuid.uuid4().hex
                filename = f"{file_id}.pdf"
                
                input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"raw_{filename}")
                output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                file.save(input_path)

                # رابط فتح المعاينة ورابط الـ QR
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


@app.route('/view/')
def view_pdf(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, mimetype='application/pdf')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
