"""
PII detection and masking using Microsoft Presidio.

CRITICAL: the output of mask_pii() is the ONLY version of a prompt
that may ever be stored in MongoDB or logged anywhere (DPDP Act 2023
compliance — see database/models.py). Raw prompts never touch disk.
"""

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# These are loaded once at import time (model loading is slow) and
# reused across every request.
_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()

# Entities we actively look for. Presidio supports many more; this
# list covers what DPDP Act 2023 cares about most for a chat app.
PII_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "IN_AADHAAR",
    "IN_PAN",
    "LOCATION",
    "IP_ADDRESS",
    "DATE_TIME",
]


def mask_pii(text: str) -> dict:
    """
    Detect and mask PII in `text`.

    Returns:
        {
            "masked_text": str,          # safe to store/log
            "pii_found": bool,
            "entities_found": [str, ...] # entity types detected, e.g. ["EMAIL_ADDRESS"]
        }
    """
    results = _analyzer.analyze(
        text=text,
        entities=PII_ENTITIES,
        language="en",
    )

    if not results:
        return {
            "masked_text": text,
            "pii_found": False,
            "entities_found": [],
        }

    anonymized = _anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={
            "DEFAULT": OperatorConfig(
                "replace", {"new_value": "[REDACTED]"}
            )
        },
    )

    entities_found = sorted({r.entity_type for r in results})

    return {
        "masked_text": anonymized.text,
        "pii_found": True,
        "entities_found": entities_found,
    }
