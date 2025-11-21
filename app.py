"""
Bitcoin Dada / DadaDevs Certificate Signature System
COMPLETE MVP - NO ADMIN AUTHENTICATION
"""

import os
import io
import csv
import json
import base64
import sqlite3
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

from flask import (
    Flask, request, send_file, render_template, redirect,
    url_for, flash, jsonify, abort
)
from nacl.signing import SigningKey, VerifyKey
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader

# Load environment variables
load_dotenv()

# Configuration
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", 5000))
DB_PATH = os.environ.get("DB_PATH", "certs.db")
KEY_FILE = os.environ.get("KEY_FILE", "signing_key.base64")
FLASK_SECRET = os.environ.get("FLASK_SECRET", "production-secret-change-me")

# Database Functions
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS certs (
            id TEXT PRIMARY KEY,
            data TEXT,
            signature TEXT,
            revoked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.commit()
    conn.close()

def db_insert(cert_id, data_json, signature_b64):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO certs (id, data, signature) VALUES (?, ?, ?)",
              (cert_id, data_json, signature_b64))
    conn.commit()
    conn.close()

def db_get(cert_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT data, signature, revoked FROM certs WHERE id=?", (cert_id,))
    row = c.fetchone()
    conn.close()
    return row

def db_list_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, data, signature, revoked FROM certs ORDER BY rowid DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def db_set_revoked(cert_id, revoked=True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE certs SET revoked=? WHERE id=?", (1 if revoked else 0, cert_id))
    conn.commit()
    conn.close()

def db_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM certs")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM certs WHERE revoked=1")
    revoked = c.fetchone()[0]
    conn.close()
    return {"total": total, "revoked": revoked, "active": total - revoked}

# Signing Keys
def load_or_create_key():
    if not os.path.exists(KEY_FILE):
        sk = SigningKey.generate()
        with open(KEY_FILE, "wb") as f:
            f.write(base64.b64encode(sk.encode()))
        print(f"[INFO] Generated new signing key and saved to {KEY_FILE}")
    else:
        with open(KEY_FILE, "rb") as f:
            sk = SigningKey(base64.b64decode(f.read()))
    return sk

def serialize_data(d: dict) -> bytes:
    return json.dumps(d, separators=(",", ":"), sort_keys=True).encode()

# Flask App
app = Flask(__name__)
app.secret_key = FLASK_SECRET

@app.template_filter('fromjson')
def fromjson_filter(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return value

# Initialize database and keys
init_db()
sk = load_or_create_key()
vk = sk.verify_key
VK_B64 = base64.b64encode(vk.encode()).decode()

# PDF Generation
def create_certificate_pdf(data: dict, signature_b64: str, verify_url: str) -> bytes:
    buffer = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(width, height))
    
    # Background
    c.setFillColorRGB(0.95, 0.95, 0.98)
    c.rect(0, 0, width, height, fill=1)
    
    # Border
    c.setStrokeColorRGB(0.2, 0.4, 0.8)
    c.setLineWidth(8)
    c.rect(20, 20, width-40, height-40, stroke=1, fill=0)
    
    # Header
    c.setFillColorRGB(0.1, 0.3, 0.6)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width/2, height - 120, "BITCOIN DADA")
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width/2, height - 170, "Certificate of Completion")
    
    # Content
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height - 250, "This certifies that")
    
    c.setFillColorRGB(0.1, 0.3, 0.6)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width/2, height - 300, data.get('name', '').upper())
    
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica", 18)
    c.drawCentredString(width/2, height - 350, f"has successfully completed the {data.get('course', '')}")
    c.drawCentredString(width/2, height - 380, f"Cohort: {data.get('cohort', '')}")
    
    # Details
    c.setFont("Helvetica", 12)
    c.drawString(80, 200, f"Certificate ID: {data.get('id')}")
    c.drawString(80, 180, f"Issued: {data.get('issued_at')}")
    c.drawString(80, 160, f"Signature: {signature_b64[:50]}...")
    
    # QR Code
    qr = qrcode.make(verify_url)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    
    c.drawImage(ImageReader(qr_buffer), width - 220, 90, width=160, height=160)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(width - 220, 70, "Scan to verify authenticity")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

# Routes - NO AUTHENTICATION AT ALL
@app.route("/")
def index():
    stats = db_stats()
    return render_template('index.html', vk=VK_B64, stats=stats)

@app.route("/create", methods=["GET", "POST"])
def create_certificate():
    """Certificate creation page - NO AUTH"""
    if request.method == "GET":
        return render_template('create.html')
    
    try:
        name = request.form.get("name", "").strip()
        course = request.form.get("course", "").strip()
        cohort = request.form.get("cohort", "").strip()
        
        if not name:
            flash("Name is required", "error")
            return redirect(url_for('create_certificate'))
        
        # Generate certificate
        cert_id = str(uuid.uuid4())
        data = {
            "id": cert_id,
            "name": name,
            "course": course,
            "cohort": cohort,
            "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        # Create digital signature
        payload = serialize_data(data)
        sig = sk.sign(payload).signature
        sig_b64 = base64.b64encode(sig).decode()

        # Save to database
        db_insert(cert_id, json.dumps(data), sig_b64)

        # Generate PDF with QR code
        verify_url = request.url_root.rstrip("/") + url_for("verify_certificate", cert_id=cert_id)
        pdf_bytes = create_certificate_pdf(data, sig_b64, verify_url)
        
        flash(f"Certificate created successfully for {name}!", "success")
        return send_file(io.BytesIO(pdf_bytes), 
                        mimetype="application/pdf", 
                        as_attachment=True,
                        download_name=f"certificate_{name.replace(' ', '_')}.pdf")
                        
    except Exception as e:
        flash(f"Error creating certificate: {str(e)}", "error")
        return redirect(url_for('create_certificate'))

@app.route("/bulk_create", methods=["GET", "POST"])
def bulk_create():
    """Bulk certificate creation page - NO AUTH"""
    if request.method == "GET":
        return render_template('bulk_create.html')
    
    try:
        if "csvfile" not in request.files:
            flash("CSV file required", "error")
            return redirect(url_for('bulk_create'))
            
        f = request.files["csvfile"]
        if not f or f.filename == '':
            flash("No file selected", "error")
            return redirect(url_for('bulk_create'))

        if not f.filename.lower().endswith('.csv'):
            flash("Please upload a CSV file", "error")
            return redirect(url_for('bulk_create'))

        # Read CSV
        content = f.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        
        required_columns = ['name']
        if not all(col in reader.fieldnames for col in required_columns):
            flash("CSV must contain 'name' column", "error")
            return redirect(url_for('bulk_create'))

        # Create zip file
        import zipfile
        zip_io = io.BytesIO()
        created_count = 0
        
        with zipfile.ZipFile(zip_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for row_num, row in enumerate(reader, 1):
                try:
                    name = row.get('name', '').strip()
                    if not name:
                        continue
                        
                    course = row.get('course', '').strip()
                    cohort = row.get('cohort', '').strip()
                    
                    cert_id = str(uuid.uuid4())
                    data = {
                        "id": cert_id,
                        "name": name,
                        "course": course,
                        "cohort": cohort,
                        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    }
                    
                    payload = serialize_data(data)
                    sig = sk.sign(payload).signature
                    sig_b64 = base64.b64encode(sig).decode()
                    
                    db_insert(cert_id, json.dumps(data), sig_b64)
                    verify_url = request.url_root.rstrip("/") + url_for("verify_certificate", cert_id=cert_id)
                    pdf_bytes = create_certificate_pdf(data, sig_b64, verify_url)
                    
                    filename = f"certificate_{name.replace(' ', '_')}.pdf"
                    zf.writestr(filename, pdf_bytes)
                    created_count += 1
                    
                except Exception as e:
                    flash(f"Error processing row {row_num}: {str(e)}", "warning")
                    continue

        zip_io.seek(0)
        flash(f"Successfully created {created_count} certificates!", "success")
        return send_file(zip_io, 
                        mimetype="application/zip", 
                        as_attachment=True, 
                        download_name="bitcoin_dada_certificates.zip")
                        
    except Exception as e:
        flash(f"Error processing bulk creation: {str(e)}", "error")
        return redirect(url_for('bulk_create'))

@app.route("/verify")
def verify_home():
    """Certificate verification home page"""
    return render_template('verify.html')

@app.route("/verify/<cert_id>")
def verify_certificate(cert_id):
    """Verify a specific certificate"""
    row = db_get(cert_id)
    if not row:
        return render_template('verify_result.html', 
                             status="not_found",
                             message="Certificate not found"), 404
        
    data_json, signature_b64, revoked = row
    data = json.loads(data_json)
    payload = serialize_data(data)
    
    try:
        VerifyKey(base64.b64decode(VK_B64)).verify(payload, base64.b64decode(signature_b64))
        if revoked:
            status = "revoked"
            message = "This certificate has been revoked by the issuer"
        else:
            status = "authentic"
            message = "This certificate is authentic and valid"
    except Exception:
        status = "tampered"
        message = "Certificate has been tampered with or signature is invalid"
    
    return render_template('verify_result.html',
                         status=status,
                         message=message,
                         data=data,
                         cert_id=cert_id,
                         vk=VK_B64)

@app.route("/upload_verify", methods=["GET", "POST"])
def upload_verify():
    """Verify certificate by uploading JSON file"""
    if request.method == "GET":
        return render_template('upload_verify.html')
    
    try:
        if 'file' not in request.files or not request.files['file']:
            flash("Please select a file", "error")
            return redirect(url_for('upload_verify'))
            
        f = request.files['file']
        if not f.filename.lower().endswith('.json'):
            flash("Please upload a JSON file", "error")
            return redirect(url_for('upload_verify'))
        
        file_data = json.loads(f.read().decode('utf-8'))
        
        # Extract certificate data
        cert_id = file_data.get('id')
        data = file_data.get('data', file_data)
        signature_b64 = file_data.get('signature')
        
        if not all([cert_id, data, signature_b64]):
            flash("Invalid certificate file format", "error")
            return redirect(url_for('upload_verify'))
        
        payload = serialize_data(data)
        try:
            VerifyKey(base64.b64decode(VK_B64)).verify(payload, base64.b64decode(signature_b64))
            
            # Check if certificate exists in database and is not revoked
            db_row = db_get(cert_id)
            revoked = db_row[2] if db_row else False
            
            if revoked:
                status = "revoked"
                message = "This certificate has been revoked by the issuer"
            else:
                status = "authentic"
                message = "Certificate is authentic and valid"
                
        except Exception:
            status = "tampered"
            message = "Certificate has been tampered with or signature is invalid"
        
        return render_template('verify_result.html',
                             status=status,
                             message=message,
                             data=data,
                             cert_id=cert_id,
                             vk=VK_B64)
                             
    except json.JSONDecodeError:
        flash("Invalid JSON file", "error")
        return redirect(url_for('upload_verify'))
    except Exception as e:
        flash(f"Error processing file: {str(e)}", "error")
        return redirect(url_for('upload_verify'))

@app.route("/manage")
def manage_certificates():
    """Certificate management dashboard - NO AUTH"""
    try:
        rows = db_list_all()
        stats = db_stats()
        return render_template('manage.html', rows=rows, stats=stats)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('manage.html', rows=[], stats={"total": 0, "active": 0, "revoked": 0})

@app.route("/revoke", methods=["POST"])
def revoke_certificate():
    """Revoke a certificate - NO AUTH"""
    cert_id = request.form.get("id")
    if not cert_id:
        abort(400)
    db_set_revoked(cert_id, True)
    flash("Certificate revoked successfully", "success")
    return redirect(url_for('manage_certificates'))

@app.route("/unrevoke", methods=["POST"])
def unrevoke_certificate():
    """Unrevoke a certificate - NO AUTH"""
    cert_id = request.form.get("id")
    if not cert_id:
        abort(400)
    db_set_revoked(cert_id, False)
    flash("Certificate unrevoked successfully", "success")
    return redirect(url_for('manage_certificates'))

@app.route("/download/<cert_id>")
def download_certificate(cert_id):
    """Download a certificate PDF - NO AUTH"""
    row = db_get(cert_id)
    if not row:
        return render_template('error.html', error="Certificate Not Found"), 404
        
    data_json, signature_b64, revoked = row
    data = json.loads(data_json)
    verify_url = request.url_root.rstrip("/") + url_for("verify_certificate", cert_id=cert_id)
    pdf_bytes = create_certificate_pdf(data, signature_b64, verify_url)
    
    return send_file(io.BytesIO(pdf_bytes), 
                    mimetype="application/pdf", 
                    as_attachment=True,
                    download_name=f"certificate_{data['name'].replace(' ', '_')}.pdf")

# API Routes
@app.route("/api/certificate/<cert_id>")
def api_certificate(cert_id):
    """API endpoint to get certificate data"""
    row = db_get(cert_id)
    if not row:
        return jsonify({"error": "Certificate not found"}), 404
        
    data_json, signature_b64, revoked = row
    data = json.loads(data_json)
    
    return jsonify({
        "certificate": data,
        "signature": signature_b64,
        "revoked": bool(revoked),
        "public_key": VK_B64
    })

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', 
                         error="Page Not Found",
                         message="The requested page could not be found."), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html',
                         error="Internal Server Error",
                         message="An unexpected error has occurred."), 500

if __name__ == "__main__":
    print(f"🚀 Starting Bitcoin Dada Certificate System on http://{APP_HOST}:{APP_PORT}")
    print(f"📝 Create certificates: http://{APP_HOST}:{APP_PORT}/create")
    print(f"🔍 Verify certificates: http://{APP_HOST}:{APP_PORT}/verify")
    print(f"📊 Manage certificates: http://{APP_HOST}:{APP_PORT}/manage")
    app.run(host=APP_HOST, port=APP_PORT, debug=True)