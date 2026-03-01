"""
Dosage Schedule Parser
Parses medication dosage instructions and converts them to structured schedules.
Handles Indian shorthand (OD, BD, TDS, QID, HS, SOS) and standardizes timing.
"""
import re
from typing import Dict, List, Optional, Any


class DosageSchedule:
    """Represents a structured medication schedule."""
    
    def __init__(self):
        self.frequency_per_day: int = 1
        self.timing = {
            "morning": False,
            "afternoon": False,
            "evening": False,
            "night": False
        }
        self.as_needed: bool = False
        self.duration_days: Optional[int] = None
        self.instructions: str = ""
        self.uncertainty: bool = False  # True if parsing failed or ambiguous
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "frequency_per_day": self.frequency_per_day,
            "timing": self.timing,
            "as_needed": self.as_needed,
            "duration_days": self.duration_days,
            "instructions": self.instructions,
            "uncertainty": self.uncertainty
        }


class DosageParser:
    """Parse medication dosage instructions into structured schedules."""
    
    # Indian medical shorthand
    INDIAN_SHORTHAND = {
        r'\bod\b|\bo\.d\b|\b1-0-0\b': ("Once daily (morning)", 1, {"morning": True}),
        r'\bbd\b|\bb\.d\b|\b1-1-0\b': ("Twice daily (morning + evening)", 2, {"morning": True, "evening": True}),
        r'\btds\b|\bt\.d\.s\b|\b1-1-1\b': ("Three times daily (morning + afternoon + evening)", 3, {"morning": True, "afternoon": True, "evening": True}),
        r'\bqid\b|\bq\.i\.d\b': ("Four times daily", 4, {"morning": True, "afternoon": True, "evening": True, "night": True}),
        r'\bhs\b|\bat\s+bedtime\b|\bat\s+night\b': ("At bedtime", 1, {"night": True}),
        r'\bsos\b|\bas\s+needed\b|\bprn\b': ("As needed", 0, {}),  # variable frequency
        r'\bac\b': ("Before meals", 3, {"morning": True, "afternoon": True, "evening": True}),
        r'\bpc\b': ("After meals", 3, {"morning": True, "afternoon": True, "evening": True}),
        r'\b6h\b|\bevery\s+6\s+h': ("Every 6 hours", 4, {"morning": True, "afternoon": True, "evening": True, "night": True}),
        r'\b8h\b|\bevery\s+8\s+h': ("Every 8 hours", 3, {"morning": True, "afternoon": True, "evening": True}),
        r'\b12h\b|\bevery\s+12\s+h': ("Twice daily (every 12 hours)", 2, {"morning": True, "evening": True}),
        r'\b24h\b|\bevery\s+24\s+h': ("Once daily", 1, {"morning": True}),
    }
    
    # Duration patterns
    DURATION_PATTERN = r'for\s+(\d+)\s+(?:days?|d|weeks?|w|months?|m|doses?)'
    
    # Frequency patterns (alternative parsing)
    FREQ_PATTERNS = {
        r'once\s+daily': (1, {"morning": True}),
        r'twice\s+daily': (2, {"morning": True, "evening": True}),
        r'three?\s+times?\s+daily': (3, {"morning": True, "afternoon": True, "evening": True}),
        r'four\s+times?\s+daily': (4, {"morning": True, "afternoon": True, "evening": True, "night": True}),
        r'every\s+(\d+)\s+hours?': None,  # Handled separately
    }
    
    @classmethod
    def parse(cls, dosage_instruction: str) -> DosageSchedule:
        """
        Parse a dosage instruction string into a structured schedule.
        
        Args:
            dosage_instruction: e.g., "1-0-1", "BD", "take with food"
        
        Returns:
            DosageSchedule object with parsed components
        """
        schedule = DosageSchedule()
        
        if not dosage_instruction or not isinstance(dosage_instruction, str):
            schedule.uncertainty = True
            return schedule
        
        instruction_lower = dosage_instruction.lower().strip()
        schedule.instructions = dosage_instruction
        
        # Check for "as needed" first
        if any(pattern in instruction_lower for pattern in ['as needed', 'when needed', 'sos', 'prn', 'as required']):
            schedule.as_needed = True
            schedule.frequency_per_day = 0
            return schedule
        
        # Try to match Indian shorthand
        matched = False
        for pattern, (desc, freq, timing) in cls.INDIAN_SHORTHAND.items():
            if re.search(pattern, instruction_lower):
                schedule.frequency_per_day = freq if freq > 0 else 1
                schedule.timing = timing.copy()
                matched = True
                schedule.instructions = desc
                break
        
        # If no shorthand matched, try frequency patterns
        if not matched:
            for pattern, freq_timing in cls.FREQ_PATTERNS.items():
                if freq_timing is None:  # Skip patterns with no handler
                    continue
                freq, timing = freq_timing
                if re.search(pattern, instruction_lower):
                    schedule.frequency_per_day = freq
                    schedule.timing = timing.copy()
                    matched = True
                    break
        
        if not matched:
            # Mark as uncertain - couldn't parse
            schedule.uncertainty = True
            schedule.frequency_per_day = 1  # Default fallback
        
        # Extract duration
        duration_match = re.search(cls.DURATION_PATTERN, instruction_lower)
        if duration_match:
            duration_num = int(duration_match.group(1))
            # Normalize to days
            if 'week' in duration_match.group(0):
                schedule.duration_days = duration_num * 7
            elif 'month' in duration_match.group(0):
                schedule.duration_days = duration_num * 30
            else:
                schedule.duration_days = duration_num
        
        return schedule
    
    @classmethod
    def normalize_timing_display(cls, schedule: DosageSchedule) -> str:
        """
        Generate a human-readable timing description from a schedule.
        
        Args:
            schedule: DosageSchedule object
        
        Returns:
            Human-readable string, e.g., "Twice daily (morning and evening)"
        """
        if schedule.as_needed:
            return "As needed"
        
        if schedule.uncertainty:
            return f"{schedule.instructions} (uncertain parsing)"
        
        timing_parts = []
        if schedule.timing.get("morning"):
            timing_parts.append("morning")
        if schedule.timing.get("afternoon"):
            timing_parts.append("afternoon")
        if schedule.timing.get("evening"):
            timing_parts.append("evening")
        if schedule.timing.get("night"):
            timing_parts.append("night")
        
        if not timing_parts:
            return schedule.instructions or "Once daily"
        
        freq_words = {
            0: "Once",
            1: "Once",
            2: "Twice",
            3: "Three times",
            4: "Four times",
            5: "Five times",
            6: "Six times"
        }
        
        freq_word = freq_words.get(schedule.frequency_per_day, f"{schedule.frequency_per_day} times")
        timing_str = " and ".join(timing_parts)
        
        return f"{freq_word} daily ({timing_str})"
    
    @classmethod
    def merge_with_context(cls, dosage_str: str, context_text: str) -> DosageSchedule:
        """
        Parse dosage and enhance with contextual information from surrounding text.
        
        Args:
            dosage_str: Direct dosage instruction
            context_text: Surrounding prescription text for additional context
        
        Returns:
            DosageSchedule with merged information
        """
        schedule = cls.parse(dosage_str)
        
        # Look for additional timing hints in context
        context_lower = context_text.lower() if context_text else ""
        
        # Check for meal-related instructions
        if 'with food' in context_lower or 'with meal' in context_lower:
            schedule.instructions += " (with meals)"
        elif 'empty stomach' in context_lower:
            schedule.instructions += " (on empty stomach)"
        elif 'before food' in context_lower:
            schedule.instructions += " (before meals)"
        elif 'after food' in context_lower:
            schedule.instructions += " (after meals)"
        
        # Check for safety warnings
        if 'milk' in context_lower and 'avoid' in context_lower:
            schedule.instructions += " (avoid with milk)"
        
        return schedule


def parse_medication_schedule(dosage_text: str, frequency: str = "", duration: str = "") -> Dict[str, Any]:
    """
    High-level function to parse complete medication schedule information.
    
    Args:
        dosage_text: The dosage amount (e.g., "500mg")
        frequency: The frequency instruction (e.g., "BD", "1-1-0")
        duration: The duration (e.g., "for 7 days")
    
    Returns:
        Dictionary with standardized schedule information
    """
    combined_instruction = " ".join(filter(None, [dosage_text, frequency, duration]))
    schedule = DosageParser.parse(combined_instruction)
    
    return {
        "frequency_per_day": schedule.frequency_per_day,
        "timing": schedule.timing,
        "as_needed": schedule.as_needed,
        "duration_days": schedule.duration_days,
        "standardized_display": DosageParser.normalize_timing_display(schedule),
        "instructions": schedule.instructions,
        "uncertain": schedule.uncertainty
    }
