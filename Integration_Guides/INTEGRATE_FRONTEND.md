# Frontend Integration Guide — MediVault AI Pipeline

## Overview

The AI pipeline (prescription upload, OCR, NLP, drug interactions, voice, lab reports) runs as a standalone Flask app. Your React/Next.js frontend embeds it via **iframe**.

---

## Step 1: Embed the AI Tool in Your App

Add an iframe wherever users need to upload prescriptions or lab reports:

```html
<iframe
  src="http://AI_SERVER:5000/?patient_id=123&doctor_id=5"
  width="100%"
  height="800px"
  style="border: none; border-radius: 16px;"
  title="MediVault AI Pipeline"
></iframe>
```

### URL Parameters You Must Pass

| Parameter    | Type    | Required | Description                          |
|-------------|---------|----------|--------------------------------------|
| `patient_id` | integer | Yes      | Logged-in patient's ID from your DB  |
| `doctor_id`  | integer | Yes      | Prescribing doctor's ID from your DB |

These IDs are used when saving prescriptions and lab reports to the database.

---

## Step 2: React Component Example

```jsx
import React from 'react';

function PrescriptionUpload({ patientId, doctorId }) {
  const aiUrl = `http://AI_SERVER:5000/?patient_id=${patientId}&doctor_id=${doctorId}`;

  return (
    <div style={{ width: '100%', height: '800px' }}>
      <iframe
        src={aiUrl}
        width="100%"
        height="100%"
        style={{ border: 'none', borderRadius: '16px' }}
        title="MediVault AI Prescription Upload"
      />
    </div>
  );
}

export default PrescriptionUpload;
```

---

## Step 3: Next.js Page Example

```jsx
'use client';
import { useSearchParams } from 'next/navigation';

export default function UploadPage() {
  const params = useSearchParams();
  const patientId = params.get('pid') || 1;
  const doctorId = params.get('did') || 1;

  return (
    <main>
      <h1>Upload Prescription</h1>
      <iframe
        src={`http://AI_SERVER:5000/?patient_id=${patientId}&doctor_id=${doctorId}`}
        width="100%"
        height="800px"
        style={{ border: 'none' }}
      />
    </main>
  );
}
```

---

## Step 4: Button to Open/Close the AI Tool

```html
<button onclick="openMediVaultAI()">📄 Upload Prescription</button>

<div id="ai-container" style="display:none;">
  <button onclick="closeMediVaultAI()" style="float:right;">✕ Close</button>
  <iframe id="ai-frame" width="100%" height="800px" style="border:none;"></iframe>
</div>

<script>
function openMediVaultAI() {
  const patientId = 123; // Get from your auth/session
  const doctorId = 5;
  document.getElementById('ai-frame').src =
    `http://AI_SERVER:5000/?patient_id=${patientId}&doctor_id=${doctorId}`;
  document.getElementById('ai-container').style.display = 'block';
}

function closeMediVaultAI() {
  document.getElementById('ai-container').style.display = 'none';
  document.getElementById('ai-frame').src = '';
}
</script>
```

---

## What the AI Tool Does (User Flow Inside the iframe)

When embedded, the user sees a 5-step sidebar:

| Step | Name | What Happens |
|------|------|-------------|
| 1 | **Upload** | User uploads a prescription image/PDF. OCR extracts text (Textract). User can edit extracted text. |
| 2 | **Extract** | AI normalizes text + extracts medications, conditions, allergies (Bedrock Nova Micro). Saves to database. |
| 3 | **Check** | Optional drug interaction check using Knowledge Base RAG. Shows severity + citations. |
| 4 | **Voice** | Optional audio summary in regional language (Polly: Aditi, Raveena, Joanna, Matthew). |
| 5 | **Lab Reports** | Separate tab — upload lab reports (Blood, Urine, Thyroid, etc.) to S3 + database. |

---

## What Gets Saved to Database

After the user completes the flow, the following data lands in MySQL:

- `prescriptions` table — patient_id, doctor_id, prescribed_date, FHIR bundle (JSON)
- `medicines` table — unique medication names (name, dosage, frequency, duration)
- `prescription_medicines` — links prescriptions to medicines
- `lab_reports` table — patient_id, test_date, report_type, lab_name, S3 URL

---

## If You Want Direct API Access Instead of iframe

You can call the AI endpoints directly from your frontend:

| Method | Endpoint | What It Does |
|--------|----------|-------------|
| POST | `/ai/process-document` | Upload image, get OCR text + confidence |
| POST | `/ai/normalize-and-extract` | Normalize text, extract entities |
| POST | `/ai/check-interaction` | Check drug interactions |
| POST | `/ai/tts` | Generate audio summary |
| POST | `/ai/save-prescription` | Save prescription to DB |
| POST | `/ai/save-lab-report` | Upload lab report to S3 + DB |
| GET | `/ai/check-database` | Check DB connection + stats |
| GET | `/ai/test-bedrock` | Check AI service status |

See `FRONTEND_DATAFLOW.json` for exact request/response field mappings.
See `API_SCHEMA.json` for full endpoint definitions.

---

## CORS Is Already Configured

The AI backend allows requests from:
- `http://localhost:3000` (React dev server)
- `http://localhost:3001`
- `*` (all origins during development)

iframe embedding is also enabled via `X-Frame-Options: ALLOWALL`.

---

## How to Run the AI Backend

```bash
cd MediVault/backend
pip install -r requirements.txt
python app.py
# Runs on http://localhost:5000
```

### Required Environment Variables
```
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=ap-south-1
```

### Quick Health Check
Open `http://localhost:5000/` in browser — should show the AI pipeline UI.

---

## Questions?

Contact the AI pipeline developer. Reference files:
- `FRONTEND_DATAFLOW.json` — UI field mappings
- `API_SCHEMA.json` — endpoint schemas
- `AI_ReadMe.md` — full technical documentation
