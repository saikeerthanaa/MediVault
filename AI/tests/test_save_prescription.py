"""
Test for POST /ai/save-prescription endpoint

This demonstrates the complete prescription saving flow:
1. Save to MySQL database
2. Auto drug interaction checking
3. FHIR bundle generation
"""

import requests
import json
from datetime import datetime

# Test endpoint
BASE_URL = "http://localhost:5000"

def test_save_prescription():
    """Test the save-prescription endpoint"""
    
    # Sample prescription data - HITL approved by patient
    payload = {
        "patient_id": 1,
        "doctor_id": 2,
        "s3_image_url": "https://bucket.s3.amazonaws.com/prescriptions/rx-001.jpg",
        "ocr_confidence": 0.87,
        "reviewed_text": "Ibuprofen 200mg twice daily for 7 days. Omeprazole 20mg once daily.",
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
    
    print("=" * 60)
    print("Testing POST /ai/save-prescription")
    print("=" * 60)
    print("\nRequest Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            f"{BASE_URL}/ai/save-prescription",
            json=payload,
            timeout=10
        )
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ SUCCESS")
            print(json.dumps(data, indent=2))
            
            if data.get("ok"):
                print(f"\n📋 Prescription ID: {data.get('prescription_id')}")
                print(f"💊 Medicines Saved: {data.get('medicines_saved')}")
                print(f"⚠️ Interactions Found: {len(data.get('interactions', []))}")
                
                if data.get("interactions"):
                    print("\nDrug Interactions:")
                    for interaction in data.get("interactions", []):
                        print(f"  • {interaction['pair'][0]} + {interaction['pair'][1]}")
                        print(f"    Severity: {interaction['severity']}")
                        print(f"    Summary: {interaction['summary']}")
                
                print(f"\n📄 FHIR Bundle Saved: {data.get('fhir_bundle_saved')}")
                
                if data.get("warnings"):
                    print(f"\n⚠️ Warnings ({len(data.get('warnings'))}):")
                    for warning in data.get("warnings", []):
                        print(f"  • {warning}")
        else:
            print(f"\n❌ ERROR: {response.status_code}")
            print(response.text)
    
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection error - ensure Flask server is running on port 5000")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


def test_drug_interactions():
    """Test with medications that have known interactions"""
    
    # High interaction risk: Warfarin + Ibuprofen + Aspirin
    payload = {
        "patient_id": 2,
        "doctor_id": 1,
        "s3_image_url": "https://bucket.s3.amazonaws.com/prescriptions/rx-002.jpg",
        "ocr_confidence": 0.92,
        "reviewed_text": "Warfarin 5mg daily. Ibuprofen 400mg twice daily. Aspirin 81mg daily.",
        "entities": {
            "medications": [
                {
                    "name": "Warfarin",
                    "dosage": "5 mg",
                    "frequency": "Once daily",
                    "duration": "Ongoing"
                },
                {
                    "name": "Ibuprofen",
                    "dosage": "400 mg",
                    "frequency": "Twice daily",
                    "duration": "For 7 days"
                },
                {
                    "name": "Aspirin",
                    "dosage": "81 mg",
                    "frequency": "Once daily",
                    "duration": "Ongoing"
                }
            ],
            "conditions": [
                "Atrial fibrillation",
                "Fever",
                "Pain"
            ],
            "allergies": []
        }
    }
    
    print("\n" + "=" * 60)
    print("Testing Prescription with High Interaction Risk")
    print("=" * 60)
    print("\nRequest Payload (High Risk: Warfarin + NSAIDs):")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            f"{BASE_URL}/ai/save-prescription",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Prescription saved")
            
            interactions = data.get("interactions", [])
            if interactions:
                print(f"\n🚨 HIGH RISK DETECTED: {len(interactions)} significant interaction(s)")
                for interaction in interactions:
                    print(f"\n  {interaction['pair'][0]} + {interaction['pair'][1]}")
                    print(f"  Severity: {interaction['severity'].upper()}")
                    print(f"  Action: {interaction.get('action', 'Consult pharmacist')}")
            else:
                print("\n✅ No high-risk interactions detected")
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    print("\n🏥 MediVault Save-Prescription Endpoint Tests\n")
    
    # Test 1: Basic prescription saving
    test_save_prescription()
    
    # Test 2: High interaction risk
    test_drug_interactions()
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
