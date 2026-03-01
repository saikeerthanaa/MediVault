"""
Knowledge Base RAG Service
Provides drug interaction checking with citations and severity assessment.
"""
import boto3
from typing import Dict, List, Any


class KBRagService:
    def __init__(self, region: str, kb_id: str):
        self.kb_id = kb_id.strip() if kb_id else ""
        self.region = region
        try:
            self.client = boto3.client("bedrock-agent-runtime", region_name=region)
            self.available = bool(self.kb_id)
        except Exception as e:
            print(f"⚠️ KB RAG client initialization failed: {e}")
            self.client = None
            self.available = False

    def check_interaction(self, new_med: str, current_meds: List[str]) -> dict:
        """
        Check for drug interactions with citations.
        Returns detailed interaction information with evidence sources.
        """
        if not self.kb_id or not self.available:
            # MVP-safe behavior: "unknown" rather than hallucinate
            return {
                "ok": True,
                "new_med": new_med,
                "current_meds": current_meds,
                "interactions": [{
                    "severity": "unknown",
                    "summary": "Knowledge Base not configured",
                    "mechanism": "Cannot verify - KB not available",
                    "action": "Consult healthcare provider",
                    "citations": []
                }]
            }

        query = f"drug interaction {new_med} {' '.join(current_meds)}"

        try:
            # Retrieve from knowledge base
            resp = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
            )

            results = resp.get("retrievalResults", [])
            interactions = []
            
            if results:
                # Process each result into an interaction record
                for result in results:
                    location = result.get("location", {})
                    text_snippet = result.get("content", {}).get("text", "")[:500]
                    score = result.get("score", 0)
                    
                    interactions.append({
                        "severity": self._infer_severity(text_snippet),
                        "summary": self._extract_summary(text_snippet),
                        "mechanism": text_snippet,
                        "action": self._extract_action(text_snippet),
                        "citations": [{
                            "title": location.get("s3Location", {}).get("uri", location.get("webLocation", {}).get("uri", "Unknown")),
                            "snippet": text_snippet,
                            "source_uri": location.get("s3Location", {}).get("uri", location.get("webLocation", {}).get("uri", "")),
                            "relevance_score": float(score)
                        }]
                    })
            else:
                # No evidence found - still return "unknown" not "safe"
                interactions.append({
                    "severity": "unknown",
                    "summary": "No evidence found in Knowledge Base",
                    "mechanism": "No supporting documents retrieved",
                    "action": "Consult healthcare provider for verification",
                    "citations": []
                })

            return {
                "ok": True,
                "new_med": new_med,
                "current_meds": current_meds,
                "interactions": interactions
            }

        except Exception as e:
            print(f"❌ KB RAG call failed: {type(e).__name__}: {str(e)}")
            return {
                "ok": True,
                "new_med": new_med,
                "current_meds": current_meds,
                "interactions": [{
                    "severity": "unknown",
                    "summary": f"Error accessing Knowledge Base: {str(e)}",
                    "mechanism": "KB service unavailable",
                    "action": "Consult healthcare provider",
                    "citations": []
                }]
            }
    
    @staticmethod
    def _infer_severity(text: str) -> str:
        """Infer interaction severity from text content."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['contraindicated', 'fatal', 'severe', 'critical', 'life-threaten']):
            return "high"
        elif any(word in text_lower for word in ['caution', 'monitor', 'moderate', 'significant']):
            return "medium"
        elif any(word in text_lower for word in ['minor', 'mild', 'low']):
            return "low"
        else:
            return "unknown"
    
    @staticmethod
    def _extract_summary(text: str) -> str:
        """Extract a brief summary from text."""
        # Take first sentence or first 100 chars
        sentences = text.split('.')
        summary = sentences[0].strip() if sentences else text[:100]
        return summary[:200] + ("..." if len(summary) > 200 else "")
    
    @staticmethod
    def _extract_action(text: str) -> str:
        """Extract recommended action from text."""
        text_lower = text.lower()
        
        if 'avoid' in text_lower or 'contraindicated' in text_lower:
            return "Do not use together"
        elif 'monitor' in text_lower:
            return "Use with caution; monitor patient closely"
        elif 'dose' in text_lower or 'adjust' in text_lower:
            return "Dosage adjustment may be needed"
        else:
            return "Consult healthcare provider"
