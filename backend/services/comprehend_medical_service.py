"""
Amazon Comprehend Medical Service (Optional)
Integrates with AWS Comprehend Medical for entity extraction.
Falls back gracefully if service is unavailable or disabled.
"""
import boto3
from typing import Dict, List, Optional, Any
from config import Config


class ComprehendMedicalService:
    """Optional service for enhanced medical entity extraction using AWS Comprehend Medical."""
    
    def __init__(self, region: str = "ap-south-1"):
        self.region = region
        self.enabled = Config.ENABLE_COMPREHEND_MEDICAL
        self.client = None
        self.available = False
        
        if self.enabled:
            try:
                self.client = boto3.client("comprehendmedical", region_name=region)
                self.available = True
                print(f"✅ Comprehend Medical initialized in region: {region}")
            except Exception as e:
                print(f"⚠️ Comprehend Medical unavailable: {type(e).__name__} - {str(e)}")
                self.available = False
    
    def detect_medical_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract medical entities using Comprehend Medical.
        
        Args:
            text: Medical text to analyze
        
        Returns:
            Dictionary with entities by type
        """
        if not self.enabled or not self.available:
            return {"ok": False, "reason": "Comprehend Medical not enabled or unavailable"}
        
        try:
            response = self.client.detect_entities(Text=text)
            
            entities = {
                "medications": [],
                "conditions": [],
                "allergies": [],
                "dosages": [],
                "procedures": []
            }
            
            for entity in response.get("Entities", []):
                entity_type = entity.get("Type", "").lower()
                text_val = entity.get("Text", "")
                confidence = entity.get("Score", 0.0)
                
                # Map Comprehend entity types to MediVault types
                if entity_type == "medication":
                    entities["medications"].append({
                        "name": text_val,
                        "confidence": confidence,
                        "source": "comprehend_medical"
                    })
                elif entity_type == "medical_condition":
                    entities["conditions"].append({
                        "name": text_val,
                        "confidence": confidence,
                        "source": "comprehend_medical"
                    })
                elif entity_type == "dosage":
                    entities["dosages"].append({
                        "dosage": text_val,
                        "confidence": confidence,
                        "source": "comprehend_medical"
                    })
                elif entity_type == "procedure":
                    entities["procedures"].append({
                        "procedure": text_val,
                        "confidence": confidence,
                        "source": "comprehend_medical"
                    })
            
            return {"ok": True, "entities": entities}
        
        except Exception as e:
            print(f"❌ Comprehend Medical call failed: {type(e).__name__}: {str(e)}")
            return {"ok": False, "error": str(e)}
    
    def detect_phi(self, text: str) -> Dict[str, Any]:
        """
        Detect Protected Health Information (PHI) in text.
        
        Args:
            text: Text to scan for PHI
        
        Returns:
            Dictionary with detected PHI
        """
        if not self.enabled or not self.available:
            return {"ok": False, "reason": "Comprehend Medical not enabled"}
        
        try:
            response = self.client.detect_phi(Text=text)
            
            phi_entities = []
            for entity in response.get("Entities", []):
                phi_entities.append({
                    "type": entity.get("Type", ""),
                    "text": entity.get("Text", ""),
                    "confidence": entity.get("Score", 0.0),
                    "begin_offset": entity.get("BeginOffset", 0),
                    "end_offset": entity.get("EndOffset", 0)
                })
            
            return {"ok": True, "phi": phi_entities}
        
        except Exception as e:
            print(f"❌ PHI Detection failed: {type(e).__name__}: {str(e)}")
            return {"ok": False, "error": str(e)}


def merge_entities(base_entities: Dict[str, List], comprehend_entities: Dict[str, List]) -> Dict[str, List]:
    """
    Merge entities from base extraction with Comprehend Medical results.
    Deduplicates by normalized name and handles confidence scoring.
    
    Args:
        base_entities: Entities from pattern matching / Bedrock (with 'name' field)
        comprehend_entities: Entities from Comprehend Medical (with 'name' field)
    
    Returns:
        Merged entities dictionary
    """
    merged = {
        "medications": [],
        "conditions": [],
        "allergies": []
    }
    
    # Process medications
    med_map = {}
    
    # Add base medications
    for med in base_entities.get("medications", []):
        name_lower = med.get("name", "").lower().strip()
        if name_lower:
            if name_lower not in med_map:
                med_map[name_lower] = med.copy()
                med_map[name_lower]["sources"] = ["pattern_extraction"]
    
    # Merge Comprehend medications
    for med in comprehend_entities.get("medications", []):
        name_lower = med.get("name", "").lower().strip()
        if name_lower:
            if name_lower in med_map:
                # Merge with existing
                existing = med_map[name_lower]
                # Use higher confidence score if available
                if "confidence" in med and med["confidence"] > existing.get("confidence", 0):
                    existing["confidence"] = med["confidence"]
                existing["sources"].append("comprehend_medical")
            else:
                # New medication from Comprehend
                med_map[name_lower] = med.copy()
                med_map[name_lower]["sources"] = ["comprehend_medical"]
    
    merged["medications"] = list(med_map.values())
    
    # Similar logic for conditions
    cond_map = {}
    for cond in base_entities.get("conditions", []):
        name_lower = cond.get("name", "").lower().strip()
        if name_lower:
            if name_lower not in cond_map:
                cond_map[name_lower] = cond.copy()
                cond_map[name_lower]["sources"] = ["pattern_extraction"]
    
    for cond in comprehend_entities.get("conditions", []):
        name_lower = cond.get("name", "").lower().strip()
        if name_lower:
            if name_lower in cond_map:
                existing = cond_map[name_lower]
                if "confidence" in cond and cond["confidence"] > existing.get("confidence", 0):
                    existing["confidence"] = cond["confidence"]
                existing["sources"].append("comprehend_medical")
            else:
                cond_map[name_lower] = cond.copy()
                cond_map[name_lower]["sources"] = ["comprehend_medical"]
    
    merged["conditions"] = list(cond_map.values())
    
    # Allergies (typically come from base extraction, merge if present)
    merged["allergies"] = base_entities.get("allergies", [])
    
    return merged
