# Database Integration Guide — MediVault AI Pipeline

## Overview

The AI pipeline writes prescription and lab report data to **MySQL**. This guide explains the exact tables, columns, and data types so you can integrate with your database setup.

---

## Step 1: Create the Database

```sql
CREATE DATABASE IF NOT EXISTS medivault_db;
USE medivault_db;
```

---

## Step 2: Create the Tables

The AI pipeline writes to 4 tables. Run these SQL statements to create them:

### Table 1: prescriptions

```sql
CREATE TABLE IF NOT EXISTS prescriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    s3_image_url VARCHAR(255),
    prescribed_date DATE,
    fhir_bundle JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**Who writes here:** AI pipeline via `POST /ai/save-prescription`
**What it stores:** One row per uploaded prescription with the patient/doctor IDs, image URL, date, and the full FHIR bundle (HL7 FHIR 4.0 JSON).

### Table 2: medicines

```sql
CREATE TABLE IF NOT EXISTS medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Who writes here:** AI pipeline via `POST /ai/save-prescription`
**What it stores:** Unique medication names extracted by AI. Uses `INSERT IGNORE` to avoid duplicates.

### Table 3: prescription_medicines (link table)

```sql
CREATE TABLE IF NOT EXISTS prescription_medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id INT NOT NULL,
    medicine_id INT NOT NULL,
    dosage VARCHAR(100),
    frequency VARCHAR(100),
    duration VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
);
```

**Who writes here:** AI pipeline via `POST /ai/save-prescription`
**What it stores:** Links each prescription to its medicines with dosage details.

### Table 4: lab_reports

```sql
CREATE TABLE IF NOT EXISTS lab_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    test_date DATE NOT NULL,
    lab_name VARCHAR(255),
    report_type ENUM('Blood','Urine','Thyroid','Lipid','Liver','Kidney','Imaging','Other') NOT NULL,
    s3_image_url VARCHAR(255),
    ocr_text LONGTEXT,
    lab_values_json LONGTEXT,
    extracted_conditions JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_patient (patient_id),
    INDEX idx_date (test_date),
    INDEX idx_type (report_type)
);
```

**Who writes here:** AI pipeline via `POST /ai/save-lab-report`
**What it stores:** Lab report metadata + S3 file URL + OCR results.

---

## Step 3: Connection Configuration

The AI pipeline connects using these credentials (in `backend/config.py`):

```python
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "redBlue3011!")
MYSQL_DB = os.getenv("MYSQL_DB", "medivault_db")
```

### To change the database connection:

**Option A — Environment variables** (recommended):
```bash
export MYSQL_HOST=your-rds-endpoint.amazonaws.com
export MYSQL_PORT=3306
export MYSQL_USER=medivault_admin
export MYSQL_PASSWORD=your-secure-password
export MYSQL_DB=medivault_db
```

**Option B — Edit config.py** directly (for development):
```python
MYSQL_HOST = "your-rds-endpoint.amazonaws.com"
MYSQL_PASSWORD = "your-secure-password"
```

---

## Step 4: How Data Flows In

### Prescription Flow
```
User uploads image
  → AI extracts text (Textract OCR)
  → AI normalizes + extracts entities (Bedrock)
  → POST /ai/save-prescription is called
  → AI pipeline writes to MySQL:
      1. INSERT INTO prescriptions (patient_id, doctor_id, ...)
      2. INSERT IGNORE INTO medicines (name) for each medication
      3. INSERT INTO prescription_medicines (prescription_id, medicine_id, dosage, ...)
      4. UPDATE prescriptions SET fhir_bundle = ... (FHIR 4.0 JSON)
  → Returns prescription_id to frontend
```

### Lab Report Flow
```
User uploads lab report file
  → POST /ai/save-lab-report is called
  → AI pipeline:
      1. Uploads file to S3 (medivault-lab-reports bucket)
      2. INSERT INTO lab_reports (patient_id, test_date, report_type, ...)
  → Returns lab_report_id + S3 URL
```

---

## Step 5: Adding Your Own Tables

You can add your own tables to `medivault_db`. The AI pipeline only touches the 4 tables listed above.

### Suggested Foreign Keys for Your Tables

```sql
-- If you have a patients table:
ALTER TABLE prescriptions
ADD FOREIGN KEY (patient_id) REFERENCES patients(id);

ALTER TABLE lab_reports
ADD FOREIGN KEY (patient_id) REFERENCES patients(id);

-- If you have a doctors table:
ALTER TABLE prescriptions
ADD FOREIGN KEY (doctor_id) REFERENCES doctors(id);
```

### Useful Queries to Read AI Data

```sql
-- Get all prescriptions for a patient
SELECT p.id, p.prescribed_date, p.fhir_bundle, p.created_at
FROM prescriptions p
WHERE p.patient_id = 123
ORDER BY p.created_at DESC;

-- Get medications for a prescription
SELECT m.name, pm.dosage, pm.frequency, pm.duration
FROM prescription_medicines pm
JOIN medicines m ON pm.medicine_id = m.id
WHERE pm.prescription_id = 42;

-- Get all medications a patient has ever been prescribed
SELECT DISTINCT m.name, pm.dosage, pm.frequency
FROM prescriptions p
JOIN prescription_medicines pm ON p.id = pm.prescription_id
JOIN medicines m ON pm.medicine_id = m.id
WHERE p.patient_id = 123;

-- Get lab reports for a patient
SELECT id, test_date, report_type, lab_name, s3_image_url
FROM lab_reports
WHERE patient_id = 123
ORDER BY test_date DESC;

-- Count stats
SELECT
  (SELECT COUNT(*) FROM prescriptions) AS total_prescriptions,
  (SELECT COUNT(*) FROM medicines) AS unique_medications,
  (SELECT COUNT(*) FROM lab_reports) AS total_lab_reports;
```

---

## Step 6: AWS RDS Setup (Production)

For production, replace localhost MySQL with AWS RDS:

1. Create an RDS MySQL instance in AWS Console
2. Note the endpoint: `medivault-db.abc123.ap-south-1.rds.amazonaws.com`
3. Set environment variables:
   ```bash
   export MYSQL_HOST=medivault-db.abc123.ap-south-1.rds.amazonaws.com
   export MYSQL_USER=admin
   export MYSQL_PASSWORD=secure-production-password
   export MYSQL_DB=medivault_db
   ```
4. Run the CREATE TABLE statements from Step 2 on the RDS instance
5. The AI pipeline code stays exactly the same — no code changes needed

---

## Step 7: S3 Bucket for Lab Reports

Lab report files are stored in S3. The bucket is already created:

- **Bucket name:** `medivault-lab-reports`
- **Region:** `ap-south-1`
- **File key format:** `lab-reports/{patient_id}/{timestamp}_{filename}`

The AI pipeline handles all S3 uploads. You just need read access if you want to display files.

---

## What the AI Pipeline Does NOT Do

- Does NOT create `patients` or `doctors` tables — that's your responsibility
- Does NOT handle user authentication — that's the cybersecurity team's job
- Does NOT delete or update existing prescriptions — only inserts new ones
- Does NOT validate `patient_id` or `doctor_id` against your tables — it trusts the IDs passed in

---

## Verify Database Connection

After setup, run this to verify:

```bash
cd MediVault/backend
python -c "
from services.db_service import DatabaseService
with DatabaseService.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM prescriptions')
    print('Connected! Prescriptions:', cursor.fetchone()[0])
"
```

Or start the server and hit: `GET http://localhost:5000/ai/check-database`

---

## Reference Files

- `DATABASE_SCHEMA.json` — Full schema in JSON format
- `SAVE_PRESCRIPTION_ENDPOINT.md` — Detailed save-prescription endpoint docs
- `LAB_REPORTS_SETUP.md` — Lab reports feature documentation
- `backend/services/db_service.py` — Database connection code
- `backend/config.py` — All configuration variables
