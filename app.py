import os
from flask import Flask, render_template, request, send_file
import pdfplumber
import docx
import csv
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF  # pip install fpdf

# Set up API key from environment variable
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel("models/gemini-1.5-pro")
else:
    model = None

app = Flask(__name__)

# Directories for storing uploaded and processed files
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    text = ""
    try:
        if ext == 'pdf':
            with pdfplumber.open(file_path) as pdf:
                text = '\n'.join([page.extract_text() for page in pdf.pages if page.extract_text()])
        elif ext == 'docx':
            doc = docx.Document(file_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
        elif ext == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
    except Exception as e:
        print(f"Error extracting text: {e}")
    return text.strip() if text else None

def Question_mcqs_generator(input_text, num_questions):
    if not model:
        return "Error: Google API key is missing."
    
    print("Generating MCQs with input text:")
    print(input_text[:500])  # Print first 500 characters for debugging

    prompt = f"""
    You are an AI assistant generating multiple-choice questions (MCQs) from the following text:
    '{input_text}'
    Generate {num_questions} MCQs with:
    - A clear question
    - Four answer options (A, B, C, D)
    - Indicate the correct answer
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
        mcqs = response.text.strip()
        print("MCQ Generation Response:")
        print(mcqs[:500])  # Print first 500 characters for debugging
        return mcqs
    except Exception as e:
        print(f"Error during MCQ generation: {e}")
        return None

def save_mcqs_to_file(mcqs, filename):
    file_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(mcqs)
    return file_path

def create_pdf(mcqs, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            pdf.multi_cell(0, 10, mcq.strip())
            pdf.ln(5)

    pdf_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    pdf.output(pdf_path)
    return pdf_path

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
            print(f"Error occurred: {e}")
            return "An error occurred during MCQ generation."
    
    return "Invalid file format or upload issue"

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use Render's assigned port or default to 5000
    app.run(host="0.0.0.0", port=port, debug=True)
