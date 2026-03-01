"""
MediVault - bedrock_service.py

ROOT CAUSE FIX:
  The previous version sent `anthropic_version` + `max_tokens` in the request body,
  which is the Claude invoke_model format. Amazon Nova (nova-micro) uses a completely
  different body schema, so every call silently failed → empty medications [].

  FIX: Use the Bedrock Converse API (client.converse()) which accepts ONE unified
  format for ALL models (Nova, Claude, Titan, Llama). No model-specific body needed.

Pipeline:
  1. Normalize OCR text (fix char artifacts, expand abbreviations)
  2. Call Bedrock via Converse API with a handwriting-aware prompt
  3. ALWAYS also run fuzzy matching (catches what LLM misses, works offline)
  4. Merge both results — Bedrock wins on conflicts, fuzzy fills gaps
"""

import re
import json
import logging
import boto3
from difflib import SequenceMatcher
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
try:
    from config import Config
    AWS_REGION = Config.AWS_REGION
    BEDROCK_MODEL_ID = Config.BEDROCK_MODEL_ID
    DEBUG_AI = getattr(Config, 'DEBUG_AI', False)
except (ImportError, AttributeError):
    AWS_REGION = "ap-south-1"
    BEDROCK_MODEL_ID = "amazon.nova-micro-v1:0"
    DEBUG_AI = False


# ─────────────────────────────────────────────
# DRUG DATABASE  (canonical name → aliases incl. OCR misspellings)
# ─────────────────────────────────────────────
DRUG_DATABASE = {
    # Analgesics / NSAIDs
    "paracetamol":      ["paracetamol", "paracetamoi", "parcetamol", "paracetamo"],
    "acetaminophen":    ["acetaminophen", "tylenol"],
    "ibuprofen":        ["ibuprofen", "lbuprofen", "ibupr0fen", "brufen", "advil"],
    "aspirin":          ["aspirin", "asprin", "ecosprin", "disprin"],
    "diclofenac":       ["diclofenac", "diclofenag", "voltaren", "voveran"],
    "naproxen":         ["naproxen", "naprosyn"],
    "tramadol":         ["tramadol", "tramodol", "tramal", "ultram"],
    "morphine":         ["morphine", "morph"],
    "codeine":          ["codeine", "codine"],
    "indomethacin":     ["indomethacin", "indocin"],
    "meloxicam":        ["meloxicam", "mobicox"],
    # Antibiotics
    "amoxicillin":              ["amoxicillin", "amoxycillin", "amoxicllin", "amox", "mox"],
    "amoxicillin-clavulanate":  ["amoxiclav", "augmentin", "clavamox"],
    "azithromycin":     ["azithromycin", "azithromydn", "azee", "zithromax", "azithro"],
    "ciprofloxacin":    ["ciprofloxacin", "cipro", "ciplox"],
    "doxycycline":      ["doxycycline", "doxycycine", "doxycyclin"],
    "cephalexin":       ["cephalexin", "cefalexin", "keflex"],
    "cefuroxime":       ["cefuroxime", "zinnat"],
    "metronidazole":    ["metronidazole", "flagyl", "metrogyl"],
    "clindamycin":      ["clindamycin", "cleocin"],
    "erythromycin":     ["erythromycin", "erythrocin"],
    "trimethoprim":     ["trimethoprim", "tmp"],
    "nitrofurantoin":   ["nitrofurantoin", "macrobid"],
    "levofloxacin":     ["levofloxacin", "levaquin"],
    "moxifloxacin":     ["moxifloxacin", "avelox"],
    "penicillin":       ["penicillin"],
    # Antifungals
    "fluconazole":      ["fluconazole", "diflucan", "flucoz"],
    "itraconazole":     ["itraconazole", "sporanox"],
    "ketoconazole":     ["ketoconazole", "nizoral"],
    # Antihistamines
    "cetirizine":       ["cetirizine", "cetrizine", "cetzine", "zyrtec"],
    "loratadine":       ["loratadine", "claritin"],
    "fexofenadine":     ["fexofenadine", "allegra"],
    "chlorpheniramine": ["chlorpheniramine", "chlorphenamine", "cpm"],
    "promethazine":     ["promethazine", "phenergan"],
    "hydroxyzine":      ["hydroxyzine", "atarax"],
    # GI / Antacids
    "omeprazole":       ["omeprazole", "prilosec", "omez"],
    "pantoprazole":     ["pantoprazole", "protonix", "pan"],
    "ranitidine":       ["ranitidine", "zantac"],
    "cimetidine":       ["cimetidine", "cinatidise", "cimatidine", "cimetidise", "tagamet"],
    "domperidone":      ["domperidone", "motilium"],
    "metoclopramide":   ["metoclopramide", "maxolon", "perinorm"],
    "ondansetron":      ["ondansetron", "zofran"],
    "loperamide":       ["loperamide", "imodium"],
    "lactulose":        ["lactulose"],
    "esomeprazole":     ["esomeprazole", "nexium"],
    # Cardiovascular
    "amlodipine":       ["amlodipine", "norvasc", "amlong"],
    "atenolol":         ["atenolol", "tenormin"],
    "metoprolol":       ["metoprolol", "lopressor", "betaloc"],
    "propranolol":      ["propranolol", "inderal"],
    "oxprenolol":       ["oxprenolol", "oxpratal", "oxprenol", "trasicor"],
    "bisoprolol":       ["bisoprolol", "cardicor"],
    "lisinopril":       ["lisinopril", "zestril"],
    "enalapril":        ["enalapril", "vasotec"],
    "ramipril":         ["ramipril", "tritace", "altace"],
    "losartan":         ["losartan", "cozaar"],
    "telmisartan":      ["telmisartan", "micardis"],
    "valsartan":        ["valsartan", "diovan"],
    "atorvastatin":     ["atorvastatin", "lipitor", "atorva"],
    "rosuvastatin":     ["rosuvastatin", "crestor"],
    "simvastatin":      ["simvastatin", "zocor"],
    "warfarin":         ["warfarin", "coumadin"],
    "clopidogrel":      ["clopidogrel", "plavix"],
    "digoxin":          ["digoxin", "lanoxin"],
    "furosemide":       ["furosemide", "lasix"],
    "spironolactone":   ["spironolactone", "aldactone"],
    "hydrochlorothiazide": ["hydrochlorothiazide", "hctz"],
    "nitroglycerine":   ["nitroglycerine", "nitroglycerin", "nitro"],
    "isosorbide":       ["isosorbide", "imdur"],
    "nicorandil":       ["nicorandil", "ikorel"],
    # Diabetes
    "metformin":        ["metformin", "glucophage", "glycomet"],
    "glibenclamide":    ["glibenclamide", "daonil"],
    "glimepiride":      ["glimepiride", "amaryl"],
    "sitagliptin":      ["sitagliptin", "januvia"],
    "insulin":          ["insulin", "actrapid", "mixtard", "lantus", "glargine", "regular"],
    "empagliflozin":    ["empagliflozin", "jardiance"],
    "dapagliflozin":    ["dapagliflozin", "forxiga"],
    "linagliptin":      ["linagliptin", "tradjenta"],
    "vildagliptin":     ["vildagliptin", "galvus"],
    # Thyroid
    "levothyroxine":    ["levothyroxine", "thyroxine", "eltroxin", "thyronorm"],
    # Respiratory
    "salbutamol":       ["salbutamol", "albuterol", "ventolin"],
    "fluticasone":      ["fluticasone", "flixotide"],
    "salmeterol":       ["salmeterol", "serevent"],
    "montelukast":      ["montelukast", "singulair"],
    "theophylline":     ["theophylline"],
    "ipratropium":      ["ipratropium", "atrovent"],
    "budesonide":       ["budesonide", "pulmicort"],
    # CNS / Neurological
    "amitriptyline":    ["amitriptyline", "elavil"],
    "sertraline":       ["sertraline", "zoloft"],
    "fluoxetine":       ["fluoxetine", "prozac"],
    "escitalopram":     ["escitalopram", "lexapro"],
    "paroxetine":       ["paroxetine", "paxil"],
    "venlafaxine":      ["venlafaxine", "effexor"],
    "alprazolam":       ["alprazolam", "xanax"],
    "diazepam":         ["diazepam", "valium"],
    "lorazepam":        ["lorazepam", "ativan"],
    "zolpidem":         ["zolpidem", "ambien"],
    "haloperidol":      ["haloperidol", "haldol"],
    "carbamazepine":    ["carbamazepine", "tegretol"],
    "phenytoin":        ["phenytoin", "dilantin"],
    "gabapentin":       ["gabapentin", "neurontin"],
    "pregabalin":       ["pregabalin", "lyrica"],
    "levodopa":         ["levodopa", "sinemet"],
    "donepezil":        ["donepezil", "aricept"],
    # Steroids
    "prednisolone":     ["prednisolone"],
    "prednisone":       ["prednisone"],
    "dexamethasone":    ["dexamethasone", "decadron"],
    "hydrocortisone":   ["hydrocortisone"],
    "methylprednisolone": ["methylprednisolone", "medrol"],
    "betamethasone":    ["betamethasone"],
    # Vitamins / Supplements
    "vitamin d3":       ["vitamin d", "vitamin d3", "cholecalciferol"],
    "vitamin b12":      ["vitamin b12", "cyanocobalamin", "methylcobalamin"],
    "folic acid":       ["folic acid", "folate"],
    "calcium":          ["calcium carbonate", "calcium"],
    "iron":             ["ferrous sulphate", "ferrous sulfate", "iron"],
    # Antivirals
    "acyclovir":        ["acyclovir", "aciclovir", "zovirax"],
    "oseltamivir":      ["oseltamivir", "tamiflu"],
    # Other
    "betahistine":      ["betahistine", "batalan", "serc", "vertin"],
    "baclofen":         ["baclofen", "lioresal"],
    "colchicine":       ["colchicine"],
    "allopurinol":      ["allopurinol", "zyloric"],
    "febuxostat":       ["febuxostat", "uloric"],
}

ALIAS_TO_CANONICAL: dict = {}
for _c, _al in DRUG_DATABASE.items():
    for _a in _al:
        ALIAS_TO_CANONICAL[_a.lower()] = _c.title()

# ─────────────────────────────────────────────
# REGEX PATTERNS
# ─────────────────────────────────────────────
FREQUENCY_MAP = [
    (r'\bqid\b',                            'Four times daily'),
    (r'\btds\b|\btid\b',                    'Three times daily'),
    (r'\bbd\b|\bbid\b',                     'Twice daily'),
    (r'\bod\b',                             'Once daily'),
    (r'\bhs\b|\bbedtime\b',                 'At bedtime'),
    (r'\bsos\b|\bprn\b|\bas\s+needed\b',    'As needed'),
    (r'\bstat\b',                           'Immediately'),
    (r'\b1\s*[-–]\s*1\s*[-–]\s*1\b',       'Three times daily'),
    (r'\b1\s*[-–]\s*0\s*[-–]\s*1\b',       'Twice daily (morning + night)'),
    (r'\b1\s*[-–]\s*1\s*[-–]\s*0\b',       'Twice daily (morning + afternoon)'),
    (r'\b0\s*[-–]\s*0\s*[-–]\s*1\b',       'Once daily (at night)'),
    (r'\b1\s*[-–]\s*0\s*[-–]\s*0\b',       'Once daily (morning)'),
    (r'four\s+times?\s+(a\s+)?day',         'Four times daily'),
    (r'three\s+times?\s+(a\s+)?day',        'Three times daily'),
    (r'twice\s+(a\s+)?day|two\s+times',     'Twice daily'),
    (r'once\s+(a\s+)?day|once\s+daily',     'Once daily'),
    (r'every\s+(\d+)\s+hours?',             'Every {1} hours'),
]
ROUTE_MAP = [
    (r'\boral(?:ly)?\b|\bpo\b|\bby\s+mouth\b',  'Oral'),
    (r'\biv\b|\bintravenous',                    'Intravenous'),
    (r'\bim\b|\bintramuscular',                  'Intramuscular'),
    (r'\bsc\b|\bsubcutaneous',                   'Subcutaneous'),
    (r'\binhaler?\b|\binhalation\b|\bpuffs?\b',  'Inhalation'),
    (r'\btopical\b|\bcream\b|\bointment\b|\bgel\b', 'Topical'),
    (r'\bpatch\b|\btransdermal\b',               'Transdermal'),
    (r'\binjection\b|\binjectable\b|\bsi\b',     'Injection'),
    (r'\bsublingual\b|\bsl\b',                   'Sublingual'),
    (r'\bdrops?\b|\beye\s+drop\b|\bear\s+drop\b','Drops'),
    (r'\btab(?:let)?s?\b|\bcapsule?s?\b|\bcap\b','Oral'),
]
DOSAGE_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(mg|mcg|µg|g\b|ml|l\b|iu|units?|u\b|tabs?|tablets?|caps?|capsules?|puffs?|drops?|mmol)',
    re.IGNORECASE
)
DURATION_RE = re.compile(r'(?:for\s+)?(\d+)\s*(days?|weeks?|months?)', re.IGNORECASE)


# ─────────────────────────────────────────────
# FUZZY HELPERS
# ─────────────────────────────────────────────
def _fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def _find_drug_fuzzy(token: str, threshold: float = 0.72):
    token_l = token.lower().strip()
    if token_l in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[token_l]
    best_score, best_name = 0.0, None
    for alias, canonical in ALIAS_TO_CANONICAL.items():
        s = _fuzzy_score(token_l, alias)
        if s > best_score:
            best_score, best_name = s, canonical
    return best_name if best_score >= threshold else None

def _extract_frequency(text: str) -> str:
    for pattern, label in FREQUENCY_MAP:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return label.replace('{1}', m.group(1)) if '{1}' in label else label
    return ''

def _extract_route(text: str) -> str:
    for pattern, label in ROUTE_MAP:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return ''

def _extract_dosage(text: str) -> str:
    m = DOSAGE_RE.search(text)
    return f"{m.group(1)} {m.group(2).lower()}" if m else ''

def _extract_duration(text: str) -> str:
    m = DURATION_RE.search(text)
    if m:
        n, unit = m.group(1), m.group(2)
        return f"For {n} {unit if unit.endswith('s') else unit}"
    return ''

def extract_medications_fuzzy(text: str) -> list:
    medications, seen = [], set()
    lines = text.replace('\r', '\n').split('\n')
    for line_idx, line in enumerate(lines):
        words = line.split()
        for window_size in [3, 2, 1]:
            for i in range(len(words) - window_size + 1):
                token = ' '.join(words[i:i + window_size])
                if re.fullmatch(r'[\d\W]+', token) or len(token) < 3:
                    continue
                canonical = _find_drug_fuzzy(token)
                if canonical and canonical.lower() not in seen:
                    seen.add(canonical.lower())
                    context = ' '.join(lines[max(0, line_idx - 1):line_idx + 2])
                    medications.append({
                        "name": canonical,
                        "dosage": _extract_dosage(context),
                        "frequency": _extract_frequency(context),
                        "duration": _extract_duration(context),
                        "route": _extract_route(context),
                        "notes": "Extracted via fuzzy OCR matching",
                    })
                    break
    return medications


# ─────────────────────────────────────────────
# BEDROCK — Converse API (model-agnostic)
# ─────────────────────────────────────────────
EXTRACTION_PROMPT = """You are a clinical pharmacist reviewing a scanned prescription. The text was extracted by OCR from a HANDWRITTEN prescription and may contain noise, misspellings, or garbled characters.

Extract ALL medications. Return ONLY valid JSON — no explanation, no markdown fences.

{{
  "medications": [
    {{
      "name": "Corrected drug name (fix OCR errors: Cinatidise->Cimetidine, Batalan->Betahistine, Oxpratal->Oxprenolol)",
      "dosage": "e.g. 100mg, 50mg, 2 tabs — empty string if unclear",
      "frequency": "expand: BD->Twice daily, OD->Once daily, TDS->Three times daily, QID->Four times daily, HS->At bedtime, PRN/SOS->As needed",
      "duration": "e.g. For 7 days — empty string if not specified",
      "route": "Oral/Injection/Inhalation/Topical — empty string if not specified"
    }}
  ],
  "conditions": ["any diagnoses or complaints mentioned"],
  "allergies": ["any allergies mentioned"]
}}

Rules:
- 1-0-1 = Twice daily (morning + night); 1-1-1 = Three times daily
- Include drugs even if name is garbled — correct what you can, keep as-is if unsure
- NEVER omit the medications/conditions/allergies keys even if empty arrays

PRESCRIPTION TEXT:
{ocr_text}"""


def _call_bedrock_converse(ocr_text: str, region: str, model_id: str):
    """
    THE KEY FIX: Use client.converse() instead of client.invoke_model().
    Converse API works with Nova, Claude, Titan, Llama — same request format.
    invoke_model() requires different body schemas per model family.
    """
    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        prompt = EXTRACTION_PROMPT.format(ocr_text=ocr_text)

        response = client.converse(
            modelId=model_id,
            messages=[{
                "role": "user",
                "content": [{"text": prompt}]
            }],
            inferenceConfig={
                "maxTokens": 1500,
                "temperature": 0.1,
            }
        )

        raw = response["output"]["message"]["content"][0]["text"]
        logger.info(f"✅ Bedrock converse succeeded ({model_id})")
        return _parse_json_response(raw)

    except ClientError as e:
        logger.error(f"❌ Bedrock ClientError ({e.response['Error']['Code']}): {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Bedrock converse failed: {e}")
        return None


def _parse_json_response(raw: str):
    raw = re.sub(r'```(?:json)?', '', raw).strip()
    start, end = raw.find('{'), raw.rfind('}')
    if start == -1 or end == -1:
        logger.warning("No JSON object in Bedrock response")
        return None
    json_str = raw[start:end + 1]
    json_str = re.sub(r'\bNone\b', 'null', json_str)
    json_str = re.sub(r'\bTrue\b', 'true', json_str)
    json_str = re.sub(r'\bFalse\b', 'false', json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} | snippet: {json_str[:300]}")
        return None


# ─────────────────────────────────────────────
# OCR NORMALIZER
# ─────────────────────────────────────────────
def normalize_ocr_text(raw_text: str) -> dict:
    corrections, text = [], raw_text
    for pattern, replacement in [
        (r'(?<=[A-Za-z])0(?=[A-Za-z])', 'o'),
        (r'(?<=[A-Za-z])1(?=[A-Za-z])', 'l'),
        (r'\|', 'l'),
        (r'(?<!\d)rn(?!\d)', 'm'),
    ]:
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            corrections.append({"original": pattern, "corrected": replacement,
                                 "type": "ocr_char_fix", "confidence": 0.75, "source": "pattern_match"})
            text = new_text

    for pattern, expanded in {
        r'\bBD\b': 'Twice daily', r'\bOD\b': 'Once daily',
        r'\bTDS\b': 'Three times daily', r'\bQID\b': 'Four times daily',
        r'\bHS\b': 'At bedtime', r'\bSOS\b': 'As needed',
        r'\bPRN\b': 'As needed', r'\bStat\b': 'Immediately',
    }.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            corrections.append({"original": m.group(0), "corrected": expanded,
                                 "type": "abbrev_expansion", "confidence": 0.95, "source": "pattern_match"})

    word_count = len(text.split())
    return {
        "cleaned_text": text.strip(),
        "corrections": corrections,
        "confidence": round(min(0.95, max(0.4, word_count / 50)), 3),
        "flags": (["very_short_text"] if word_count < 10 else []) +
                 (["non_ascii_chars"] if re.search(r'[^\x00-\x7F]', text) else []),
        "needs_term_review": True,
    }


# ─────────────────────────────────────────────
# MERGE + SCHEDULE
# ─────────────────────────────────────────────
def _merge_medications(bedrock_meds: list, fuzzy_meds: list) -> list:
    merged = list(bedrock_meds)
    bedrock_names = {m.get("name", "").lower() for m in bedrock_meds}
    for fmed in fuzzy_meds:
        fname = fmed.get("name", "").lower()
        if not any(_fuzzy_score(fname, bn) > 0.8 for bn in bedrock_names):
            merged.append(fmed)
    return merged

def _build_schedule(med: dict) -> dict:
    freq = med.get("frequency", "")
    freq_lower = freq.lower()
    freq_map = {"four times": 4, "three times": 3, "twice": 2, "once": 1, "at bedtime": 1, "as needed": 0}
    freq_per_day = next((v for k, v in freq_map.items() if k in freq_lower), 0)
    duration_days = None
    dm = re.search(r'(\d+)\s*(day|week|month)', med.get("duration", ""), re.IGNORECASE)
    if dm:
        n, unit = int(dm.group(1)), dm.group(2).lower()
        duration_days = n * (7 if unit.startswith('week') else 30 if unit.startswith('month') else 1)
    return {
        "frequency_per_day": freq_per_day,
        "as_needed": any(w in freq_lower for w in ("needed", "prn", "sos")),
        "duration_days": duration_days,
        "instructions": freq or "As directed",
        "uncertainty": not bool(freq),
    }

def _extract_conditions(text: str) -> list:
    keywords = ["hypertension", "diabetes", "asthma", "copd", "hypothyroidism",
                 "hyperthyroidism", "depression", "anxiety", "epilepsy", "gerd",
                 "gastritis", "uti", "infection", "fever", "pain", "arthritis",
                 "gout", "anaemia", "anemia", "vertigo", "migraine"]
    text_lower = text.lower()
    return [kw.title() for kw in keywords if kw in text_lower]

def _extract_allergies(text: str) -> list:
    m = re.search(r'allerg(?:ic|y)\s+to\s+([A-Za-z ,]+)', text, re.IGNORECASE)
    return [a.strip() for a in m.group(1).split(',') if a.strip()] if m else []


# ─────────────────────────────────────────────
# MAIN SERVICE CLASS
# ─────────────────────────────────────────────
class BedrockService:
    def __init__(self, region: str = "ap-south-1", model_id: str = "amazon.nova-micro-v1:0"):
        self.region = region
        self.model_id = model_id

    def normalize_and_extract(self, reviewed_text: str, ocr_confidence: float = 0.8,
                              patient_verified: bool = True, debug: bool = False) -> dict:
        # Step 1: normalize OCR
        normalized = normalize_ocr_text(reviewed_text)
        clean_text = normalized["cleaned_text"]

        # Step 2: Bedrock via Converse API (THE FIX)
        bedrock_result = _call_bedrock_converse(clean_text, self.region, self.model_id)
        bedrock_meds = bedrock_conditions = bedrock_allergies = []
        if bedrock_result:
            bedrock_meds       = bedrock_result.get("medications", [])
            bedrock_conditions = bedrock_result.get("conditions", [])
            bedrock_allergies  = bedrock_result.get("allergies", [])
            logger.info(f"✅ Bedrock extracted {len(bedrock_meds)} medication(s)")
        else:
            logger.warning("⚠️  Bedrock returned nothing — fuzzy fallback will cover")

        # Step 3: fuzzy (always runs)
        fuzzy_meds = extract_medications_fuzzy(clean_text)
        logger.info(f"🔍 Fuzzy extracted {len(fuzzy_meds)} medication(s)")

        # Step 4: merge
        merged_meds = _merge_medications(bedrock_meds, fuzzy_meds)

        # Step 5: enrich with schedule
        for med in merged_meds:
            med["schedule"] = _build_schedule(med)

        entities = {
            "medications": merged_meds,
            "conditions":  bedrock_conditions or _extract_conditions(clean_text),
            "allergies":   bedrock_allergies  or _extract_allergies(clean_text),
            "lab_values":  [],
        }

        response = {"ok": True, "normalized": normalized, "entities": entities}

        if debug or DEBUG_AI:
            response["extraction_debug"] = {
                "bedrock_ok":        bedrock_result is not None,
                "bedrock_med_count": len(bedrock_meds),
                "fuzzy_med_count":   len(fuzzy_meds),
                "merged_count":      len(merged_meds),
                "model_used":        self.model_id,
                "api_method":        "converse",
                "clean_text_preview": clean_text[:200],
            }

        return response

    def normalize_text(self, text: str, patient_verified: bool = False,
                       ocr_confidence: float = 0.8) -> dict:
        return normalize_ocr_text(text)

    def extract_entities(self, text: str) -> dict:
        result = self.normalize_and_extract(text)
        return result.get("entities", {
            "medications": [], "conditions": [], "allergies": [], "lab_values": []
        })


# ─────────────────────────────────────────────
# CONNECTION TEST
# ─────────────────────────────────────────────
def test_bedrock_connection(region: str = None, model_id: str = None):
    region   = region   or AWS_REGION
    model_id = model_id or BEDROCK_MODEL_ID
    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply with: OK"}]}],
            inferenceConfig={"maxTokens": 10}
        )
        reply = response["output"]["message"]["content"][0]["text"].strip()
        return True, f"✅ Bedrock ACTIVE via Converse API — {reply}"
    except Exception as e:
        return False, f"⚠️ Bedrock UNAVAILABLE ({type(e).__name__}) — fuzzy fallback active"