import os
from flask import Flask, render_template, request, send_file
import pdfplumber
import docx
import logging
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF  # pip install fpdf

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set API key
os.environ["GOOGLE_API_KEY"] = "AIzaSyADzoh56fpNGKBV8VpTbVmX7TeM-H5yPdM"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("models/gemini-1.5-pro")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

# Ensure necessary folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    try:
        ext = file_path.rsplit('.', 1)[1].lower()
        if ext == 'pdf':
            with pdfplumber.open(file_path) as pdf:
                return '\n'.join([page.extract_text() or '' for page in pdf.pages])
        elif ext == 'docx':
            return '\n'.join([para.text for para in docx.Document(file_path).paragraphs])
        elif ext == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
    except Exception as e:
        logging.error(f"Error extracting text from file: {e}")
    return None

def Question_mcqs_generator(input_text, num_questions):
    logging.info("Generating MCQs from input text")
    prompt = f"""
    Generate {num_questions} MCQs from the following text:
    '{input_text[:1000]}'
    Format:
    ## MCQ
    Question: [question]
    A) [option A]
    B) [option B]
    C) [option C]
    D) [option D]
    Correct Answer: [correct option]
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Error generating MCQs: {e}")
        return None

def save_mcqs_to_file(mcqs, filename):
    results_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    try:
        with open(results_path, 'w', encoding='utf-8') as f:
            f.write(mcqs)
        return results_path
    except Exception as e:
        logging.error(f"Error saving MCQs to file: {e}")
        return None

def create_pdf(mcqs, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    try:
        for mcq in mcqs.split("## MCQ"):
            if mcq.strip():
                pdf.multi_cell(0, 10, mcq.strip())
                pdf.ln(5)
        pdf_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
        pdf.output(pdf_path)
        return pdf_path
    except Exception as e:
        logging.error(f"Error creating PDF: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_mcqs():
    if 'file' not in request.files:
        return "No file part"
    
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        text = extract_text_from_file(file_path)
        if not text:
            return "Text extraction failed."

        try:
            num_questions = int(request.form['num_questions'])
            mcqs = Question_mcqs_generator(text, num_questions)
            if not mcqs:
                return "MCQ generation failed."
            
            txt_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.txt"
            pdf_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.pdf"
            save_mcqs_to_file(mcqs, txt_filename)
            create_pdf(mcqs, pdf_filename)
            
            return render_template('results.html', mcqs=mcqs, txt_filename=txt_filename, pdf_filename=pdf_filename)
        except Exception as e:
            logging.error(f"Error in MCQ generation process: {e}")
            return "An error occurred during MCQ generation."
    
    return "Invalid file format or upload issue"

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "File not found."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

