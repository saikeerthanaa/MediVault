#!/usr/bin/env python3
"""
Test OCR extraction with fuzzy matching, brand mapping, and preprocessing.
Tests medication extraction from noisy OCR with India pharmaceutical brands.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.bedrock_service import BedrockService, preprocess_ocr_text

def test_extraction():
    """Test medication extraction with improved pattern matching."""
    print("=" * 80)
    print("Testing Medication Extraction with OCR Preprocessing, Brand Mapping, & Fuzzy Matching")
    print("=" * 80)
    
    service = BedrockService(region="ap-south-1", model_id="amazon.nova-micro-v1:0")
    
    # Test cases with OCR noise and India brand names
    test_cases = [
        {
            "name": "OCR with line breaks in medication name",
            "text": "Metfor-\nmin 500mg twice daily for diabetes",
            "expected": ["Metformin"]
        },
        {
            "name": "India brand names",
            "text": "Patient prescribed Dolo 650mg for fever, Pan 40mg for acidity, Azee 500mg for infection",
            "expected": ["Paracetamol", "Pantoprazole", "Azithromycin"]
        },
        {
            "name": "Mixed exact and brand names",
            "text": "Take Ibuprofen 400mg or Glycomet 500mg tablets daily",
            "expected": ["Ibuprofen", "Metformin"]
        },
        {
            "name": "OCR noise with extra spaces",
            "text": "DOLO   650  mg   twice     daily  for   headache",
            "expected": ["Paracetamol"]
        },
        {
            "name": "Complex prescription",
            "text": """
            Patient Medications:
            1. Ecosprin 75mg once daily (for heart)
            2. Lisinopril 10 mg once daily (blood pressure)
            3. Azee 250 mg for 3 days (infection)
            """,
            "expected": ["Aspirin", "Lisinopril", "Azithromycin"]
        },
        {
            "name": "Standard prescriptions",
            "text": "Ibuprofen 400mg tablet orally twice daily for 5 days. Amoxicillin 500mg oral capsule three times daily for 7 days.",
            "expected": ["Ibuprofen", "Amoxicillin"]
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n{'─' * 80}")
        print(f"Test: {test['name']}")
        print(f"Text: {test['text'][:100]}...")
        
        # Preprocess text first (like extract_entities does)
        preprocessed = preprocess_ocr_text(test['text'])
        print(f"Preprocessed: {preprocessed[:100]}...")
        
        medications, debug_info = service._extract_medications_simple(preprocessed, debug_mode=True)
        
        extracted_names = [med['name'] for med in medications]
        print(f"\nExtracted medications: {extracted_names}")
        print(f"Expected: {test['expected']}")
        print(f"Debug info: {debug_info}")
        
        # Check if all expected medications were found
        all_found = all(exp in extracted_names for exp in test['expected'])
        
        if all_found:
            print("✅ PASS")
            passed += 1
        else:
            print("❌ FAIL")
            failed += 1
            
            # Print details
            for med in medications:
                print(f"  - {med['name']}")
                print(f"    Dosage: {med['dosage']}")
                print(f"    Frequency: {med['frequency']}")
                print(f"    Route: {med['route']}")
                print(f"    Duration: {med['duration']}")
                print(f"    Notes: {med['notes']}")
    
    print(f"\n{'=' * 80}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 80}")
    
    return failed == 0

if __name__ == "__main__":
    success = test_extraction()
    sys.exit(0 if success else 1)
