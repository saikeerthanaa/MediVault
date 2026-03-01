"""
MediVault - bedrock_service.py
Robust medical entity extraction designed for noisy handwritten prescription OCR.

Key improvements:
- Two-stage extraction: fuzzy drug name matching FIRST, then Bedrock LLM
- Bedrock prompt engineered specifically for noisy/fragmented OCR text
- JSON response cleaned before parsing (handles markdown fences, trailing text)
- Fuzzy matching catches garbled OCR names (e.g. "Cinatidise" → "Cimetidine")
- Indian shorthand fully supported (OD, BD, TDS, QID, HS, SOS, 1-0-1)
- Fallback chain: Bedrock LLM → Fuzzy pattern match → Partial match
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
    DEBUG_AI = Config.DEBUG_AI
except ImportError:
    AWS_REGION = "ap-south-1"
    BEDROCK_MODEL_ID = "amazon.nova-micro-v1:0"
    DEBUG_AI = False


# ─────────────────────────────────────────────
# COMPREHENSIVE DRUG DATABASE (200+ entries)
# Includes common OCR misspellings as aliases
# ─────────────────────────────────────────────
DRUG_DATABASE = {
    # ── Analgesics / NSAIDs ──
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

    # ── Antibiotics ──
    "amoxicillin":      ["amoxicillin", "amoxycillin", "amoxicllin", "amox", "mox"],
    "amoxicillin-clavulanate": ["amoxiclav", "augmentin", "clavamox"],
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

    # ── Antifungals ──
    "fluconazole":      ["fluconazole", "diflucan", "flucoz"],
    "itraconazole":     ["itraconazole", "sporanox"],
    "ketoconazole":     ["ketoconazole", "nizoral"],

    # ── Antihistamines ──
    "cetirizine":       ["cetirizine", "cetrizine", "cetzine", "zyrtec"],
    "loratadine":       ["loratadine", "claritin"],
    "fexofenadine":     ["fexofenadine", "allegra"],
    "chlorpheniramine": ["chlorpheniramine", "chlorphenamine", "cpm"],
    "promethazine":     ["promethazine", "phenergan"],
    "hydroxyzine":      ["hydroxyzine", "atarax"],

    # ── GI / Antacids ──
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

    # ── Cardiovascular ──
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
    "irbesartan":       ["irbesartan", "avapro"],
    "atorvastatin":     ["atorvastatin", "lipitor", "atorva"],
    "rosuvastatin":     ["rosuvastatin", "crestor"],
    "simvastatin":      ["simvastatin", "zocor"],
    "lovastatin":       ["lovastatin"],
    "pravastatin":      ["pravastatin"],
    "warfarin":         ["warfarin", "coumadin"],
    "clopidogrel":      ["clopidogrel", "plavix"],
    "digoxin":          ["digoxin", "lanoxin"],
    "furosemide":       ["furosemide", "lasix"],
    "spironolactone":   ["spironolactone", "aldactone"],
    "hydrochlorothiazide": ["hydrochlorothiazide", "hctz"],
    "nitroglycerine":   ["nitroglycerine", "nitroglycerin", "nitro"],
    "isosorbide":       ["isosorbide", "imdur"],
    "nicorandil":       ["nicorandil", "ikorel"],

    # ── Diabetes ──
    "metformin":        ["metformin", "glucophage", "glycomet"],
    "glibenclamide":    ["glibenclamide", "daonil"],
    "glimepiride":      ["glimepiride", "amaryl"],
    "sitagliptin":      ["sitagliptin", "januvia"],
    "insulin":          ["insulin", "actrapid", "mixtard", "lantus", "glargine", "regular"],
    "empagliflozin":    ["empagliflozin", "jardiance"],
    "dapagliflozin":    ["dapagliflozin", "forxiga"],
    "linagliptin":      ["linagliptin", "tradjenta"],
    "saxagliptin":      ["saxagliptin", "onglyza"],
    "vildagliptin":     ["vildagliptin", "galvus"],

    # ── Thyroid ──
    "levothyroxine":    ["levothyroxine", "thyroxine", "eltroxin", "thyronorm"],
    "liothyronine":     ["liothyronine", "cytomel"],

    # ── Respiratory ──
    "salbutamol":       ["salbutamol", "albuterol", "ventolin"],
    "fluticasone":      ["fluticasone", "flixotide"],
    "salmeterol":       ["salmeterol", "serevent"],
    "montelukast":      ["montelukast", "singulair"],
    "theophylline":     ["theophylline"],
    "ipratropium":      ["ipratropium", "atrovent"],
    "budesonide":       ["budesonide", "pulmicort"],
    "beclomethasone":   ["beclomethasone"],

    # ── CNS / Neurological ──
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
    "memantine":        ["memantine", "namenda"],

    # ── Steroids ──
    "prednisolone":     ["prednisolone", "prednis0lone"],
    "prednisone":       ["prednisone"],
    "dexamethasone":    ["dexamethasone", "decadron"],
    "hydrocortisone":   ["hydrocortisone"],
    "methylprednisolone": ["methylprednisolone", "medrol"],
    "betamethasone":    ["betamethasone"],
    "triamcinolone":    ["triamcinolone"],

    # ── Vitamins / Supplements ──
    "vitamin d":        ["vitamin d", "vitamin d3", "cholecalciferol"],
    "vitamin b12":      ["vitamin b12", "cyanocobalamin", "methylcobalamin"],
    "folic acid":       ["folic acid", "folate"],
    "calcium":          ["calcium carbonate", "calcium"],
    "iron":             ["ferrous sulphate", "ferrous sulfate", "iron"],
    "magnesium":        ["magnesium"],

    # ── Antivirals ──
    "acyclovir":        ["acyclovir", "aciclovir", "zovirax"],
    "oseltamivir":      ["oseltamivir", "tamiflu"],
    "valacyclovir":     ["valacyclovir", "valtrex"],

    # ── Other common ──
    "betahistine":      ["betahistine", "batalan", "serc", "vertin"],
    "baclofen":         ["baclofen", "lioresal"],
    "colchicine":       ["colchicine"],
    "allopurinol":      ["allopurinol", "zyloric"],
    "febuxostat":       ["febuxostat", "uloric"],
}

# Flatten to alias → canonical map for quick lookup
ALIAS_TO_CANONICAL = {}
for canonical, aliases in DRUG_DATABASE.items():
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias.lower()] = canonical.title()


# ─────────────────────────────────────────────
# FREQUENCY / ROUTE / DOSAGE PATTERNS
# ─────────────────────────────────────────────
FREQUENCY_MAP = [
    # Indian shorthands first (priority)
    (r'\bqid\b',                            'Four times daily'),
    (r'\btds\b|\btid\b',                    'Three times daily'),
    (r'\bbd\b|\bbid\b',                     'Twice daily'),
    (r'\bod\b',                             'Once daily'),
    (r'\bhs\b|\bbedtime\b',                 'At bedtime'),
    (r'\bsos\b|\bprn\b|\bas\s+needed\b',    'As needed'),
    (r'\bstat\b',                           'Immediately'),
    # Numeric notation (1-0-1 = morning-afternoon-night)
    (r'\b1\s*[-–]\s*1\s*[-–]\s*1\b',       'Three times daily'),
    (r'\b1\s*[-–]\s*0\s*[-–]\s*1\b',       'Twice daily (morning + night)'),
    (r'\b1\s*[-–]\s*1\s*[-–]\s*0\b',       'Twice daily (morning + afternoon)'),
    (r'\b0\s*[-–]\s*0\s*[-–]\s*1\b',       'Once daily (at night)'),
    (r'\b1\s*[-–]\s*0\s*[-–]\s*0\b',       'Once daily (morning)'),
    # English phrases
    (r'four\s+times?\s+(a\s+)?day',         'Four times daily'),
    (r'three\s+times?\s+(a\s+)?day',        'Three times daily'),
    (r'twice\s+(a\s+)?day|two\s+times',     'Twice daily'),
    (r'once\s+(a\s+)?day|once\s+daily',     'Once daily'),
    (r'every\s+(\d+)\s+hours?',             'Every {1} hours'),
]

ROUTE_MAP = [
    (r'\boral(?:ly)?\b|\bpo\b|\bby\s+mouth\b',         'Oral'),
    (r'\biv\b|\bintravenous',                           'Intravenous'),
    (r'\bim\b|\bintramuscular',                         'Intramuscular'),
    (r'\bsc\b|\bsubcutaneous',                          'Subcutaneous'),
    (r'\binhaler?\b|\binhalation\b|\bpuffs?\b',         'Inhalation'),
    (r'\btopical\b|\bcream\b|\bointment\b|\bgel\b',     'Topical'),
    (r'\bpatch\b|\btransdermal\b',                      'Transdermal'),
    (r'\binjection\b|\binjectable\b|\bsi\b',            'Injection'),
    (r'\bsublingual\b|\bsl\b',                          'Sublingual'),
    (r'\bdrops?\b|\beye\s+drop\b|\bear\s+drop\b',       'Drops'),
    (r'\btab(?:let)?s?\b|\bcapsule?s?\b|\bcap\b',       'Oral'),
]

DOSAGE_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*'
    r'(mg|mcg|µg|g\b|ml|l\b|iu|units?|u\b|tabs?|tablets?|caps?|capsules?|puffs?|drops?|mmol)',
    re.IGNORECASE
)

DURATION_RE = re.compile(
    r'(?:for\s+)?(\d+)\s*(days?|weeks?|months?)',
    re.IGNORECASE
)


# ─────────────────────────────────────────────
# FUZZY MATCHING HELPERS
# ─────────────────────────────────────────────
def _fuzzy_score(a: str, b: str) -> float:
    """Calculate similarity between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _find_drug_fuzzy(token: str, threshold: float = 0.72) -> str | None:
    """Return canonical drug name if token fuzzy-matches any alias above threshold."""
    token_l = token.lower().strip()

    # Exact match first
    if token_l in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[token_l]

    # Fuzzy match against all aliases
    best_score = 0.0
    best_name = None
    for alias, canonical in ALIAS_TO_CANONICAL.items():
        score = _fuzzy_score(token_l, alias)
        if score > best_score:
            best_score = score
            best_name = canonical

    return best_name if best_score >= threshold else None


def _extract_frequency(text: str) -> str:
    """Extract frequency from text using regex patterns."""
    for pattern, label in FREQUENCY_MAP:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if '{1}' in label:
                return label.replace('{1}', m.group(1))
            return label
    return ''


def _extract_route(text: str) -> str:
    """Extract route of administration from text."""
    for pattern, label in ROUTE_MAP:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return ''


def _extract_dosage(text: str) -> str:
    """Extract dosage from text."""
    m = DOSAGE_RE.search(text)
    if m:
        return f"{m.group(1)} {m.group(2).lower()}"
    return ''


def _extract_duration(text: str) -> str:
    """Extract duration from text."""
    m = DURATION_RE.search(text)
    if m:
        unit = m.group(2)
        n = m.group(1)
        return f"For {n} {unit}" if not unit.endswith('s') else f"For {n} {unit}"
    return ''


# ─────────────────────────────────────────────
# STAGE 1: FUZZY PATTERN EXTRACTION
# (works offline, handles OCR noise)
# ─────────────────────────────────────────────
def extract_medications_fuzzy(text: str) -> list:
    """
    Slide a window over every word in the OCR text and fuzzy-match against
    the drug database. For each hit, extract dosage/frequency from surrounding context.
    """
    medications = []
    seen = set()

    # Split into lines for context window
    lines = text.replace('\r', '\n').split('\n')

    for line in lines:
        words = line.split()
        # Try 3-word, 2-word, 1-word windows
        for window_size in [3, 2, 1]:
            for i in range(len(words) - window_size + 1):
                token = ' '.join(words[i:i + window_size])
                # Skip tokens that are clearly not drug names
                if re.fullmatch(r'[\d\W]+', token):
                    continue
                if len(token) < 3:
                    continue

                canonical = _find_drug_fuzzy(token)
                if canonical and canonical.lower() not in seen:
                    seen.add(canonical.lower())

                    # Context = full line + adjacent lines for dosage/freq
                    line_idx = lines.index(line)
                    context_lines = lines[max(0, line_idx - 1):line_idx + 2]
                    context = ' '.join(context_lines)

                    med = {
                        "name": canonical,
                        "dosage": _extract_dosage(context),
                        "frequency": _extract_frequency(context),
                        "duration": _extract_duration(context),
                        "route": _extract_route(context),
                        "notes": "Extracted via fuzzy OCR matching",
                    }
                    medications.append(med)
                    break  # Don't double-count within same window position

    return medications


# ─────────────────────────────────────────────
# STAGE 2: BEDROCK LLM EXTRACTION
# ─────────────────────────────────────────────
BEDROCK_EXTRACTION_PROMPT = """You are a clinical pharmacist reviewing a scanned prescription. The text below was extracted by OCR from a handwritten prescription and may contain noise, misspellings, or garbled characters.

Your job: extract ALL medications and return ONLY a valid JSON object. No explanation, no markdown, no code fences.

JSON format (strict):
{{
  "medications": [
    {{
      "name": "Correct drug name (fix OCR errors, e.g. Cinatidise→Cimetidine)",
      "dosage": "e.g. 100mg, 50mg, 2 tabs",
      "frequency": "e.g. Twice daily, Once daily, Three times daily",
      "duration": "e.g. For 7 days, or empty string if not specified",
      "route": "e.g. Oral, Injection, or empty string"
    }}
  ],
  "conditions": ["any diagnoses mentioned"],
  "allergies": ["any allergies mentioned"]
}}

Rules:
1. Fix obvious OCR errors in drug names (e.g. "Batalan" could be "Betahistine", "Oxpratal" could be "Oxprenolol")
2. Expand abbreviations: BD→Twice daily, OD→Once daily, TDS→Three times daily, QID→Four times daily, HS→At bedtime, PRN→As needed
3. Interpret numeric dosing: "1-0-1" = morning+night (Twice daily), "1-1-1" = Three times daily
4. If a drug name is completely unrecognisable, include it as-is rather than omitting it
5. Return an empty array for medications/conditions/allergies if none found — never omit the keys

OCR TEXT:
{ocr_text}"""


def _call_bedrock(ocr_text: str) -> dict | None:
    """Call Bedrock and return parsed JSON dict, or None on failure."""
    try:
        client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        prompt = BEDROCK_EXTRACTION_PROMPT.format(ocr_text=ocr_text)

        body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
            "anthropic_version": "bedrock-2023-05-31",
        })

        # Try Claude Sonnet first (best for noisy medical text)
        model_ids_to_try = [
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            BEDROCK_MODEL_ID,  # fallback to configured model
        ]

        response_text = None
        for model_id in model_ids_to_try:
            try:
                resp = client.invoke_model(
                    modelId=model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                resp_body = json.loads(resp["body"].read())

                # Handle different response formats
                if "content" in resp_body:
                    # Claude format
                    response_text = resp_body["content"][0]["text"]
                elif "results" in resp_body:
                    # Nova/Titan format
                    response_text = resp_body["results"][0]["outputText"]
                elif "output" in resp_body:
                    response_text = resp_body["output"]["message"]["content"][0]["text"]
                else:
                    response_text = str(resp_body)

                logger.info(f"✅ Bedrock call succeeded with model: {model_id}")
                break

            except ClientError as e:
                code = e.response["Error"]["Code"]
                if code in ("ValidationException", "ResourceNotFoundException"):
                    logger.warning(f"Model {model_id} not available, trying next...")
                    continue
                raise

        if not response_text:
            return None

        return _parse_bedrock_response(response_text)

    except Exception as e:
        logger.error(f"❌ Bedrock call failed: {e}")
        return None


def _parse_bedrock_response(raw: str) -> dict | None:
    """
    Robustly parse JSON from Bedrock response.
    Handles: markdown fences, leading text, trailing text, single quotes.
    """
    # Strip markdown code fences
    raw = re.sub(r'```(?:json)?', '', raw).strip()

    # Find the outermost JSON object
    start = raw.find('{')
    end = raw.rfind('}')
    if start == -1 or end == -1:
        logger.warning("❌ No JSON object found in Bedrock response")
        return None

    json_str = raw[start:end + 1]

    # Fix common LLM JSON issues
    json_str = json_str.replace('\n', ' ')
    # Replace Python-style None/True/False
    json_str = re.sub(r'\bNone\b', 'null', json_str)
    json_str = re.sub(r'\bTrue\b', 'true', json_str)
    json_str = re.sub(r'\bFalse\b', 'false', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}\nRaw JSON: {json_str[:500]}")
        return None


# ─────────────────────────────────────────────
# NORMALIZER (clean OCR noise before extraction)
# ─────────────────────────────────────────────
def normalize_ocr_text(raw_text: str) -> dict:
    """
    Clean common OCR artefacts from handwritten prescription text.
    Returns dict with cleaned_text, corrections, confidence, flags.
    """
    corrections = []
    text = raw_text

    # Common OCR character substitutions
    char_fixes = [
        (r'(?<=[A-Za-z])0(?=[A-Za-z])', 'o'),   # zero→o inside words
        (r'(?<=[A-Za-z])1(?=[A-Za-z])', 'l'),   # one→l inside words
        (r'\|', 'l'),                             # pipe→l
        (r'(?<!\d)rn(?!\d)', 'm'),               # rn→m (common OCR artifact)
    ]
    for pattern, replacement in char_fixes:
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            corrections.append({
                "original": pattern,
                "corrected": replacement,
                "type": "ocr_char_fix",
                "confidence": 0.75,
                "source": "pattern_match"
            })
            text = new_text

    # Abbreviation expansions (record as corrections)
    abbrev_expansions = {
        r'\bBD\b': 'Twice daily',
        r'\bOD\b': 'Once daily',
        r'\bTDS\b': 'Three times daily',
        r'\bQID\b': 'Four times daily',
        r'\bHS\b': 'At bedtime',
        r'\bSOS\b': 'As needed',
        r'\bPRN\b': 'As needed',
        r'\bStat\b': 'Immediately',
    }
    for pattern, expanded in abbrev_expansions.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            corrections.append({
                "original": m.group(0),
                "corrected": expanded,
                "type": "abbrev_expansion",
                "confidence": 0.95,
                "source": "pattern_match"
            })

    # Confidence: lower for short/sparse text
    word_count = len(text.split())
    confidence = min(0.95, max(0.4, word_count / 50))
    flags = []
    if word_count < 10:
        flags.append("very_short_text")
    if re.search(r'[^\x00-\x7F]', text):
        flags.append("non_ascii_chars")

    return {
        "cleaned_text": text.strip(),
        "corrections": corrections,
        "confidence": round(confidence, 3),
        "flags": flags,
        "needs_term_review": True,
    }


# ─────────────────────────────────────────────
# MERGE & UTILITY HELPERS
# ─────────────────────────────────────────────
def _merge_medications(bedrock_meds: list, fuzzy_meds: list) -> list:
    """
    Merge two medication lists. Bedrock result takes priority.
    Fuzzy results are added only if not already present (by name).
    """
    merged = list(bedrock_meds)
    bedrock_names = {m.get("name", "").lower() for m in bedrock_meds}

    for fmed in fuzzy_meds:
        fname = fmed.get("name", "").lower()
        # Check if already captured by Bedrock (fuzzy name match)
        already_present = any(
            _fuzzy_score(fname, bname) > 0.8
            for bname in bedrock_names
        )
        if not already_present:
            merged.append(fmed)

    return merged


def _build_schedule(med: dict) -> dict:
    """Build structured schedule from frequency string."""
    freq = med.get("frequency", "")
    freq_lower = freq.lower()

    freq_map = {
        "four times": 4,
        "three times": 3,
        "twice": 2,
        "once": 1,
        "at bedtime": 1,
        "as needed": 0,
    }
    freq_per_day = 0
    for key, val in freq_map.items():
        if key in freq_lower:
            freq_per_day = val
            break

    # Parse duration_days
    duration_days = None
    dur = med.get("duration", "")
    dm = re.search(r'(\d+)\s*(day|week|month)', dur, re.IGNORECASE)
    if dm:
        n = int(dm.group(1))
        unit = dm.group(2).lower()
        if unit.startswith('week'):
            n *= 7
        elif unit.startswith('month'):
            n *= 30
        duration_days = n

    return {
        "frequency_per_day": freq_per_day,
        "as_needed": "needed" in freq_lower or "prn" in freq_lower or "sos" in freq_lower,
        "duration_days": duration_days,
        "instructions": freq or "As directed",
        "uncertainty": not bool(freq),
    }


def _extract_conditions(text: str) -> list:
    """Extract medical conditions from text."""
    condition_keywords = [
        "hypertension", "diabetes", "asthma", "copd", "hypothyroidism",
        "hyperthyroidism", "depression", "anxiety", "epilepsy", "gerd",
        "gastritis", "uti", "infection", "fever", "pain", "arthritis",
        "gout", "anaemia", "anemia", "vertigo", "migraine",
    ]
    found = []
    text_lower = text.lower()
    for kw in condition_keywords:
        if kw in text_lower:
            found.append(kw.title())
    return found


def _extract_allergies(text: str) -> list:
    """Extract allergies from text."""
    m = re.search(r'allerg(?:ic|y)\s+to\s+([A-Za-z ,]+)', text, re.IGNORECASE)
    if m:
        allergens = [a.strip() for a in m.group(1).split(',') if a.strip()]
        return allergens
    return []


# ─────────────────────────────────────────────
# MAIN SERVICE CLASS
# ─────────────────────────────────────────────
class BedrockService:
    """
    Two-stage medical entity extraction:
    1. Bedrock LLM (best results, requires AWS)
    2. Fuzzy pattern matching (offline fallback)
    Results are MERGED so neither stage loses data.
    """

    def __init__(self, region: str = "ap-south-1", model_id: str = "amazon.nova-micro-v1:0"):
        """Initialize service with AWS region and model."""
        self.region = region
        self.model_id = model_id

    def normalize_and_extract(self, reviewed_text: str, ocr_confidence: float = 0.8,
                              patient_verified: bool = True, debug: bool = False) -> dict:
        """
        Main method called by /ai/normalize-and-extract endpoint.
        Returns full response dict compatible with existing API schema.
        """
        # ── Step 1: Normalize OCR text ──
        normalized = normalize_ocr_text(reviewed_text)
        clean_text = normalized["cleaned_text"]

        # ── Step 2: Try Bedrock LLM first ──
        bedrock_result = _call_bedrock(clean_text)
        bedrock_meds = []
        bedrock_conditions = []
        bedrock_allergies = []

        if bedrock_result:
            bedrock_meds = bedrock_result.get("medications", [])
            bedrock_conditions = bedrock_result.get("conditions", [])
            bedrock_allergies = bedrock_result.get("allergies", [])
            logger.info(f"✅ Bedrock extracted {len(bedrock_meds)} medications")
        else:
            logger.warning("⚠️  Bedrock extraction failed or returned empty — using fuzzy fallback")

        # ── Step 3: Always run fuzzy matching as supplement ──
        fuzzy_meds = extract_medications_fuzzy(clean_text)
        logger.info(f"✅ Fuzzy extracted {len(fuzzy_meds)} medications")

        # ── Step 4: Merge results (Bedrock wins on conflicts, fuzzy fills gaps) ──
        merged_meds = _merge_medications(bedrock_meds, fuzzy_meds)

        # ── Step 5: Enrich each med with schedule info ──
        for med in merged_meds:
            med["schedule"] = _build_schedule(med)

        entities = {
            "medications": merged_meds,
            "conditions": bedrock_conditions or _extract_conditions(clean_text),
            "allergies": bedrock_allergies or _extract_allergies(clean_text),
            "lab_values": [],
        }

        response = {
            "ok": True,
            "normalized": normalized,
            "entities": entities,
        }

        if debug or DEBUG_AI:
            response["extraction_debug"] = {
                "bedrock_med_count": len(bedrock_meds),
                "fuzzy_med_count": len(fuzzy_meds),
                "merged_count": len(merged_meds),
                "bedrock_ok": bedrock_result is not None,
                "clean_text_preview": clean_text[:200],
            }

        return response

    # Kept for backward compat with older callers
    def normalize_text(self, text: str, patient_verified: bool = False, ocr_confidence: float = 0.8) -> dict:
        """Backward compatible: normalize text without extraction."""
        return normalize_ocr_text(text)

    def extract_entities(self, text: str) -> dict:
        """Backward compatible: extract entities only."""
        result = self.normalize_and_extract(text)
        return result.get("entities", {
            "medications": [],
            "conditions": [],
            "allergies": [],
            "lab_values": []
        })


# ─────────────────────────────────────────────
# BEDROCK CONNECTION TEST
# ─────────────────────────────────────────────
def test_bedrock_connection(region: str = "ap-south-1", model_id: str = "amazon.nova-micro-v1:0"):
    """
    Test Bedrock connectivity.
    Returns tuple: (success: bool, message: str)
    """
    try:
        client = boto3.client("bedrock-runtime", region_name=region)

        print(f"📡 Testing Bedrock model: {model_id}")
        print(f"📡 Region: {region}")

        # Use Converse API
        response = client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": "Say Bedrock OK"}]
                }
            ]
        )

        # Parse response from Converse API
        result = response.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "").strip()

        print(f"✅ Bedrock is WORKING!")
        return True, f"✅ Bedrock is ACTIVE - {result}"

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ Bedrock connection failed ({error_type}): {error_msg}")

        # Provide user-friendly fallback message
        return False, f"⚠️ Bedrock UNAVAILABLE - Using MOCK MODE with fuzzy matching (Error: {error_type})"
