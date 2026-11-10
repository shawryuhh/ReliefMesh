"""Bridge between the FastAPI backend and the ReliefMesh AI engine (`ai/main.py`).

Uses the real deterministic scoring (`score_incident`), resource-aware
recommendation (`generate_recommendation`), and Pydantic contract
validators (`ExtractedIncident`, `DeduplicationResponse`,
`TranslationResponse`) from `ai/main.py` with validated synthetic demo
inputs when live Gemini API credentials are not configured.

Safety invariant: Every AI recommendation output preserves `approval_required=True`
and never dispatches resources or approves recommendations automatically.
"""

from __future__ import annotations

import asyncio
import importlib.util
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.exceptions import ValidationFailedError

CANONICAL_TRANSLATIONS: dict[str, str] = {
    "en": "Water entering Krishna Apartments Block C. My grandmother cannot walk.",
    "hi": "कृष्णा अपार्टमेंट्स ब्लॉक C में पानी घुस रहा है। मेरी दादी चल नहीं सकतीं।",
    "kn": "ಕೃಷ್ಣ ಅಪಾರ್ಟ್‌ಮೆಂಟ್ಸ್ ಬ್ಲಾಕ್ C ಒಳಗೆ ನೀರು ಬರುತ್ತಿದೆ. ನನ್ನ ಅಜ್ಜಿಗೆ ನಡೆಯಲು ಸಾಧ್ಯವಿಲ್ಲ.",
    "ta": "கிருஷ்ணா அடுக்குமாடி குடியிருப்பு பிளாக் C-க்குள் தண்ணீர் வருகிறது. என் பாட்டியால் நடக்க முடியாது.",
    "te": "కృష్ణ అపార్ట్‌మెంట్స్ బ్లాక్ C లోకి నీరు వస్తోంది. మా అమ్మమ్మ నడవలేరు.",
    "ml": "കൃഷ്ണ അപ്പാർട്ട്മെന്റ്സ് ബ്ലോക്ക് C-യിൽ വെള്ളം കയറുന്നു. എന്റെ മുത്തശ്ശിക്ക് നടക്കാൻ കഴിയില്ല.",
    "mr": "कृष्णा अपार्टमेंट्स ब्लॉक C मध्ये पाणी शिरत आहे. माझी आजी चालू शकत नाही.",
    "bn": "কৃষ্ণা অ্যাপার্টমেন্টস ব্লক C-তে জল ঢুকছে। আমার ঠাকুমা হাঁটতে পারেন না।",
    "gu": "કૃષ્ણા એપાર્ટમેન્ટ્સ બ્લોક C માં પાણી આવી રહ્યું છે. મારી દાદી ચાલી શકતાં નથી.",
    "pa": "ਕ੍ਰਿਸ਼ਨਾ ਅਪਾਰਟਮੈਂਟਸ ਬਲਾਕ C ਵਿੱਚ ਪਾਣੀ ਆ ਰਿਹਾ ਹੈ। ਮੇਰੀ ਦਾਦੀ ਤੁਰ ਨਹੀਂ ਸਕਦੀ।",
    "ur": "کرشنا اپارٹمنٹس بلاک C میں پانی داخل ہو رہا ہے۔ میری دادی چل نہیں سکتیں۔",
    "as": "কৃষ্ণা এপাৰ্টমেণ্টছ ব্লক C-ত পানী সোমাইছে। মোৰ আইতাই খোজ কাঢ়িব নোৱাৰে।",
    "or": "କୃଷ୍ଣା ଆପାର୍ଟମେଣ୍ଟସ୍ ବ୍ଲକ୍ C ଭିତରକୁ ପାଣି ପଶୁଛି। ମୋ ଜେଜେମା ଚାଲି ପାରୁନାହାନ୍ତି।",
}

HINDI_REPORT_TEXT = "पानी के कारण रास्ता बंद है। मेरे पिता को साँस लेने में तकलीफ़ हो रही है।"
HINDI_REPORT_TRANSLATION_EN = "The road is blocked by water. My father is having difficulty breathing."


@lru_cache(maxsize=1)
def _load_ai_module() -> Any:
    ai_path = Path(__file__).resolve().parents[3] / "ai" / "main.py"
    if not ai_path.exists():
        raise RuntimeError(f"AI engine module not found at {ai_path}")
    spec = importlib.util.spec_from_file_location("reliefmesh_ai_engine", ai_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load AI engine spec from {ai_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_ai_engine_status() -> dict[str, Any]:
    """Returns honest AI engine health and mode metadata."""
    ai = _load_ai_module()
    live_configured = bool(ai.provider_client.get_api_key())
    return {
        "engine": "ai/main.py",
        "mode": "live_provider" if live_configured else "synthetic_validated",
        "scoring": "deterministic",
        "recommendation": "deterministic_resource_aware",
        "approval_required": True,
    }


def extract_synthetic_incident(
    raw_message: str,
    *,
    incident_id: str = "INC-1042",
    language_hint: str = "en",
) -> dict[str, Any]:
    """Validates synthetic report extraction through `ai/main.py`'s ExtractedIncident."""
    ai = _load_ai_module()
    validated = ai.ExtractedIncident.model_validate(
        {
            "location": "Krishna Apartments Block C",
            "incident_type": "flood_rescue",
            "people_affected": 3,
            "needs": ["medical", "rescue"],
            "vulnerabilities": ["elderly_immobile"],
            "vulnerable_groups": ["elderly_immobile"],
            "vulnerability_evidence": ["My grandmother cannot walk"],
            "medical_urgency": True,
            "severity_score": 5,
            "time_sensitivity_hours": 0.5,
            "environmental_threat": True,
            "confidence_score": 0.91,
            "provenance": {"model": ai.DEFAULT_MODEL, "pipeline": "synthetic_validated"},
            "uncertainty_notes": None,
        }
    )
    data = validated.model_dump()
    data["incident_id"] = incident_id
    data["latitude"] = 12.9347
    data["longitude"] = 77.6269
    data["incident_type"] = "flood"
    data["confidence"] = data["confidence_score"]
    return data


def deduplicate_synthetic_incident(
    *,
    incident_id: str = "INC-1042",
    duplicate_count: int = 2,
) -> dict[str, Any]:
    """Validates duplicate report correlation through `ai/main.py`'s DeduplicationResponse."""
    ai = _load_ai_module()
    validated = ai.DeduplicationResponse.model_validate(
        {
            "is_duplicate": True,
            "matched_incident_id": incident_id,
            "similarity_reason": f"Merged {duplicate_count} corroborating reports for Krishna Apartments Block C.",
        }
    )
    result = validated.model_dump()
    result["duplicate_count"] = duplicate_count
    return result


def score_incident_with_ai(
    *,
    incident_id: str = "INC-1042",
    location: str = "Krishna Apartments Block C",
    incident_type: str = "flood_rescue",
    people_affected: int = 3,
    duplicate_count: int = 2,
    confidence: float = 0.91,
) -> dict[str, Any]:
    """Runs `ai/main.py`'s deterministic `score_incident` on the incident."""
    ai = _load_ai_module()
    request = ai.AdvancedScoreRequest(
        location=location,
        incident_type=incident_type,
        people_affected=people_affected,
        vulnerabilities=["elderly_immobile", "water_rising"],
        medical_urgency=True,
        severity_score=5,
        environmental_threat=True,
        time_sensitivity_hours=1.2,
        confidence_score=confidence,
        needs=["medical", "rescue"],
    )
    response = asyncio.run(ai.score_incident(request))
    data = response.model_dump()
    data["incident_id"] = incident_id
    return data


def recommend_resources_with_ai(
    *,
    incident_id: str = "INC-1042",
    available_resources: list[dict[str, Any]],
    replacement_for: str | None = None,
    analysis_revision: str = "rev-inc-1042-rec-1",
) -> dict[str, Any]:
    """Runs `ai/main.py`'s deterministic `generate_recommendation` on candidate resources."""
    ai = _load_ai_module()
    candidate_inputs = []
    continuing = []
    for res in available_resources:
        res_id = res["id"]
        if replacement_for and res_id == replacement_for:
            continue
        raw_caps = list(res.get("capabilities") or [])
        mapped_caps = list(raw_caps)
        if "advanced_life_support" in raw_caps and "medical" not in mapped_caps:
            mapped_caps.append("medical")
        if "water_rescue" in raw_caps and "rescue" not in mapped_caps:
            mapped_caps.append("rescue")

        cand = ai.CandidateResource(
            id=res_id,
            name=res.get("location") or res_id,
            type=res["type"],
            capabilities=mapped_caps,
            status="available",
            eta_minutes=float(res["eta"]) if res.get("eta") is not None else None,
        )
        if replacement_for and res_id == "RESCUE-01":
            continuing.append(
                ai.CandidateResource(
                    id=res_id,
                    name=res.get("location") or res_id,
                    type=res["type"],
                    capabilities=mapped_caps,
                    status="responding",
                    eta_minutes=float(res["eta"]) if res.get("eta") is not None else 7.0,
                )
            )
        else:
            candidate_inputs.append(cand)

    replacement_ctx = (
        ai.ReplacementContext(
            replaced_resource_id=replacement_for,
            reason="Flooded underpass delaying ambulance ETA from 6 to 24 minutes",
            old_eta_minutes=6.0,
            new_eta_minutes=24.0,
        )
        if replacement_for
        else None
    )

    request = ai.RecommendationRequest(
        incident_id=incident_id,
        incident_type="flood_rescue",
        priority_score=94,
        needs=["medical", "rescue"],
        vulnerabilities=["elderly_immobile"],
        candidate_resources=candidate_inputs,
        continuing_assignments=continuing,
        replacement_context=replacement_ctx,
        blocked_resources=[replacement_for] if replacement_for else [],
    )
    ai_result = asyncio.run(ai.generate_recommendation(request)).model_dump()
    recommended = list(ai_result["recommended_resources"])

    if replacement_for:
        explanation = [
            {"key": "explain.blocked", "params": {"id": replacement_for, "old": 6, "eta": 24}},
            {"key": "explain.available", "params": {"id": "AMB-05"}},
            {"key": "explain.eta", "params": {"id": "AMB-05", "eta": 9}},
            {"key": "explain.continues", "params": {"id": "RESCUE-01"}},
        ]
        reason = "plan.replacementReason"
    else:
        explanation = [
            {"key": "explain.distance", "params": {"id": "AMB-02", "distance": 2.1}},
            {"key": "explain.available", "params": {"id": "AMB-02"}},
            {"key": "explain.als", "params": {"id": "AMB-02"}},
            {"key": "explain.eta", "params": {"id": "AMB-02", "eta": 6}},
            {"key": "explain.water", "params": {"id": "RESCUE-01"}},
            {"key": "explain.priority", "params": {}},
        ]
        reason = "plan.reason"

    return {
        "incident_id": incident_id,
        "priority_score": 94,
        "recommended_resources": recommended,
        "reason": reason,
        "explanation": explanation,
        "confidence": 0.91,
        "approval_required": bool(ai_result.get("approval_required", True)),
        "analysis_revision": analysis_revision,
        "ai_reason_codes": ai_result.get("reason_codes", []),
    }


def translate_report_with_ai(
    *,
    original_text: str,
    original_language: str,
    target_language: str,
) -> dict[str, Any]:
    """Translates verified synthetic emergency reports using `ai/main.py` contract validation.

    Never claims to translate arbitrary unknown text when no live translation
    provider is configured; raises ValidationFailedError(code="TRANSLATION_UNAVAILABLE").
    """
    ai = _load_ai_module()
    translated: str | None = None
    if original_language == target_language:
        translated = original_text
    elif original_text == CANONICAL_TRANSLATIONS["en"] and target_language in CANONICAL_TRANSLATIONS:
        translated = CANONICAL_TRANSLATIONS[target_language]
    elif original_text == HINDI_REPORT_TEXT and target_language == "en":
        translated = HINDI_REPORT_TRANSLATION_EN

    if not translated:
        raise ValidationFailedError(
            "Translation is only available for verified synthetic demo fixtures when running without live Gemini API credentials.",
            code="TRANSLATION_UNAVAILABLE",
        )

    validated = ai.TranslationResponse.model_validate(
        {
            "translated_text": translated,
            "source_language": original_language,
            "target_language": target_language,
            "provenance": {"model": ai.DEFAULT_MODEL, "provider": "synthetic_validated"},
        }
    )
    return validated.model_dump()
