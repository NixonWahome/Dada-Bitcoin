# Bitcoin Dada Digital Certificate System

A secure, production-ready digital certificate issuance and verification system built for Bitcoin Dada and DadaDevs.

## 🚀 Features

- **🔐 Cryptographic Security** - Ed25519 digital signatures
- **📱 QR Code Verification** - Instant verification via QR codes
- **🚫 Certificate Revocation** - Admin can revoke compromised certificates
- **📊 Admin Dashboard** - Complete management interface
- **📄 Bulk Issuance** - Generate multiple certificates via CSV upload
- **🌐 Web Verification** - Public verification portal
- **📱 Mobile Responsive** - Works on all devices

## 🛠 How It Works

### Core Security Architecture

1. **Unique Identifiers**: Each certificate gets a UUIDv4
2. **Deterministic Signing**: Certificate data is serialized in canonical JSON format
3. **Ed25519 Signatures**: Cryptographically signed using PyNaCl library
4. **QR Code Integration**: Each PDF contains QR code linking to verification page
5. **Database Storage**: Signatures stored in SQLite with revocation support

### Technical Stack

- **Backend**: Flask (Python)
- **Cryptography**: Ed25519 via PyNaCl
- **Database**: SQLite
- **PDF Generation**: ReportLab
- **QR Codes**: qrcode library
- **Frontend**: Bootstrap 5 + Jinja2 templates

## 📋 Steps to Issue a Certificate

2. **Single Certificate**
- Fill in student name, course, and cohort
- Click "Generate Certificate"
- PDF downloads automatically

3. **Bulk Certificates**
- Prepare CSV file with columns: `name,course,cohort`
- Upload CSV file
- Download ZIP file containing all certificates

### CSV Format Example:
```csv
name,course,cohort
John Doe,Bitcoin Development,Cohort 2024
Jane Smith,Lightning Network,Cohort 2024

### For Administrators:

1. **Access Admin Portal**
