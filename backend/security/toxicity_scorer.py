"""
Toxicity scoring using Detoxify.

Used on BOTH the incoming user prompt and the outgoing LLM response
(see routers/chat.py) — harmful content can appear on either side.
"""

from detoxify import Detoxify

# Loaded once at import time (loads a model into memory).
# "original" is the standard English toxicity model.
_model = Detoxify("original")

# Above this score for any single label, we treat the text as toxic.
# Detoxify scores are 0.0-1.0 per label. 0.5 is a common default
# threshold; tune this later once you see real traffic.
TOXICITY_THRESHOLD = 0.5


def score_toxicity(text: str) -> dict:
    """
    Score `text` for toxicity.

    Returns:
        {
            "is_toxic": bool,
            "max_score": float,          # highest score across all labels
            "scores": {label: float, ...},
            "flagged_labels": [str, ...] # labels that crossed the threshold
        }
    """
    if not text or not text.strip():
        return {
            "is_toxic": False,
            "max_score": 0.0,
            "scores": {},
            "flagged_labels": [],
        }

    raw_scores = _model.predict(text)
    # raw_scores values come back as numpy floats; cast to plain float
    # so this is JSON-serializable without extra handling downstream.
    scores = {label: float(score) for label, score in raw_scores.items()}

    flagged_labels = [
        label for label, score in scores.items() if score >= TOXICITY_THRESHOLD
    ]

    return {
        "is_toxic": len(flagged_labels) > 0,
        "max_score": max(scores.values()) if scores else 0.0,
        "scores": scores,
        "flagged_labels": flagged_labels,
    }
