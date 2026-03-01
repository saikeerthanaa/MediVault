#!/usr/bin/env python3
"""Quick test of new two-stage bedrock service."""

from backend.services.bedrock_service import BedrockService

# Test 1: Normalization
print("=" * 60)
print("TEST 1: OCR Text Normalization")
print("=" * 60)

service = BedrockService()
ocr_text = "Paracetam0l 100mg BD, Ibupr0fen 200mg TDS for 7 days"
result = service.normalize_text(ocr_text)

print(f"Original: {ocr_text}")
print(f"Cleaned:  {result['cleaned_text']}")
print(f"Corrections found: {len(result['corrections'])}")
for corr in result['corrections']:
    print(f"  - {corr['original']} → {corr['corrected']} ({corr['type']})")

# Test 2: Fuzzy extraction (offline)
print("\n" + "=" * 60)
print("TEST 2: Fuzzy Medication Extraction (Offline)")
print("=" * 60)

from backend.services.bedrock_service import extract_medications_fuzzy

prescription = """
Dr's Name: Dr. Smith
Date: 2024-01-15

Rx: Paracetem 500mg BD
    Amoxycllin-clavulante 625mg TDS x 7 days
    Cetirizine 10mg OD HS
    Ibuprofen 200mg as needed
"""

fuzzy_meds = extract_medications_fuzzy(prescription)
print(f"Medications found (fuzzy): {len(fuzzy_meds)}")
for med in fuzzy_meds:
    print(f"  - {med['name']}: {med['dosage']} {med['frequency']}")

# Test 3: Full extraction with both stages
print("\n" + "=" * 60)
print("TEST 3: Full Two-Stage Extraction")
print("=" * 60)

result = service.normalize_and_extract(ocr_text, debug=True)

print(f"Status: {'✅ OK' if result['ok'] else '❌ FAILED'}")
print(f"Medications extracted: {len(result['entities']['medications'])}")
for med in result['entities']['medications']:
    print(f"  - {med['name']}: {med['dosage']} {med['frequency']}")

if "extraction_debug" in result:
    debug = result["extraction_debug"]
    print(f"\nDebug info:")
    print(f"  Bedrock meds: {debug['bedrock_med_count']}")
    print(f"  Fuzzy meds:   {debug['fuzzy_med_count']}")
    print(f"  Merged total: {debug['merged_count']}")
    print(f"  Bedrock OK:   {debug['bedrock_ok']}")

print("\n✅ All tests completed!")
