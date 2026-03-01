#!/usr/bin/env python3
"""
Test script to verify the Bedrock service fixes work correctly.
Tests:
1. File upload and OCR extraction
2. Normalize & Extract with improved error handling
3. Check interactions
4. TTS generation
"""

import requests
import json
import sys
from pathlib import Path

BASE_URL = "http://localhost:5000"

def test_api():
    print("\n" + "="*60)
    print("TESTING MEDIAVAULT API WITH IMPROVED BEDROCK SERVICE")
    print("="*60)
    
    # Test 1: Simple text normalization (no file needed)
    print("\n✅ TEST 1: Normalize text endpoint")
    print("-" * 60)
    
    normalize_payload = {
        "reviewed_text": "Prescribed Ibuprofen 200 mg twice daily for 7 days. Patient has allergy to Penicillin.",
        "patient_verified": True,
        "ocr_confidence": 0.85
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/ai/normalize-and-extract",
            json=normalize_payload,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        
        if result.get("ok"):
            print("✅ Normalization successful!")
            print(f"Cleaned text: {result.get('cleaned_text', '')[:100]}...")
            if result.get("flags"):
                print(f"Flags: {result['flags']}")
            if "entities" in result:
                print(f"Entities found: {json.dumps(result['entities'], indent=2)}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            if "raw" in result:
                print(f"Raw response: {result['raw'][:200]}")
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {str(e)}")
        return False
    
    # Test 2: Check drug interactions
    print("\n✅ TEST 2: Check drug interactions")
    print("-" * 60)
    
    interaction_payload = {
        "new_med": "Ibuprofen",
        "current_meds": ["Warfarin", "Aspirin"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/ai/check-interaction",
            json=interaction_payload,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        
        if result.get("ok"):
            print("✅ Interaction check successful!")
            for interaction in result.get("interactions", []):
                print(f"  - {interaction.get('drugs')}: {interaction.get('risk', 'unknown')} risk")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {str(e)}")
        return False
    
    # Test 3: TTS generation
    print("\n✅ TEST 3: Text-to-speech generation")
    print("-" * 60)
    
    tts_payload = {
        "text": "Patient is prescribed Ibuprofen 200 milligrams twice daily for 7 days. Report any side effects.",
        "language": "en"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/ai/tts",
            json=tts_payload,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            # Check if it's audio data or JSON error
            try:
                result = response.json()
                if result.get("ok"):
                    print("✅ TTS generation successful!")
                    print(f"Audio URL: {result.get('audio_url', 'N/A')}")
                else:
                    print(f"❌ Error: {result.get('error', 'Unknown error')}")
            except:
                # It's audio data
                print(f"✅ TTS generation successful! Received {len(response.content)} bytes of audio data")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(response.text[:200])
        
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {str(e)}")
        return False
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETED!")
    print("="*60)
    return True

if __name__ == "__main__":
    try:
        success = test_api()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {type(e).__name__}: {str(e)}")
        sys.exit(1)
