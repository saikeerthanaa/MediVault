import io
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, Response, send_file, send_from_directory
from flask_cors import CORS
from config import Config

from services.textract_service import TextractService
from services.bedrock_service import BedrockService, test_bedrock_connection
from services.kb_rag_service import KBRagService
from services.polly_service import PollyService
from services.db_service import DatabaseService
from utils.fhir_bundle_generator import FHIRBundleGenerator
from utils.dosage_parser import DosageParser
from utils.comprehend_medical_service import ComprehendMedicalService

def create_app():
    app = Flask(__name__, static_folder='../frontend', static_url_path='/static')
    app.config.from_object(Config)
    
    # Enable CORS for API endpoints
    CORS(app, resources={r"/ai/*": {"origins": ["http://localhost:5000", "http://localhost:3000", "http://127.0.0.1:5000", "http://127.0.0.1:3000"]}})

    textract = TextractService(app.config["AWS_REGION"])
    bedrock = BedrockService(app.config["AWS_REGION"], app.config["BEDROCK_MODEL_ID"])
    kb_rag = KBRagService(app.config["AWS_REGION"], app.config["BEDROCK_KB_ID"])
    polly = PollyService(app.config["AWS_REGION"])
    
    @app.route("/")
    def index():
        """Serve index.html"""
        return send_from_directory(app.static_folder, 'index.html')
    
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """Serve static assets"""
        return send_from_directory(app.static_folder, filename)
    # 1) Trusted Pipeline - Stage 1: Textract
    @app.post("/ai/process-document")
    def process_document():
        """
        Input: multipart/form-data with file=<image>
        Output: raw_text, confidence, requires_review
        """
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "Missing file"}), 400

        f = request.files["file"]
        image_bytes = f.read()

        tex = textract.detect_text_from_image_bytes(image_bytes)
        if not tex.get("ok"):
            return jsonify(tex), 500

        conf = float(tex.get("confidence", 0.0))
        requires_review = conf < app.config["TEXTRACT_CONFIDENCE_REVIEW_THRESHOLD"]

        return jsonify({
            "ok": True,
            "raw_text": tex["raw_text"],
            "confidence": conf,
            "requires_review": requires_review,
            "blocks": tex.get("blocks", [])  # Block-level OCR for HITL highlighting
        })

    # Test endpoint for Bedrock connectivity
    @app.get("/ai/test-bedrock")
    def test_bedrock():
        """Test Bedrock connection and return status"""
        success, message = test_bedrock_connection()
        return jsonify({
            "ok": success,
            "bedrock_status": "ACTIVE" if success else "UNAVAILABLE (Using Mock Mode)",
            "result": message
        })

    # 2) Trusted Pipeline - Stage 2+3: Bedrock normalize + entity extraction (after HITL)
    @app.post("/ai/normalize-and-extract")
    def normalize_and_extract():
        """
        Input JSON:
        {
          "reviewed_text": "...",
          "patient_verified": true,
          "ocr_confidence": 72.1,
          "debug": false (optional)
        }
        Output:
          normalized.cleaned_text, normalized.confidence, normalized.flags, normalized.corrections,
          entities (JSON),
          extraction_debug (if debug=true)
        """
        try:
            data = request.get_json(silent=True) or {}
            reviewed_text = (data.get("reviewed_text") or "").strip()
            patient_verified = bool(data.get("patient_verified", True))
            ocr_confidence = float(data.get("ocr_confidence", 0.0))
            debug_mode = bool(data.get("debug", False)) or request.args.get("debug") == "true"

            if not reviewed_text:
                return jsonify({"ok": False, "error": "reviewed_text is required"}), 400

            # Call the two-stage extraction method directly
            result = bedrock.normalize_and_extract(
                reviewed_text=reviewed_text,
                ocr_confidence=ocr_confidence,
                patient_verified=patient_verified,
                debug=debug_mode
            )

            # Flag low-confidence normalization for review
            norm_conf = float(result.get("normalized", {}).get("confidence", 0))
            needs_term_review = norm_conf < app.config["NORMALIZATION_CONFIDENCE_FLAG_THRESHOLD"]
            result["normalized"]["needs_term_review"] = needs_term_review

            return jsonify(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"ok": False, "error": f"Internal error: {str(e)}"}), 500

    # 3) Safety Engine - KB grounded interaction check
    @app.post("/ai/check-interaction")
    def check_interaction():
        """
        Input JSON (flexible field naming):
        { "new_med": "Ibuprofen", "current_meds": ["Warfarin", "Aspirin"] }
        OR
        { "new_medication": "Ibuprofen", "existing_medications": ["Warfarin", "Aspirin"] }
        """
        data = request.get_json(silent=True) or {}
        
        # Support both field naming conventions
        new_med = (data.get("new_med") or data.get("new_medication") or "").strip()
        current_meds = data.get("current_meds") or data.get("existing_medications") or []

        if not new_med:
            return jsonify({"ok": False, "error": "new_med (or new_medication) is required"}), 400
        if not isinstance(current_meds, list):
            return jsonify({"ok": False, "error": "current_meds (or existing_medications) must be a list"}), 400

        result = kb_rag.check_interaction(new_med, [str(x) for x in current_meds])
        return jsonify(result)

    # 4) Accessibility Layer - Polly TTS
    @app.post("/ai/tts")
    def tts():
        """
        Input JSON:
        { "text": "...", "voice_id": "Aditi" }
        Returns audio/mp3 bytes.
        """
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        voice_id = (data.get("voice_id") or app.config["POLLY_VOICE_ID"]).strip()

        if not text:
            return jsonify({"ok": False, "error": "text is required"}), 400

        out = polly.synthesize(text=text, voice_id=voice_id)
        if not out.get("ok"):
            return jsonify(out), 500

        return Response(out["audio_bytes"], mimetype="audio/mpeg")

    # 5) Emergency Summary - Quick access to critical patient info
    @app.post("/ai/emergency-summary")
    def emergency_summary():
        """
        Input JSON (flexible):
        {
          "medications": [...],
          "allergies": [...],
          "conditions": [...]
        }
        OR
        {
          "patient_id": "...",
          "vault_entities": {...}
        }
        
        Output: {emergency_bundle, short_text}
        """
        data = request.get_json(silent=True) or {}
        
        # Support both direct entities and vault_entities
        medications = data.get("medications") or data.get("vault_entities", {}).get("medications", [])
        allergies = data.get("allergies") or data.get("vault_entities", {}).get("allergies", [])
        conditions = data.get("conditions") or data.get("vault_entities", {}).get("conditions", [])
        patient_id = data.get("patient_id", "patient-unidentified")
        
        if not medications and not allergies and not conditions:
            return jsonify({
                "ok": True,
                "emergency_bundle": {
                    "allergies": [],
                    "current_meds": [],
                    "chronic_conditions": [],
                    "key_risks": []
                },
                "short_text": "No medications or conditions on file."
            })
        
        # Build emergency bundle from structured data only (no raw OCR)
        emergency_bundle = {
            "allergies": [
                {
                    "allergen": a.get("allergen") or a.get("name", "Unknown"),
                    "severity": a.get("severity", "unknown"),
                    "reaction": a.get("reaction", "")
                }
                for a in (allergies if isinstance(allergies, list) else [])
            ],
            "current_meds": [
                {
                    "name": m.get("name", "Unknown"),
                    "dosage": m.get("dosage", ""),
                    "frequency": m.get("frequency", ""),
                    "is_critical": m.get("is_critical", False)
                }
                for m in (medications if isinstance(medications, list) else [])
            ],
            "chronic_conditions": [
                c.get("name") or c.get("condition", "Unknown")
                for c in (conditions if isinstance(conditions, list) else [])
            ],
            "key_risks": [
                f"Allergic to {a.get('allergen') or a.get('name', 'Unknown')}"
                for a in (allergies if isinstance(allergies, list) else [])
                if a.get("severity") in ["high", "severe"]
            ]
        }
        
        # Generate short_text summary
        allergies_text = ", ".join([a.get("allergen") or a.get("name", "Unknown") for a in (allergies if isinstance(allergies, list) else [])])
        meds_text = ", ".join([m.get("name", "Unknown") for m in (medications if isinstance(medications, list) else [])])
        conditions_text = ", ".join([c.get("name") or c.get("condition", "Unknown") for c in (conditions if isinstance(conditions, list) else [])])
        
        short_text = f"Patient ID: {patient_id}. "
        if allergies_text:
            short_text += f"Allergies: {allergies_text}. "
        if meds_text:
            short_text += f"Current medications: {meds_text}. "
        if conditions_text:
            short_text += f"Chronic conditions: {conditions_text}."
        
        return jsonify({
            "ok": True,
            "emergency_bundle": emergency_bundle,
            "short_text": short_text.strip()
        })

    # 7) Save Prescription - HITL Confirmed Prescription to Database
    @app.post("/ai/save-prescription")
    def save_prescription():
        """
        Save a patient-confirmed prescription to database with auto interaction checking and FHIR generation.
        
        Input JSON:
        {
          "patient_id": 1,
          "doctor_id": 2,
          "s3_image_url": "https://...",
          "ocr_confidence": 0.87,
          "reviewed_text": "...",
          "entities": {
            "medications": [
              { "name": "Ibuprofen", "dosage": "200mg", "frequency": "Twice daily", "duration": "7 days" }
            ],
            "conditions": [],
            "allergies": []
          }
        }
        
        Process:
        1. Save to MySQL (prescriptions, medicines, prescription_medicines) in transaction
        2. Auto drug interaction check (all pairs)
        3. Generate FHIR bundle and update prescription
        
        Output:
        {
          "ok": true,
          "prescription_id": 42,
          "medicines_saved": 2,
          "interactions": [...],
          "fhir_bundle_saved": true,
          "warnings": []
        }
        """
        data = request.get_json(silent=True) or {}
        
        # Validate required fields
        required = ["patient_id", "doctor_id", "s3_image_url", "entities"]
        for field in required:
            if field not in data:
                return jsonify({
                    "ok": False,
                    "error": f"Missing required field: {field}"
                }), 400
        
        patient_id = data.get("patient_id")
        doctor_id = data.get("doctor_id")
        s3_image_url = data.get("s3_image_url")
        entities = data.get("entities", {})
        medications = entities.get("medications", [])
        conditions = entities.get("conditions", [])
        allergies = entities.get("allergies", [])
        
        warnings = []
        
        # STEP 1: Save to MySQL database
        try:
            prescribed_date = datetime.now().strftime("%Y-%m-%d")
            
            prescription_id, medicines_count, db_error = DatabaseService.save_prescription(
                patient_id=patient_id,
                doctor_id=doctor_id,
                s3_image_url=s3_image_url,
                prescribed_date=prescribed_date,
                medications=medications,
                fhir_json=None  # Will be updated in step 3
            )
            
            if db_error:
                return jsonify({
                    "ok": False,
                    "error": f"Database error: {db_error}"
                }), 500
            
            if app.config["DEBUG_AI"]:
                print(f"✓ Saved prescription {prescription_id} with {medicines_count} medicines")
            
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Failed to save prescription: {str(e)}"
            }), 500
        
        # STEP 2: Auto drug interaction check (after successful DB write)
        interactions = []
        try:
            if len(medications) > 1:
                med_names = [med.get("name", "").strip() for med in medications if med.get("name")]
                
                # Check all pairs
                interactions_set = set()
                
                for i, med1 in enumerate(med_names):
                    # Check med1 against all others
                    other_meds = med_names[:i] + med_names[i+1:]
                    
                    try:
                        result = kb_rag.check_interaction(med1, other_meds)
                        
                        if result.get("ok") and result.get("interactions"):
                            for interaction in result.get("interactions", []):
                                severity = interaction.get("severity", "unknown")
                                
                                # Only include high/medium severity
                                if severity in ["high", "medium"]:
                                    # De-duplicate: create canonical pair
                                    pair = tuple(sorted([med1, interaction.get("medication", "")]))
                                    pair_key = "|".join(pair)
                                    
                                    if pair_key not in interactions_set:
                                        interactions_set.add(pair_key)
                                        interactions.append({
                                            "pair": list(pair),
                                            "severity": severity,
                                            "summary": interaction.get("summary", "Interaction detected"),
                                            "description": interaction.get("description", ""),
                                            "action": interaction.get("action", "")
                                        })
                    except Exception as e:
                        warn = f"Interaction check failed for {med1}: {str(e)}"
                        warnings.append(warn)
                        if app.config["DEBUG_AI"]:
                            print(f"⚠ {warn}")
            
            if app.config["DEBUG_AI"] and interactions:
                print(f"✓ Found {len(interactions)} significant drug interactions")
        
        except Exception as e:
            warn = f"Drug interaction check failed: {str(e)}"
            warnings.append(warn)
            if app.config["DEBUG_AI"]:
                print(f"⚠ {warn}")
        
        # STEP 3: Generate FHIR bundle and update prescription
        fhir_bundle_saved = False
        try:
            bundle = FHIRBundleGenerator.create_bundle(
                entities={
                    "medications": medications,
                    "conditions": conditions,
                    "allergies": allergies
                },
                patient_id=str(patient_id)
            )
            
            bundle_json = FHIRBundleGenerator.bundle_to_json(bundle)
            
            success, fhir_error = DatabaseService.update_prescription_fhir(
                prescription_id=prescription_id,
                fhir_json=bundle_json
            )
            
            if success:
                fhir_bundle_saved = True
                if app.config["DEBUG_AI"]:
                    print(f"✓ FHIR bundle generated and saved for prescription {prescription_id}")
            else:
                warn = f"Failed to save FHIR bundle: {fhir_error}"
                warnings.append(warn)
                if app.config["DEBUG_AI"]:
                    print(f"⚠ {warn}")
        
        except Exception as e:
            warn = f"FHIR generation failed: {str(e)}"
            warnings.append(warn)
            if app.config["DEBUG_AI"]:
                print(f"⚠ {warn}")
        
        # Return combined response
        return jsonify({
            "ok": True,
            "prescription_id": prescription_id,
            "medicines_saved": medicines_count,
            "interactions": interactions,
            "fhir_bundle_saved": fhir_bundle_saved,
            "warnings": warnings
        })

    # Global error handlers - return JSON instead of HTML

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"ok": False, "error": "Endpoint not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": str(e),
            "type": type(e).__name__
        }), 500

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)