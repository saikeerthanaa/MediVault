#!/usr/bin/env python3
"""
Test medication extraction with real prescription data.
Tests the improved pattern matching and medication database.
"""

import requests
import json

BASE_URL = "http://localhost:5000"

# Sample prescription data
prescriptions = [
    {
        "name": "Simple Prescription",
        "text": "Ibuprofen 200mg twice daily for 7 days. Take with food."
    },
    {
        "name": "Complex Prescription",
        "text": """
        Patient prescribed the following:
        - Metformin 500mg, 2 tablets three times daily with meals
        - Lisinopril 10mg once daily in the morning
        - Atorvastatin 20mg once daily at bedtime
        - Aspirin 81mg once daily
        Duration: 30 days
        """
    },
    {
        "name": "Drug Interaction Risk",
        "text": """
        RX WARFARIN 5mg once daily
        RX IBUPROFEN 400mg twice daily for pain
        RX ASPIRIN 81mg once daily
        """
    },
    {
        "name": "Antibiotic Course",
        "text": """
        AMOXICILLIN 500mg, 1 capsule three times daily for 10 days
        CETIRIZINE 10mg once daily as needed for allergies
        Note: Patient has penicillin allergy (verify drug safety)
        """
    },
    {
        "name": "Respiratory Treatment",
        "text": """
        1. Fluticasone inhaler - 2 puffs twice daily
        2. Albuterol inhaler - 2 puffs as needed every 4-6 hours
        3. Salmeterol - 1 puff every 12 hours
        4. Montelukast 4mg once daily at bedtime
        """
    },
    {
        "name": "Diabetic Management",
        "text": """
        INSULIN 20 units subcutaneous injection twice daily
        METFORMIN 1000mg twice daily with meals
        SITAGLIPTIN 100mg once daily
        """
    }
]

def test_prescription_extraction(prescription):
    """Test extraction for a single prescription"""
    print(f"\n{'='*70}")
    print(f"TEST: {prescription['name']}")
    print(f"{'='*70}")
    
    payload = {
        "reviewed_text": prescription["text"],
        "patient_verified": True,
        "ocr_confidence": 0.85
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/ai/normalize-and-extract",
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            return False
        
        result = response.json()
        
        if not result.get("ok"):
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            return False
        
        # Extract medications
        entities = result.get("entities", {})
        medications = entities.get("medications", [])
        
        print(f"\nInput Text:")
        print(f"  {prescription['text'][:100]}...")
        
        print(f"\n📋 Extracted Medications ({len(medications)}):")
        if medications:
            for med in medications:
                print(f"  • {med['name']}", end="")
                if med.get('dosage'):
                    print(f" - {med['dosage']}", end="")
                if med.get('frequency'):
                    print(f" - {med['frequency']}", end="")
                if med.get('duration'):
                    print(f" - {med['duration']}", end="")
                if med.get('route'):
                    print(f" (Route: {med['route']})", end="")
                print()
        else:
            print(f"  ⚠️ NO MEDICATIONS FOUND")
        
        # Show other entities if present
        conditions = entities.get("conditions", [])
        allergies = entities.get("allergies", [])
        
        if conditions:
            print(f"\n🏥 Conditions: {', '.join(conditions)}")
        if allergies:
            print(f"⚠️ Allergies: {', '.join(allergies)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {str(e)}")
        return False

def main():
    print("\n" + "="*70)
    print("MEDIAVAULT - MEDICATION EXTRACTION TEST")
    print("Testing improved pattern matching with real prescription data")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for prescription in prescriptions:
        if test_prescription_extraction(prescription):
            passed += 1
        else:
            failed += 1
    
    print(f"\n\n{'='*70}")
    print(f"TEST SUMMARY")
    print(f"{'='*70}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {passed + failed}")
    print(f"{'='*70}\n")
    
    return failed == 0

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
