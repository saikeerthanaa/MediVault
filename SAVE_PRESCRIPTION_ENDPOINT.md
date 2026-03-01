# Save Prescription Endpoint Documentation

## Overview

The `POST /ai/save-prescription` endpoint saves a patient-confirmed prescription to the database with automatic drug interaction checking and FHIR bundle generation.

This endpoint is called **after the HITL (Human-in-the-Loop) review step**, when the patient has:
1. ✅ Verified the OCR-extracted text
2. ✅ Corrected any inaccuracies
3. ✅ Confirmed the prescription is accurate

## Process Flow

```
Patient confirms prescription (HITL complete)
              ↓
POST /ai/save-prescription
              ↓
    ┌─────────┴──────────┐
    ↓                    ↓
Step 1: MySQL Save   Step 2: Check Interactions
    ↓                    ↓
Step 3: FHIR Generate & Update
    ↓
Return combined response
```

## Request Format

### Endpoint
```
POST /ai/save-prescription
Content-Type: application/json
```

### Request Body

```json
{
  "patient_id": 1,
  "doctor_id": 2,
  "s3_image_url": "https://bucket.s3.amazonaws.com/prescriptions/rx-123.jpg",
  "ocr_confidence": 0.87,
  "reviewed_text": "Ibuprofen 200mg twice daily for 7 days...",
  "entities": {
    "medications": [
      {
        "name": "Ibuprofen",
        "dosage": "200 mg",
        "frequency": "Twice daily",
        "duration": "For 7 days"
      },
      {
        "name": "Omeprazole",
        "dosage": "20 mg",
        "frequency": "Once daily",
        "duration": ""
      }
    ],
    "conditions": [
      "Gastritis",
      "Inflammation"
    ],
    "allergies": [
      "Penicillin"
    ]
  }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `patient_id` | Integer | Yes | Patient ID from database |
| `doctor_id` | Integer | Yes | Doctor ID from database |
| `s3_image_url` | String | Yes | S3 URL of original prescription image |
| `ocr_confidence` | Float | No | Textract confidence (0-1) |
| `reviewed_text` | String | No | Patient-reviewed OCR text |
| `entities` | Object | Yes | Extracted medication/condition/allergy data |
| `entities.medications[]` | Array | Yes | List of medications (can be empty) |
| `entities.conditions[]` | Array | No | List of medical conditions |
| `entities.allergies[]` | Array | No | List of allergies |

### Medication Object

```json
{
  "name": "Ibuprofen",
  "dosage": "200 mg",
  "frequency": "Twice daily",
  "duration": "For 7 days"
}
```

All fields are strings. Empty strings are acceptable.

## Response Format

### Success Response (HTTP 200)

```json
{
  "ok": true,
  "prescription_id": 42,
  "medicines_saved": 2,
  "interactions": [
    {
      "pair": ["Ibuprofen", "Warfarin"],
      "severity": "high",
      "summary": "Major drug interaction detected",
      "description": "NSAIDs increase bleeding risk when combined with anticoagulants",
      "action": "Consider alternative pain reliever or adjust Warfarin monitoring"
    }
  ],
  "fhir_bundle_saved": true,
  "warnings": []
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `ok` | Boolean | Success flag |
| `prescription_id` | Integer | New prescription ID (primary key) |
| `medicines_saved` | Integer | Number of unique medications saved |
| `interactions[]` | Array | List of significant drug interactions (severity = high/medium) |
| `fhir_bundle_saved` | Boolean | Whether FHIR bundle was successfully generated and saved |
| `warnings[]` | Array | Non-fatal warnings (async operations failures) |

### Interaction Object

| Field | Type | Description |
|-------|------|-------------|
| `pair` | Array[2] | The two medication names being checked |
| `severity` | String | "high" or "medium" (low/unknown are filtered out) |
| `summary` | String | Short description of interaction |
| `description` | String | Detailed explanation |
| `action` | String | Recommended clinical action |

### Error Response (HTTP 400/500)

```json
{
  "ok": false,
  "error": "Missing required field: patient_id"
}
```

## Step-by-Step Process

### Step 1: Save to MySQL Database

The endpoint executes this sequence in a **single transaction**:

#### 1a. Insert Prescription Row
```sql
INSERT INTO prescriptions 
(patient_id, doctor_id, source, prescribed_date, s3_image_url, fhir_json, created_at)
VALUES (1, 2, 'AI', '2026-03-01', 'https://...', NULL, NOW())
```

**Fields:**
- `source` = 'AI' (always)
- `prescribed_date` = today's date (YYYY-MM-DD)
- `fhir_json` = NULL (updated in Step 3)
- Returns: `prescription_id` (used for all subsequent operations)

#### 1b. Insert/Link Medicines

For **each medication** in the request:

```sql
-- Ensure medicine exists in master table
INSERT IGNORE INTO medicines (medicine_name) VALUES ('Ibuprofen')

-- Get the medicine_id
SELECT medicine_id FROM medicines WHERE medicine_name = 'Ibuprofen'

-- Link to this prescription
INSERT INTO prescription_medicines 
(prescription_id, medicine_id, dosage, frequency, duration)
VALUES (42, 5, '200 mg', 'Twice daily', 'For 7 days')
```

**Result:** Each unique medication is saved only once in `medicines` table, and linked via `prescription_medicines`.

#### 1c. Transaction Handling

- If any operation succeeds: ✅ **COMMIT** all changes
- If any operation fails: ❌ **ROLLBACK** entire transaction (database remains clean)

### Step 2: Auto Drug Interaction Check

**Runs AFTER Step 1 succeeds** (doesn't block the save).

For all pairs of medications:
- Check medication A vs. [B, C, D, ...]
- Check medication B vs. [A, C, D, ...]
- Check medication C vs. [A, B, D, ...]
- etc.

**Example:**
```
Medications: [Ibuprofen, Warfarin, Aspirin]

Checks:
1. Ibuprofen vs [Warfarin, Aspirin]      → severity=high (Warfarin interaction)
2. Warfarin vs [Ibuprofen, Aspirin]      → severity=high (Ibuprofen interaction)
3. Aspirin vs [Ibuprofen, Warfarin]      → severity=medium (Warfarin interaction)

De-duplicate on canonical pair (sorted names):
→ [Ibuprofen, Warfarin] = high
→ [Aspirin, Warfarin] = medium
→ [Aspirin, Ibuprofen] = low (filtered out, only high/medium included)
```

**API Call:**
```python
result = kb_rag.check_interaction(new_med="Ibuprofen", 
                                  current_meds=["Warfarin", "Aspirin"])
```

**Filtering:**
- Only "high" and "medium" severity interactions are returned
- "low" and "unknown" severity are ignored
- De-duplicates by canonical pair

**If interaction check fails:**
- Warning is added to `warnings[]`
- Prescription is NOT rolled back (save persists)
- Response continues with `fhir_bundle_saved = true/false`

### Step 3: Generate FHIR Bundle

**Also runs AFTER Step 1 succeeds** (async from interaction check).

```python
# Create FHIR 4.0 compliant bundle
bundle = FHIRBundleGenerator.create_bundle(
    entities={
        "medications": medications,
        "conditions": conditions,
        "allergies": allergies
    },
    patient_id=str(patient_id)
)

# Convert to JSON
bundle_json = FHIRBundleGenerator.bundle_to_json(bundle)

# Update prescription row
UPDATE prescriptions 
SET fhir_json = (bundle_json)
WHERE prescription_id = 42
```

**If FHIR generation fails:**
- `fhir_bundle_saved = false`
- Warning is added to `warnings[]`
- Prescription is NOT rolled back (save persists)
- Response is still successful (HTTP 200)

## Database Configuration

Add these environment variables to `.env`:

```bash
# MySQL Connection
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=medivault_user
MYSQL_PASSWORD=medivault_password
MYSQL_DB=medivault_db
```

### Database Schema

**Tables Used:**

1. **prescriptions**
   ```sql
   prescription_id (PK)  | patient_id | doctor_id | source | prescribed_date | s3_image_url | fhir_json | created_at
   42                    | 1          | 2         | AI     | 2026-03-01      | https://...  | {...}     | NOW()
   ```

2. **medicines**
   ```sql
   medicine_id (PK) | medicine_name
   5                | Ibuprofen
   6                | Omeprazole
   ```

3. **prescription_medicines**
   ```sql
   id (PK) | prescription_id | medicine_id | dosage      | frequency      | duration
   100     | 42             | 5           | 200 mg      | Twice daily    | For 7 days
   101     | 42             | 6           | 20 mg       | Once daily     | 
   ```

## Example Requests

### Basic Prescription (Single Medication)

```bash
curl -X POST http://localhost:5000/ai/save-prescription \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "doctor_id": 2,
    "s3_image_url": "s3://bucket/rx.jpg",
    "entities": {
      "medications": [
        {"name": "Aspirin", "dosage": "100 mg", "frequency": "Once daily", "duration": ""}
      ],
      "conditions": [],
      "allergies": []
    }
  }'
```

### High-Risk Prescription (Multiple Interactions)

```bash
curl -X POST http://localhost:5000/ai/save-prescription \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 2,
    "doctor_id": 1,
    "s3_image_url": "s3://bucket/rx-high-risk.jpg",
    "entities": {
      "medications": [
        {"name": "Warfarin", "dosage": "5 mg", "frequency": "Once daily", "duration": "Ongoing"},
        {"name": "Ibuprofen", "dosage": "400 mg", "frequency": "Twice daily", "duration": "7 days"},
        {"name": "Aspirin", "dosage": "81 mg", "frequency": "Once daily", "duration": "Ongoing"}
      ],
      "conditions": ["Atrial fibrillation"],
      "allergies": []
    }
  }'
```

**Expected Response:**
```json
{
  "ok": true,
  "prescription_id": 43,
  "medicines_saved": 3,
  "interactions": [
    {
      "pair": ["Ibuprofen", "Warfarin"],
      "severity": "high",
      "summary": "Major drug interaction detected",
      "description": "NSAIDs significantly increase bleeding risk with anticoagulants",
      "action": "Avoid NSAIDs; use acetaminophen or paracetamol instead"
    },
    {
      "pair": ["Aspirin", "Warfarin"],
      "severity": "medium",
      "summary": "Moderate interaction possible",
      "description": "Increased bleeding risk; monitor INR closely",
      "action": "Monitor INR more frequently"
    }
  ],
  "fhir_bundle_saved": true,
  "warnings": []
}
```

## Error Handling

### Missing Required Field
```json
{
  "ok": false,
  "error": "Missing required field: patient_id"
}
```
**Status:** 400 Bad Request

### Database Connection Failure
```json
{
  "ok": false,
  "error": "Database error: Connection failed to localhost:3306"
}
```
**Status:** 500 Internal Server Error

### Partial Success (Save OK, FHIR Failed)
```json
{
  "ok": true,
  "prescription_id": 42,
  "medicines_saved": 2,
  "interactions": [...],
  "fhir_bundle_saved": false,
  "warnings": ["FHIR generation failed: Missing required field 'status'"]
}
```
**Status:** 200 OK (prescription still saved)

## Testing

### Run Unit Tests
```bash
cd tests/
python test_save_prescription.py
```

### Test with cURL
```bash
# Test 1: Simple prescription
curl -X POST http://localhost:5000/ai/save-prescription \
  -H "Content-Type: application/json" \
  -d @- << 'EOF'
{
  "patient_id": 1,
  "doctor_id": 1,
  "s3_image_url": "s3://bucket/test.jpg",
  "entities": {
    "medications": [{"name": "Aspirin", "dosage": "100mg", "frequency": "daily", "duration": ""}],
    "conditions": [],
    "allergies": []
  }
}
EOF
```

## Dependencies

- **PyMySQL** - MySQL database driver
- **FHIRBundleGenerator** - FHIR bundle creation
- **KBRagService** - Drug interaction checking

Install via:
```bash
pip install PyMySQL==1.1.0
# or update requirements.txt
pip install -r backend/requirements.txt
```

## Performance Characteristics

| Operation | Time | Blocking |
|-----------|------|----------|
| MySQL save | ~100ms | ✅ Yes (blocking) |
| Interaction check | ~500ms-2s | ❌ No (async post-save) |
| FHIR generation | ~200ms | ❌ No (async post-save) |
| Total response time | ~100-150ms | Yes (only DB write) |

**Note:** The endpoint returns quickly after database save succeeds. Interaction checking and FHIR generation happen in parallel and don't affect response time.

## Security Considerations

- ✅ All database queries use parameterized statements (SQL injection protected)
- ✅ Transaction rollback on failure (data consistency)
- ✅ Input validation (required fields checked)
- ✅ Connection pooling via context managers
- ⚠️ TODO: Add authentication/authorization before production
- ⚠️ TODO: Add rate limiting
- ⚠️ TODO: Add audit logging

## Monitoring & Debugging

Enable debug logging:
```bash
export DEBUG_AI=true
python backend/app.py
```

**Log output:**
```
✓ Saved prescription 42 with 2 medicines
✓ Found 1 significant drug interactions
✓ FHIR bundle generated and saved for prescription 42
```

## Troubleshooting

### "Database connection failed"
- Check MySQL is running: `mysql -u root -p`
- Verify credentials in `.env`
- Check network connectivity to MYSQL_HOST:MYSQL_PORT

### "Missing field in FHIR"
- Ensure medications have at least `name` field
- Conditions/allergies can be empty arrays
- Check FHIRBundleGenerator for required fields

### "Interaction check failed"
- Verify KBRagService is initialized
- Check AWS credentials
- Ensure knowledge base is available

## Future Enhancements

- [ ] Batch save multiple prescriptions
- [ ] Prescription versioning/amendments
- [ ] Audit trail for all changes
- [ ] Real-time interaction alerts
- [ ] Email/SMS notifications for high-risk interactions
- [ ] Integration with electronic health records (EHR) systems
