#!/usr/bin/env python3
"""
Integration test for the /ai/normalize-and-extract endpoint.
Tests the full pipeline with OCR preprocessing, brand mapping, and debug output.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app import create_app

def test_extraction_api():
    """Test the normalize-and-extract API endpoint."""
    print("=" * 80)
    print("Integration Test: /ai/normalize-and-extract Endpoint")
    print("=" * 80)
    
    app = create_app()
    client = app.test_client()
    
    test_cases = [
        {
            "name": "OCR with line breaks and India brands",
            "payload": {
                "reviewed_text": "Metfor-\nmin 500mg twice daily. DOLO 650mg for fever. Pan 40mg once daily.",
                "patient_verified": True,
                "ocr_confidence": 85.0,
                "debug": True
            },
            "expected_medications": ["Metformin", "Paracetamol", "Pantoprazole"]
        },
        {
            "name": "Complex prescription with multiple India brands",
            "payload": {
                "reviewed_text": "Patient prescribed: Azee 500mg for 3 days, Ecosprin 75mg daily, Glycomet 500mg twice daily",
                "patient_verified": True,
                "ocr_confidence": 90.0,
                "debug": True
            },
            "expected_medications": ["Azithromycin", "Aspirin", "Metformin"]
        },
        {
            "name": "Standard prescription without debug",
            "payload": {
                "reviewed_text": "Ibuprofen 400mg tablet orally twice daily for 5 days. Amoxicillin 500mg three times daily.",
                "patient_verified": True,
                "ocr_confidence": 95.0,
                "debug": False
            },
            "expected_medications": ["Ibuprofen", "Amoxicillin"]
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n{'─' * 80}")
        print(f"Test: {test['name']}")
        print(f"Request payload: {json.dumps(test['payload'], indent=2)}")
        
        response = client.post(
            '/ai/normalize-and-extract',
            json=test['payload'],
            content_type='application/json'
        )
        
        print(f"\nResponse status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ FAIL - Expected 200, got {response.status_code}")
            print(f"Response body: {response.get_json()}")
            failed += 1
            continue
        
        result = response.get_json()
        print(f"Response body (formatted):")
        print(json.dumps(result, indent=2))
        
        # Verify response structure
        if not result.get('ok'):
            print(f"❌ FAIL - Response ok=false")
            failed += 1
            continue
        
        # Check entities
        entities = result.get('entities', {})
        medications = entities.get('medications', [])
        extracted_names = [m.get('name', '') for m in medications]
        
        print(f"\nExtracted medications: {extracted_names}")
        print(f"Expected: {test['expected_medications']}")
        
        # Check if all expected medications were found
        all_found = all(exp in extracted_names for exp in test['expected_medications'])
        
        # Check debug output if requested
        if test['payload'].get('debug'):
            if 'extraction_debug' not in result:
                print(f"❌ FAIL - Debug mode requested but extraction_debug not in response")
                failed += 1
                continue
            
            debug_info = result.get('extraction_debug', {})
            print(f"\nDebug info:")
            print(f"  Matched terms: {debug_info.get('matched_terms', [])}")
            print(f"  Notes: {debug_info.get('notes', '')}")
            print(f"  Text preview: {debug_info.get('normalized_text_preview', '')[:100]}...")
        
        if all_found:
            print("\n✅ PASS")
            passed += 1
        else:
            print("\n❌ FAIL - Not all expected medications found")
            failed += 1
    
    print(f"\n{'=' * 80}")
    print(f"API Integration Test Results: {passed} passed, {failed} failed")
    print(f"{'=' * 80}")
    
    return failed == 0

if __name__ == "__main__":
    success = test_extraction_api()
    sys.exit(0 if success else 1)
