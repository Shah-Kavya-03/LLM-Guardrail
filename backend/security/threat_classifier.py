"""
Five-tier threat classification.

Tier 1 — Safe               (allow)
Tier 2 — PII Detected        (mask and allow)
Tier 3 — Prompt Injection    (block)
Tier 4 — Harmful Content     (block)
Tier 5 — Jailbreak Attempt   (block + flag user)

Order matters: jailbreak > injection > harmful > PII > safe, since a
message can trigger multiple signals at once (e.g. a jailbreak
attempt that also happens to contain an email address) and we want
the most severe classification to win.
"""

from security.pii_detector import mask_pii
from security.toxicity_scorer import score_toxicity
from security.injection_detector import detect_injection

STATUS_SAFE = "Safe"
STATUS_PII = "PII Detected"
STATUS_INJECTION = "Prompt Injection"
STATUS_HARMFUL = "Harmful"
STATUS_JAILBREAK = "Jailbreak"

TIER_BY_STATUS = {
    STATUS_SAFE: 1,
    STATUS_PII: 2,
    STATUS_INJECTION: 3,
    STATUS_HARMFUL: 4,
    STATUS_JAILBREAK: 5,
}


def classify(text: str) -> dict:
    """
    Run the full pipeline on `text` and return a threat classification.

    Returns:
        {
            "status": "Safe|PII Detected|Prompt Injection|Harmful|Jailbreak",
            "threat_tier": 1-5,
            "blocked": bool,
            "masked_text": str,        # PII-masked version — always safe to store
            "pii": {...},               # raw output from pii_detector
            "toxicity": {...},          # raw output from toxicity_scorer
            "injection": {...},         # raw output from injection_detector
        }
    """
    pii_result = mask_pii(text)
    toxicity_result = score_toxicity(text)
    injection_result = detect_injection(text)

    # Decide status by descending severity.
    if injection_result["is_jailbreak"]:
        status = STATUS_JAILBREAK
    elif toxicity_result["is_toxic"]:
        status = STATUS_HARMFUL
    elif injection_result["is_injection"]:
        status = STATUS_INJECTION
    elif pii_result["pii_found"]:
        status = STATUS_PII
    else:
        status = STATUS_SAFE

    blocked = status in (STATUS_INJECTION, STATUS_HARMFUL, STATUS_JAILBREAK)

    return {
        "status": status,
        "threat_tier": TIER_BY_STATUS[status],
        "blocked": blocked,
        "masked_text": pii_result["masked_text"],
        "pii": pii_result,
        "toxicity": toxicity_result,
        "injection": injection_result,
    }
