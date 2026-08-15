"""
Prompt injection / jailbreak detection.

Two modes, controlled by INJECTION_DETECTOR_MODE in .env:

  "rules" (default) — regex pattern matching. Fast, zero extra
      dependencies, catches known/common phrasings. This is what's
      active during local development.

  "ml" — a pretrained Hugging Face classifier
      (deepset/deberta-v3-base-injection). Catches paraphrased/novel
      attempts the regex list doesn't know about, at the cost of a
      heavier model load and slightly higher per-request latency.
      This is the mode turned on for deployment (see DEPLOYMENT.md).

Both modes return the exact same shape, so nothing outside this file
(threat_classifier.py, chat.py) needs to know which mode is active.
"""

import os
import re

_MODE = os.getenv("INJECTION_DETECTOR_MODE", "rules").lower()

# Patterns are (regex, severity) where severity feeds into the
# five-tier threat classification in threat_classifier.py.
# "injection"  -> attempts to override/ignore system instructions
# "jailbreak"  -> attempts to bypass safety guidelines entirely
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bignore (all|any|the) (previous|prior|above) instructions\b", re.I), "injection"),
    (re.compile(r"\bdisregard (all|any|the) (previous|prior|above)\b", re.I), "injection"),
    (re.compile(r"\byou are now\b.{0,40}\b(dan|jailbroken|unrestricted|uncensored)\b", re.I), "jailbreak"),
    (re.compile(r"\bpretend (you are|to be)\b.{0,40}\bno (rules|restrictions|filters)\b", re.I), "jailbreak"),
    (re.compile(r"\bact as (if )?(dan|an? unrestricted|an? uncensored)\b", re.I), "jailbreak"),
    (re.compile(r"\bsystem prompt\b.{0,30}\b(reveal|show|print|output|leak)\b", re.I), "injection"),
    (re.compile(r"\b(reveal|show|print|output|leak)\b.{0,30}\bsystem prompt\b", re.I), "injection"),
    (re.compile(r"\bdeveloper mode\b", re.I), "jailbreak"),
    (re.compile(r"\bbypass (your |the )?(safety|content|ethical) (guidelines|filters|policy)\b", re.I), "jailbreak"),
    (re.compile(r"\bnew instructions\s*:", re.I), "injection"),
    (re.compile(r"\[\[?\s*system\s*\]?\]", re.I), "injection"),
]

# ML model is only loaded if INJECTION_DETECTOR_MODE=ml — importing
# transformers and downloading weights at import time would slow down
# every local dev startup otherwise, for a mode that's off by default.
_ml_classifier = None
_ML_MODEL_NAME = "deepset/deberta-v3-base-injection"
_ML_CONFIDENCE_THRESHOLD = 0.7


def _get_ml_classifier():
    global _ml_classifier
    if _ml_classifier is None:
        from transformers import pipeline
        _ml_classifier = pipeline("text-classification", model=_ML_MODEL_NAME)
    return _ml_classifier


def _detect_rules(text: str) -> dict:
    matched_patterns = []
    is_injection = False
    is_jailbreak = False

    for pattern, severity in _PATTERNS:
        match = pattern.search(text)
        if match:
            matched_patterns.append(match.group(0))
            if severity == "jailbreak":
                is_jailbreak = True
            else:
                is_injection = True

    return {
        "is_injection": is_injection,
        "is_jailbreak": is_jailbreak,
        "matched_patterns": matched_patterns,
    }


def _detect_ml(text: str) -> dict:
    classifier = _get_ml_classifier()
    result = classifier(text, truncation=True)[0]
    label = result["label"].upper()
    score = result["score"]

    is_injection = label in ("INJECTION", "LABEL_1") and score >= _ML_CONFIDENCE_THRESHOLD

    return {
        "is_injection": is_injection,
        # This model doesn't distinguish jailbreak from generic injection;
        # treat all flagged injections as the "injection" tier, not
        # "jailbreak", until a dedicated jailbreak model is added.
        "is_jailbreak": False,
        "matched_patterns": [f"{label} ({score:.2f})"] if is_injection else [],
    }


def detect_injection(text: str) -> dict:
    """
    Scan `text` for prompt-injection / jailbreak patterns.

    Returns:
        {
            "is_injection": bool,
            "is_jailbreak": bool,
            "matched_patterns": [str, ...]
        }
    """
    if _MODE == "ml":
        return _detect_ml(text)
    return _detect_rules(text)

