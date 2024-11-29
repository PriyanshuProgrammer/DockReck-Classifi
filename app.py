from flask import Flask, redirect, request, jsonify, url_for
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
from flask_dance.contrib.google import make_google_blueprint, google
from extract_text import extract_text_from_file
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from classify import classifier, classify_document
from librarymodule import SCOPES, upload_file_to_drive

app = Flask(__name__)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Set a secret key
app.secret_key = os.urandom(24)  # Generates a random 24-byte key

# Allow all origins for development, but limit in production
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'txt', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Temporary storage for classified documents (replace with a database)
classified_docs = []

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

google_bp = make_google_blueprint(
    client_id="96146810234-ibpncsnk05a84n8r4off6ac3g3a5qc1l.apps.googleusercontent.com",
    client_secret="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",
    scope=["https://www.googleapis.com/auth/drive"],
    redirect_to="home"
)
app.register_blueprint(google_bp, url_prefix="/login")

@app.route("/home")
def home():
    if not google.authorized:
        return redirect(url_for("google.login"))
    return jsonify({"message": "Successfully authenticated with Google!"})

@app.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            # Extract text from file
            text = extract_text_from_file(file_path)

            # Classify using DistilBERT
            category, subcategory = classify_document(text)

            # Add to temporary storage
            classified_docs.append({
                "name": filename,
                "type": file.filename.split('.')[-1].upper(),
                "category": category,
                "subcategory": subcategory,
                "file_path": file_path  # Store file path instead of FileStorage object
            })

            return jsonify({
                "message": "File successfully processed and classified.",
                "predictions": {
                    "category": category,
                    "subcategory": subcategory
                }
            }), 200
        except Exception as e:
            return jsonify({"message": f"Error processing file: {str(e)}"}), 500

    return jsonify({"message": "Invalid file format."}), 400

@app.route('/get_classified_docs', methods=['GET'])
def get_classified_docs():
    # Extract only the relevant details (e.g., file name and file path) to make them JSON serializable
    docs_data = [{'name': doc['name'], 'category': doc['category'], 'subcategory': doc['subcategory'], 'type': doc['type'], 'file_path': doc['file_path']} for doc in classified_docs]
    return jsonify({"docs": docs_data}), 200

@app.route("/update_label", methods=["POST"])
def update_label():
    data = request.get_json()

    if 'name' not in data or 'category' not in data or 'subcategory' not in data:
        return jsonify({"message": "Missing required fields: name, category, and subcategory."}), 400

    doc = next((doc for doc in classified_docs if doc['name'] == data['name']), None)

    if not doc:
        return jsonify({"message": "Document not found."}), 404

    doc['category'] = data['category']
    doc['subcategory'] = data['subcategory']

    return jsonify({"message": "Document updated successfully.", "document": doc}), 200

@app.route("/save_todrive", methods=["POST"])
def save_todrive():
    if not classified_docs:
        return jsonify({"message": "No classified documents available."}), 400

    if not google.authorized:
        return redirect(url_for("google.login"))

    service = google.session
    failed_uploads, successful_uploads = [], []

    for doc in classified_docs:
        if not os.path.exists(doc['file_path']):
            failed_uploads.append({"name": doc['name'], "error": "File not found."})
            continue

        try:
            drive_file_id = upload_file_to_drive(service, doc['file_path'], doc['category'], doc['subcategory'])
            successful_uploads.append({"name": doc['name'], "drive_file_id": drive_file_id})
        except Exception as e:
            failed_uploads.append({"name": doc['name'], "error": str(e)})

    if successful_uploads:
        return jsonify({
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads
        }), 200
    else:
        return jsonify({
            "message": "No successful uploads.",
            "failed_uploads": failed_uploads
        }), 500

@app.route('/authorize')
def authorize():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    flow.redirect_uri = 'http://127.0.0.1:5000/oauth2callback'
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    flow.redirect_uri = 'http://127.0.0.1:5000/oauth2callback'
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    with open('token.json', 'w') as token_file:
        token_file.write(credentials.to_json())

    return jsonify({"message": "Authentication successful!"})

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)
    app.run(debug=True)
