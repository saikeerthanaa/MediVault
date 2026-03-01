"""
FHIR Bundle Generator
Converts extracted medical entities into minimal FHIR-compliant resources.
"""
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional


class FHIRBundleGenerator:
    """Generate FHIR-compliant bundles from extracted medical data."""
    
    @staticmethod
    def create_bundle(entities: Dict[str, List], patient_id: str = "patient-unidentified") -> Dict[str, Any]:
        """
        Create a minimal FHIR Bundle with extracted entities.
        
        Args:
            entities: Entities dict with medications, conditions, allergies
            patient_id: Patient identifier (anonymized)
        
        Returns:
            FHIR Bundle JSON
        """
        bundle_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        bundle = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": "document",
            "timestamp": timestamp,
            "entry": []
        }
        
        # Composition resource (document header)
        composition_id = str(uuid.uuid4())
        bundle["entry"].append({
            "fullUrl": f"urn:uuid:{composition_id}",
            "resource": {
                "resourceType": "Composition",
                "id": composition_id,
                "status": "final",
                "type": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": "34108-1",
                        "display": "Outpatient Note"
                    }]
                },
                "date": timestamp,
                "author": [{
                    "reference": f"Practitioner/auto"
                }],
                "title": "Medication and Condition Summary",
                "confidentiality": "N",
                "subject": {
                    "reference": f"Patient/{patient_id}"
                }
            }
        })
        
        # Add medication statements
        for med in entities.get("medications", []):
            bundle["entry"].append(
                FHIRBundleGenerator._create_medication_statement(med, patient_id)
            )
        
        # Add condition resources
        for condition in entities.get("conditions", []):
            bundle["entry"].append(
                FHIRBundleGenerator._create_condition(condition, patient_id)
            )
        
        # Add allergy intolerances
        for allergy in entities.get("allergies", []):
            bundle["entry"].append(
                FHIRBundleGenerator._create_allergy_intolerance(allergy, patient_id)
            )
        
        return bundle
    
    @staticmethod
    def _create_medication_statement(medication: Dict[str, Any], patient_id: str) -> Dict[str, Any]:
        """Create a FHIR MedicationStatement resource from extracted medication."""
        med_id = str(uuid.uuid4())
        
        # Create dosage if available
        dosage = []
        if medication.get("dosage") or medication.get("frequency"):
            dosage_str = ""
            if medication.get("dosage"):
                dosage_str += medication["dosage"]
            if medication.get("frequency"):
                dosage_str += f" {medication['frequency']}"
            
            dosage.append({
                "text": dosage_str.strip() if dosage_str else "As prescribed",
                "route": {
                    "coding": [{
                        "system": "http://snomed.info/sct",
                        "code": FHIRBundleGenerator._get_route_code(medication.get("route", "")),
                        "display": medication.get("route", "Oral")
                    }]
                } if medication.get("route") else None
            })
            # Remove None values
            dosage[0] = {k: v for k, v in dosage[0].items() if v is not None}
        
        return {
            "fullUrl": f"urn:uuid:{med_id}",
            "resource": {
                "resourceType": "MedicationStatement",
                "id": med_id,
                "status": "completed",
                "medicationCodeableConcept": {
                    "coding": [{
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "display": medication.get("name", "Unknown medication")
                    }],
                    "text": medication.get("name", "Unknown medication")
                },
                "subject": {
                    "reference": f"Patient/{patient_id}"
                },
                "dateAsserted": datetime.utcnow().isoformat() + "Z",
                "informationSource": {
                    "reference": "Device/ocr-extractor"
                },
                "dosage": dosage if dosage else [{"text": "As prescribed"}],
                "note": [{
                    "text": medication.get("notes", "")
                }] if medication.get("notes") else []
            }
        }
    
    @staticmethod
    def _create_condition(condition: Dict[str, Any], patient_id: str) -> Dict[str, Any]:
        """Create a FHIR Condition resource from extracted condition."""
        cond_id = str(uuid.uuid4())
        
        return {
            "fullUrl": f"urn:uuid:{cond_id}",
            "resource": {
                "resourceType": "Condition",
                "id": cond_id,
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active"
                    }]
                },
                "code": {
                    "coding": [{
                        "system": "http://snomed.info/sct",
                        "display": condition.get("name", "Unknown condition")
                    }],
                    "text": condition.get("name", "Unknown condition")
                },
                "subject": {
                    "reference": f"Patient/{patient_id}"
                },
                "recordedDate": datetime.utcnow().isoformat() + "Z"
            }
        }
    
    @staticmethod
    def _create_allergy_intolerance(allergy: Dict[str, Any], patient_id: str) -> Dict[str, Any]:
        """Create a FHIR AllergyIntolerance resource from extracted allergy."""
        allergy_id = str(uuid.uuid4())
        
        # Determine allergy type
        allergy_name = allergy.get("name", "Unknown")
        substance_code = FHIRBundleGenerator._get_rxnorm_code(allergy_name)
        
        return {
            "fullUrl": f"urn:uuid:{allergy_id}",
            "resource": {
                "resourceType": "AllergyIntolerance",
                "id": allergy_id,
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                        "code": "active"
                    }]
                },
                "verificationStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                        "code": "unconfirmed"  # From OCR extraction, not clinically verified
                    }]
                },
                "code": {
                    "coding": [{
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": substance_code,
                        "display": allergy_name
                    }],
                    "text": allergy_name
                },
                "patient": {
                    "reference": f"Patient/{patient_id}"
                },
                "recordedDate": datetime.utcnow().isoformat() + "Z",
                "reaction": [{
                    "manifestation": [{
                        "coding": [{
                            "system": "http://snomed.info/sct",
                            "display": "Adverse reaction"
                        }]
                    }]
                }]
            }
        }
    
    @staticmethod
    def _get_route_code(route: str) -> str:
        """Get SNOMED CT code for administration route."""
        route_map = {
            "oral": "26643006",
            "intravenous": "47625008",
            "intramuscular": "78421000",
            "subcutaneous": "34206005",
            "topical": "404820008",
            "inhalation": "447694001",
            "sublingual": "37839007",
            "transdermal": "404820008"
        }
        return route_map.get(route.lower(), "26643006")  # default to oral
    
    @staticmethod
    def _get_rxnorm_code(medication_name: str) -> str:
        """Get RxNorm code for medication (simplified - would need full mapping in production)."""
        # Simplified mapping - in production use RxNorm lookup API
        med_codes = {
            "ibuprofen": "5640",
            "aspirin": "5271",
            "paracetamol": "1649",
            "acetaminophen": "1649",
            "metformin": "6809",
            "lisinopril": "21600",
            "atorvastatin": "83367"
        }
        return med_codes.get(medication_name.lower(), "0")  # 0 = unknown
    
    @staticmethod
    def bundle_to_json(bundle: Dict[str, Any]) -> str:
        """Convert bundle to JSON string."""
        import json
        return json.dumps(bundle, indent=2, default=str)
