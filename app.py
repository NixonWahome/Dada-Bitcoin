"""
Bitcoin Dada / DadaDevs Certificate Signature System
Production-ready digital certificate system with modern UI
FIXED VERSION - With custom JSON filter
"""

import os
import io
import csv
import json
import base64
import sqlite3
import uuid
from datetime import datetime, timezone
from functools import wraps
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

# ---------- Configuration ----------
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", 5000))
DB_PATH = os.environ.get("DB_PATH", "certs.db")
KEY_FILE = os.environ.get("KEY_FILE", "signing_key.base64")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "devtoken123")
FLASK_SECRET = os.environ.get("FLASK_SECRET", "production-secret-change-me")

# ---------- Helpers: DB ----------
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

# ---------- Helpers: Signing Keys ----------
def load_or_create_key():
    env_key = os.environ.get("PRIVATE_KEY_B64")
    if env_key:
        sk = SigningKey(base64.b64decode(env_key))
        return sk
    if not os.path.exists(KEY_FILE):
        sk = SigningKey.generate()
        with open(KEY_FILE, "wb") as f:
            f.write(base64.b64encode(sk.encode()))
        print(f"[INFO] Generated new signing key and saved to {KEY_FILE}. DO NOT COMMIT THIS FILE.")
    else:
        with open(KEY_FILE, "rb") as f:
            sk = SigningKey(base64.b64decode(f.read()))
    return sk

# Deterministic serialization for signing & verifying
def serialize_data(d: dict) -> bytes:
    return json.dumps(d, separators=(",", ":"), sort_keys=True).encode()

# ---------- App & keys ----------
app = Flask(__name__)
app.secret_key = FLASK_SECRET

# Custom Jinja2 filter for JSON parsing
@app.template_filter('fromjson')
def fromjson_filter(value):
    """Convert JSON string to Python object"""
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

# ---------- Authentication ----------
def require_admin(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = request.args.get("token") or request.form.get("token") or request.headers.get("X-Admin-Token")
        if token != ADMIN_TOKEN:
            return "Unauthorized — provide ?token=ADMIN_TOKEN or X-Admin-Token header", 401
        return f(*args, **kwargs)
    return wrapped

# ---------- PDF Generation ----------
def create_certificate_pdf(data: dict, signature_b64: str, verify_url: str) -> bytes:
    buffer = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(width, height))
    
    # Background color
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
    
    # Decorative line
    c.setStrokeColorRGB(0.9, 0.5, 0.1)
    c.setLineWidth(3)
    c.line(width/2 - 150, height - 190, width/2 + 150, height - 190)
    
    # Certificate content
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
    
    # Details section
    c.setFont("Helvetica", 12)
    c.drawString(80, 200, f"Certificate ID: {data.get('id')}")
    c.drawString(80, 180, f"Issued: {data.get('issued_at')}")
    c.drawString(80, 160, f"Signature: {signature_b64[:50]}...")
    
    # QR Code
    qr = qrcode.make(verify_url)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    
    # Add QR code with border
    c.setFillColorRGB(1, 1, 1)
    c.rect(width - 220, 80, 180, 180, fill=1, stroke=0)
    c.drawImage(ImageReader(qr_buffer), width - 210, 90, width=160, height=160)
    
    # Verification note
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(width - 220, 60, "Scan to verify authenticity")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

# ---------- Routes ----------
@app.route("/")
def index():
    stats = db_stats()
    return render_template('index.html', vk=VK_B64, token=ADMIN_TOKEN, stats=stats)

@app.route("/issue", methods=["POST"])
@require_admin
def issue():
    try:
        name = request.form.get("name", "").strip()
        course = request.form.get("course", "").strip()
        cohort = request.form.get("cohort", "").strip()
        
        if not name:
            flash("Name is required", "error")
            return redirect(url_for('index'))
        
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

        verify_url = request.url_root.rstrip("/") + url_for("verify_id", cert_id=cert_id)
        pdf_bytes = create_certificate_pdf(data, sig_b64, verify_url)
        
        flash(f"Certificate issued successfully for {name}!", "success")
        return send_file(io.BytesIO(pdf_bytes), 
                        mimetype="application/pdf", 
                        as_attachment=True,
                        download_name=f"certificate_{name.replace(' ', '_')}_{cert_id[:8]}.pdf")
                        
    except Exception as e:
        flash(f"Error issuing certificate: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route("/bulk_issue", methods=["POST"])
@require_admin
def bulk_issue():
    try:
        if "csvfile" not in request.files:
            flash("CSV file required", "error")
            return redirect(url_for('index'))
            
        f = request.files["csvfile"]
        if not f or f.filename == '':
            flash("No file selected", "error")
            return redirect(url_for('index'))

        if not f.filename.lower().endswith('.csv'):
            flash("Please upload a CSV file", "error")
            return redirect(url_for('index'))

        # Read CSV
        content = f.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        
        required_columns = ['name']
        if not all(col in reader.fieldnames for col in required_columns):
            flash("CSV must contain 'name' column", "error")
            return redirect(url_for('index'))

        # Create zip file
        import zipfile
        zip_io = io.BytesIO()
        issued_count = 0
        
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
                    verify_url = request.url_root.rstrip("/") + url_for("verify_id", cert_id=cert_id)
                    pdf_bytes = create_certificate_pdf(data, sig_b64, verify_url)
                    
                    filename = f"certificate_{name.replace(' ', '_')}_{cert_id[:8]}.pdf"
                    zf.writestr(filename, pdf_bytes)
                    issued_count += 1
                    
                except Exception as e:
                    flash(f"Error processing row {row_num}: {str(e)}", "warning")
                    continue

        zip_io.seek(0)
        flash(f"Successfully issued {issued_count} certificates!", "success")
        return send_file(zip_io, 
                        mimetype="application/zip", 
                        as_attachment=True, 
                        download_name="bitcoin_dada_certificates.zip")
                        
    except Exception as e:
        flash(f"Error processing bulk issue: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route("/dashboard")
@require_admin
def dashboard():
    try:
        rows = db_list_all()
        stats = db_stats()
        return render_template('dashboard.html', rows=rows, token=ADMIN_TOKEN, stats=stats)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('dashboard.html', rows=[], token=ADMIN_TOKEN, stats={"total": 0, "active": 0, "revoked": 0})

@app.route("/revoke", methods=["POST"])
@require_admin
def revoke():
    cert_id = request.form.get("id")
    if not cert_id:
        abort(400)
    db_set_revoked(cert_id, True)
    flash("Certificate revoked successfully", "success")
    return redirect(url_for('dashboard', token=ADMIN_TOKEN))

@app.route("/unrevoke", methods=["POST"])
@require_admin
def unrevoke():
    cert_id = request.form.get("id")
    if not cert_id:
        abort(400)
    db_set_revoked(cert_id, False)
    flash("Certificate unrevoked successfully", "success")
    return redirect(url_for('dashboard', token=ADMIN_TOKEN))

@app.route("/download/<cert_id>")
@require_admin
def download(cert_id):
    row = db_get(cert_id)
    if not row:
        return render_template('error.html', error="Certificate Not Found"), 404
        
    data_json, signature_b64, revoked = row
    data = json.loads(data_json)
    verify_url = request.url_root.rstrip("/") + url_for("verify_id", cert_id=cert_id)
    pdf_bytes = create_certificate_pdf(data, signature_b64, verify_url)
    
    return send_file(io.BytesIO(pdf_bytes), 
                    mimetype="application/pdf", 
                    as_attachment=True,
                    download_name=f"certificate_{data['name'].replace(' ', '_')}_{cert_id[:8]}.pdf")

@app.route("/verify")
def verify_home():
    return render_template('verify.html')

@app.route("/verify/<cert_id>")
def verify_id(cert_id):
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
        
        # Support multiple formats
        if 'id' in file_data and 'data' in file_data and 'signature' in file_data:
            # New format
            cert_id = file_data['id']
            data = file_data['data']
            signature_b64 = file_data['signature']
        else:
            # Try old format or direct certificate data
            cert_id = file_data.get('id')
            data = file_data
            signature_b64 = file_data.get('signature')
            
            if not cert_id:
                # Look for certificate in nested structure
                for key in ['certificate', 'cert_data']:
                    if key in file_data and isinstance(file_data[key], dict):
                        cert_data = file_data[key]
                        cert_id = cert_data.get('id')
                        data = cert_data
                        signature_b64 = cert_data.get('signature')
                        break
        
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

@app.route("/api/certificate/<cert_id>")
def api_certificate(cert_id):
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
    print(f"Starting Bitcoin Dada Certificate System on http://{APP_HOST}:{APP_PORT}")
    print(f"Admin dashboard: http://{APP_HOST}:{APP_PORT}/?token={ADMIN_TOKEN}")
    app.run(host=APP_HOST, port=APP_PORT, debug=os.environ.get('DEBUG', 'False').lower() == 'true')