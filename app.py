import os
import uuid
from flask import Flask, render_template, request, send_from_directory
import fitz  # PyMuPDF
import qrcode

app = Flask(__name__)

UPLOAD_FOLDER = 'uploaded_pdfs'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DOMAIN_NAME = "http://127.0.0.1:5000"

def add_qr_to_pdf(input_pdf_path, output_pdf_path, qr_url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=1,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    temp_qr_path = "temp_qr.png"
    qr_img.save(temp_qr_path)
    
    doc = fitz.open(input_pdf_path)
    
    for page in doc:
        rect_left = fitz.Rect(30, page.rect.height - 80, 80, page.rect.height - 30)
        rect_right = fitz.Rect(page.rect.width - 80, page.rect.height - 80, page.rect.width - 30, page.rect.height - 30)
        
        page.insert_image(rect_left, filename=temp_qr_path)
        page.insert_image(rect_right, filename=temp_qr_path)
        
    doc.save(output_pdf_path)
    doc.close()
    
    if os.path.exists(temp_qr_path):
        os.remove(temp_qr_path)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    # إذا كانت الصفحة بتفتح عادي (فتح جديد أو Reload)
    if request.method == 'GET':
        return render_template('upload.html', doc_id=None, view_url=None)
    
    # إذا تم الضغط على زر الرفع (POST)
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
            
        # فقط هنا بنبعت الـ doc_id و الـ view_url للملف
        return render_template('upload.html', doc_id=doc_id, view_url=view_url)

@app.route('/view/<doc_id>')
def view_document(doc_id):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{doc_id}.pdf")
    if not os.path.exists(file_path):
        return "المستند غير موجود أو تم إزالته", 404
    return render_template('view.html', doc_id=doc_id)

@app.route('/files/<doc_id>')
def serve_pdf(doc_id):
    return send_from_directory(app.config['UPLOAD_FOLDER'], f"{doc_id}.pdf")

if __name__ == '__main__':
    app.run(debug=True)