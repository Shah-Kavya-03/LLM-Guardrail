"""
Plain-English explanations for why a message was blocked or flagged.

NOTE ON NAMING: the frontend/spec calls this field "lime_explanation".
True LIME (Local Interpretable Model-agnostic Explanations) explains
individual predictions of an ML classifier by perturbing inputs and
observing output changes — it fits a case where a single black-box
model made the call. Our threat_classifier is a combination of a
rule-based injection detector, Presidio's entity recognition, and
Detoxify's multi-label scores; each already tells us exactly which
rule/entity/label fired. Re-running LIME on top of that would explain
Detoxify's toxicity score alone, not the overall decision, while
adding real latency to every request for a marginal gain.

This module builds the same field the frontend expects, from the
signals we already have — genuinely plain English, always accurate to
what actually fired, and immediate. If you later want true LIME output
specifically on the toxicity score, ml/lime_explainer.py is a natural
place to add it as a supplementary detail.
"""


def explain(classification: dict) -> str:
    """
    Build a plain-English explanation from a threat_classifier result.

    Args:
        classification: the dict returned by threat_classifier.classify()

    Returns:
        A short, non-technical sentence explaining the outcome.
    """
    status = classification["status"]

    if status == "Safe":
        return "No issues detected. Your message was processed normally."

    if status == "PII Detected":
        entities = classification["pii"]["entities_found"]
        readable = _readable_entities(entities)
        return (
            f"We found what looks like personal information in your message "
            f"({readable}). It was masked before being sent or stored, but "
            f"your message was still processed."
        )

    if status == "Prompt Injection":
        matched = classification["injection"]["matched_patterns"]
        snippet = matched[0] if matched else "an instruction override attempt"
        return (
            f"Your message was blocked because it looked like an attempt to "
            f"override the assistant's instructions (detected phrase: "
            f'"{snippet}"). If this was unintentional, try rephrasing your '
            f"message."
        )

    if status == "Harmful":
        labels = classification["toxicity"]["flagged_labels"]
        readable = _readable_labels(labels)
        return (
            f"Your message was blocked because it was flagged as potentially "
            f"harmful ({readable}). Please rephrase your message."
        )

    if status == "Jailbreak":
        return (
            "Your message was blocked because it matched a known pattern for "
            "attempting to bypass the assistant's safety guidelines. This "
            "account has been flagged for review."
        )

    return "Your message could not be processed."


def _readable_entities(entities: list[str]) -> str:
    labels = {
        "PERSON": "a name",
        "EMAIL_ADDRESS": "an email address",
        "PHONE_NUMBER": "a phone number",
        "CREDIT_CARD": "a credit card number",
        "US_SSN": "a social security number",
        "IN_AADHAAR": "an Aadhaar number",
        "IN_PAN": "a PAN number",
        "LOCATION": "a location",
        "IP_ADDRESS": "an IP address",
        "DATE_TIME": "a date or time",
    }
    readable = [labels.get(e, e.lower().replace("_", " ")) for e in entities]
    return ", ".join(readable) if readable else "sensitive information"


def _readable_labels(labels: list[str]) -> str:
    friendly = {
        "toxicity": "general toxicity",
        "severe_toxicity": "severe toxicity",
        "obscene": "obscene language",
        "threat": "threatening language",
        "insult": "insulting language",
        "identity_attack": "identity-based attack",
    }
    readable = [friendly.get(l, l.replace("_", " ")) for l in labels]
    return ", ".join(readable) if readable else "harmful content"
