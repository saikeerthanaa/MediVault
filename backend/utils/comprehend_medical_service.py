"""
AWS Comprehend Medical integration service.
Optional feature to enhance medical entity detection with AI-powered extraction.
Uses AWS Comprehend Medical API when enabled via ENABLE_COMPREHEND_MEDICAL config flag.
"""

import boto3
import json
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher


class ComprehendMedicalService:
    """
    Optional AWS Comprehend Medical entity extraction service.
    Detects medications, conditions, allergies, dosages, and Protected Health Information (PHI).
    Designed to work alongside pattern-based extraction with entity deduplication.
    """
    
    def __init__(self, region: str = "ap-south-1"):
        """
        Initialize Comprehend Medical service.
        Client creation can fail gracefully if service not available.
        """
        self.region = region
        self.client = None
        
        try:
            self.client = boto3.client("comprehendmedical", region_name=region)
            print(f"✅ Comprehend Medical client initialized for region: {region}")
        except Exception as e:
            print(f"⚠️  Comprehend Medical unavailable: {str(e)}")
            self.client = None
    
    def detect_medical_entities(self, text: str) -> Dict[str, Any]:
        """
        Detect medical entities using AWS Comprehend Medical.
        Returns structured extraction with medications, conditions, allergies, dosages, procedures.
        Safe graceful fallback if service unavailable.
        """
        if not self.client:
            return {
                "ok": False,
                "error": "Comprehend Medical client not initialized",
                "entities": {}
            }
        
        if not text or len(text.strip()) == 0:
            return {
                "ok": True,
                "entities": {
                    "medications": [],
                    "conditions": [],
                    "allergies": [],
                    "dosages": [],
                    "procedures": []
                }
            }
        
        try:
            # Call Comprehend Medical API
            response = self.client.detect_entities_v2(Text=text)
            
            entities = self._parse_entities_response(response)
            
            return {
                "ok": True,
                "entities": entities
            }
        
        except Exception as e:
            print(f"⚠️  Comprehend Medical detection failed: {str(e)}")
            return {
                "ok": False,
                "error": f"Comprehend Medical API error: {str(e)}",
                "entities": {}
            }
    
    def detect_phi(self, text: str) -> Dict[str, Any]:
        """
        Detect Protected Health Information (PHI) in text.
        Returns detected PII entities with offsets.
        """
        if not self.client:
            return {
                "ok": False,
                "error": "Comprehend Medical client not initialized",
                "phi_entities": []
            }
        
        try:
            response = self.client.detect_phi(Text=text)
            
            phi_entities = []
            for entity in response.get("Entities", []):
                phi_entities.append({
                    "type": entity.get("Type", "UNKNOWN"),
                    "text": text[entity.get("BeginOffset", 0):entity.get("EndOffset", 0)],
                    "confidence": entity.get("Score", 0),
                    "begin_offset": entity.get("BeginOffset", 0),
                    "end_offset": entity.get("EndOffset", 0)
                })
            
            return {
                "ok": True,
                "phi_entities": phi_entities
            }
        
        except Exception as e:
            print(f"⚠️  PHI detection failed: {str(e)}")
            return {
                "ok": False,
                "error": f"PHI detection error: {str(e)}",
                "phi_entities": []
            }
    
    def _parse_entities_response(self, response: Dict) -> Dict[str, list]:
        """
        Parse Comprehend Medical API response into structured entity lists.
        Categories: MEDICATION, MEDICAL_CONDITION, ALLERGIES, DOSAGE, PROCEDURE.
        """
        medications = []
        conditions = []
        allergies = []
        dosages = []
        procedures = []
        
        for entity in response.get("Entities", []):
            entity_type = entity.get("Type", "")
            attributes = entity.get("Attributes", [])
            text = entity.get("Text", "")
            confidence = entity.get("Score", 0)
            
            if entity_type == "MEDICATION":
                # Extract medication with optional strength attribute
                strength = next(
                    (a.get("Text", "") for a in attributes if a.get("Type") == "STRENGTH"),
                    ""
                )
                route = next(
                    (a.get("Text", "") for a in attributes if a.get("Type") == "ROUTE_OR_MODE"),
                    ""
                )
                form = next(
                    (a.get("Text", "") for a in attributes if a.get("Type") == "FORM"),
                    ""
                )
                
                medications.append({
                    "name": text,
                    "dosage": strength or "",
                    "route": route or "",
                    "form": form or "",
                    "confidence": confidence,
                    "source": "comprehend_medical"
                })
            
            elif entity_type == "MEDICAL_CONDITION":
                conditions.append({
                    "name": text,
                    "condition": text,
                    "confidence": confidence,
                    "source": "comprehend_medical"
                })
            
            elif entity_type == "ALLERGIES":
                allergies.append({
                    "name": text,
                    "allergen": text,
                    "confidence": confidence,
                    "source": "comprehend_medical"
                })
            
            elif entity_type == "DOSAGE":
                dosages.append({
                    "frequency": text,
                    "confidence": confidence,
                    "source": "comprehend_medical"
                })
            
            elif entity_type == "PROCEDURE":
                procedures.append({
                    "name": text,
                    "procedure": text,
                    "confidence": confidence,
                    "source": "comprehend_medical"
                })
        
        return {
            "medications": medications,
            "conditions": conditions,
            "allergies": allergies,
            "dosages": dosages,
            "procedures": procedures
        }


def merge_entities(base_entities: Dict[str, list], comprehend_entities: Dict[str, list]) -> Dict[str, list]:
    """
    Merge Comprehend Medical detected entities with base extracted entities.
    Deduplicates by normalized name, uses higher confidence score, tracks sources.
    
    Args:
        base_entities: Entities from pattern matching/Bedrock extraction
        comprehend_entities: Entities from Comprehend Medical API
    
    Returns:
        Merged entity dictionary with deduplicated entities
    """
    
    def normalize_name(name: str) -> str:
        """Normalize entity name for comparison (lowercase, stripped)."""
        return name.lower().strip() if isinstance(name, str) else ""
    
    def similarity_score(s1: str, s2: str) -> float:
        """Calculate similarity between two strings."""
        return SequenceMatcher(None, normalize_name(s1), normalize_name(s2)).ratio()
    
    def merge_entity_lists(base_list: list, comp_list: list, key_field: str) -> list:
        """
        Merge two entity lists, deduplicating by normalized name.
        Uses higher confidence score and combines sources.
        """
        merged = []
        matched_indices = set()
        
        for base_entity in base_list:
            if not isinstance(base_entity, dict):
                merged.append(base_entity)
                continue
            
            base_name = base_entity.get(key_field, "")
            best_match = None
            best_score = 0.70  # Threshold for fuzzy matching
            best_idx = -1
            
            # Find best match in comprehend list
            for idx, comp_entity in enumerate(comp_list):
                if not isinstance(comp_entity, dict) or idx in matched_indices:
                    continue
                
                comp_name = comp_entity.get(key_field, "")
                score = similarity_score(base_name, comp_name)
                
                if score > best_score:
                    best_score = score
                    best_match = comp_entity
                    best_idx = idx
            
            # Merge if match found
            if best_match:
                matched_indices.add(best_idx)
                merged_entity = base_entity.copy()
                
                # Use higher confidence
                base_conf = float(base_entity.get("confidence", 0))
                comp_conf = float(best_match.get("confidence", 0))
                merged_entity["confidence"] = max(base_conf, comp_conf)
                
                # Combine sources
                sources = [base_entity.get("source", "pattern_match")]
                if best_match.get("source") not in sources:
                    sources.append(best_match.get("source", "comprehend_medical"))
                merged_entity["sources"] = sources
                
                # Add additional fields from comprehend if missing
                for field in best_match.keys():
                    if field not in merged_entity and field not in ["source", "confidence"]:
                        merged_entity[field] = best_match[field]
                
                merged.append(merged_entity)
            else:
                # No match, add base entity as-is
                if "sources" not in base_entity:
                    base_entity["sources"] = [base_entity.get("source", "pattern_match")]
                merged.append(base_entity)
        
        # Add unmatched comprehend entities
        for idx, comp_entity in enumerate(comp_list):
            if idx not in matched_indices and isinstance(comp_entity, dict):
                comp_entity["sources"] = [comp_entity.get("source", "comprehend_medical")]
                merged.append(comp_entity)
        
        return merged
    
    # Merge each entity type
    return {
        "medications": merge_entity_lists(
            base_entities.get("medications", []),
            comprehend_entities.get("medications", []),
            "name"
        ),
        "conditions": merge_entity_lists(
            base_entities.get("conditions", []),
            comprehend_entities.get("conditions", []),
            "name"
        ),
        "allergies": merge_entity_lists(
            base_entities.get("allergies", []),
            comprehend_entities.get("allergies", []),
            "name"
        )
    }
