"""
ReliefMesh AI/ML Engine - Global & Pan-India Multilingual Intelligence Layer
Port: 8001
Lead AI/ML Maintainer: Arkin Sharma
"""

import os
import math
import asyncio
import json
import logging
from typing import List, Optional, Dict, Any, Union, Set
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("reliefmesh_ai")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ==========================================
# 0. CONFIGURATION
# ==========================================
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SERVICE_PORT = int(os.getenv("AI_SERVICE_PORT", "8001"))
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "5.0"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "1"))

app = FastAPI(
    title="ReliefMesh AI/ML Engine - Global & Pan-India Multilingual Intelligence Layer",
    version="2.0.0",
    description="Deterministic Priority Scoring, Candidate-Aware Recommendations, Multilingual Extraction, Translation, and Semantic Deduplication."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base model with backward & forward compatibility for Pydantic v1 & v2
class SafeBaseModel(BaseModel):
    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        if hasattr(super(), "model_dump"):
            return super().model_dump(*args, **kwargs)
        return super().dict(*args, **kwargs)


# ==========================================
# VOCABULARY & TAXONOMY ALIGNMENT
# ==========================================
NORMALIZED_INCIDENT_TYPES = {
    "flood": "flood_rescue",
    "flood_rescue": "flood_rescue",
    "water_rescue": "flood_rescue",
    "drowning": "flood_rescue",
    "building_collapse": "building_collapse",
    "collapse": "building_collapse",
    "structural_collapse": "building_collapse",
    "medical": "medical",
    "medical_emergency": "medical",
    "injury": "medical",
    "fire": "fire",
    "active_fire": "fire",
    "wildfire": "fire",
    "supply": "supplies",
    "supplies": "supplies",
    "food_water": "supplies",
    "food": "supplies",
    "water": "supplies",
    "hazmat": "hazmat_leak",
    "hazmat_leak": "hazmat_leak",
    "chemical_leak": "hazmat_leak",
    "dam_breach": "dam_breach",
}

CRITICAL_INCIDENT_TYPES: Set[str] = {
    "building_collapse",
    "dam_breach",
    "active_fire",
    "fire",
    "hazmat_leak"
}

SUPPORTED_RELIEFMESH_LANGUAGES: Set[str] = {
    "english", "hindi", "kannada", "tamil", "telugu",
    "malayalam", "marathi", "bengali", "gujarati",
    "punjabi", "urdu", "assamese", "odia"
}

def normalize_incident_type(val: str) -> str:
    cleaned = (val or "").strip().lower().replace("-", "_").replace(" ", "_")
    return NORMALIZED_INCIDENT_TYPES.get(cleaned, cleaned or "other")

def normalize_vulnerabilities_and_evidence(
    text: str,
    raw_vulnerabilities: Optional[List[str]] = None
) -> (List[str], List[str]):
    vulnerabilities = set()
    evidence = []

    text_lower = (text or "").lower()

    if raw_vulnerabilities:
        for v in raw_vulnerabilities:
            v_clean = v.strip().lower()
            if v_clean in ("elderly", "grandmother", "grandfather", "senior", "aged"):
                vulnerabilities.add("elderly")
            elif v_clean in ("limited_mobility", "cannot_walk", "mobility_impaired", "wheelchair", "bedridden"):
                vulnerabilities.add("limited_mobility")
            elif v_clean in ("children", "child", "infant", "toddler", "baby"):
                vulnerabilities.add("children")
            elif v_clean in ("pregnant", "pregnancy"):
                vulnerabilities.add("pregnant")
            elif v_clean in ("disabled", "disability"):
                vulnerabilities.add("disabled")
            else:
                vulnerabilities.add(v_clean)

    if any(k in text_lower for k in ["grandmother", "dadi", "nani", "grandfather", "elderly", "old age", "senior citizen", "80-year-old", "70-year-old"]):
        vulnerabilities.add("elderly")
        if "grandmother" in text_lower:
            evidence.append("grandmother")
        elif "grandfather" in text_lower:
            evidence.append("grandfather")
        else:
            evidence.append("elderly")

    if any(k in text_lower for k in ["cannot walk", "can't walk", "unable to walk", "immobile", "wheelchair", "bedridden", "paralyzed"]):
        vulnerabilities.add("limited_mobility")
        if "cannot walk" in text_lower or "can't walk" in text_lower:
            evidence.append("cannot walk")
        else:
            evidence.append("limited mobility")

    if any(k in text_lower for k in ["child", "children", "baby", "infant", "toddler", "kid", "kids"]):
        vulnerabilities.add("children")
        evidence.append("children")

    if any(k in text_lower for k in ["pregnant", "expecting"]):
        vulnerabilities.add("pregnant")
        evidence.append("pregnant")

    unique_vulns = sorted(list(vulnerabilities))
    unique_evidence = sorted(list(set(evidence)))
    return unique_vulns, unique_evidence


# ==========================================
# PROVIDER ABSTRACTION & LIVE / TEST HOOKS
# ==========================================
class ProviderClient:
    def __init__(self):
        self._mock_extractor = None
        self._mock_deduplicator = None
        self._mock_translator = None
        self._mock_reachable: Optional[bool] = None

    def set_mock_extractor(self, func):
        self._mock_extractor = func

    def set_mock_deduplicator(self, func):
        self._mock_deduplicator = func

    def set_mock_translator(self, func):
        self._mock_translator = func

    def set_mock_reachable(self, val: Optional[bool]):
        self._mock_reachable = val

    def get_api_key(self) -> Optional[str]:
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    async def ping_provider(self) -> bool:
        if self._mock_reachable is not None:
            return self._mock_reachable

        api_key = self.get_api_key()
        if not api_key:
            return False

        try:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model=DEFAULT_MODEL,
                    temperature=0,
                    max_retries=AI_MAX_RETRIES,
                    google_api_key=api_key
                )
                response = await asyncio.wait_for(llm.ainvoke("ping"), timeout=AI_TIMEOUT_SECONDS)
                return bool(response and response.content)
            except ImportError:
                import httpx
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_MODEL}:generateContent"
                payload = {"contents": [{"parts": [{"text": "ping"}]}]}
                headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    return resp.status_code == 200
        except Exception as e:
            logger.warning("Provider ping failed: %s", type(e).__name__)
            return False

    async def extract_incident_llm(self, text: str) -> Dict[str, Any]:
        if self._mock_extractor:
            return await self._mock_extractor(text)

        api_key = self.get_api_key()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Provider API key is not configured. Extraction requires live AI credentials."
            )

        system_instruction = (
            "You are an expert emergency crisis dispatcher AI. Extract structured incident data from unstructured emergency reports. "
            "You are fully fluent in English, regional Hinglish, Gen Z slang/shorthand, major Indian regional languages, "
            "and major global languages. Translate and normalize all extracted details accurately into standard English JSON.\n"
            "Return valid JSON with keys: location, incident_type, people_affected, needs, vulnerabilities, vulnerability_evidence, "
            "medical_urgency, severity_score, time_sensitivity_hours, environmental_threat, confidence_score, uncertainty_notes."
        )

        try:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                from langchain_core.prompts import ChatPromptTemplate
                llm = ChatGoogleGenerativeAI(
                    model=DEFAULT_MODEL,
                    temperature=0,
                    max_retries=AI_MAX_RETRIES,
                    google_api_key=api_key
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_instruction),
                    ("human", "{text}")
                ])
                chain = prompt | llm
                response = await asyncio.wait_for(chain.ainvoke({"text": text}), timeout=AI_TIMEOUT_SECONDS)
                raw_content = response.content if hasattr(response, "content") else str(response)
                cleaned_json = raw_content.strip()
                if cleaned_json.startswith("```json"):
                    cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
                elif cleaned_json.startswith("```"):
                    cleaned_json = cleaned_json.split("```")[1].split("```")[0].strip()
                return json.loads(cleaned_json)
            except ImportError:
                import httpx
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_MODEL}:generateContent"
                payload = {
                    "contents": [{"parts": [{"text": f"{system_instruction}\n\nReport:\n{text}"}]}],
                    "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
                }
                headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code != 200:
                        raise RuntimeError(f"Provider returned status {resp.status_code}")
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(raw_text)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Extraction provider timed out.")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Extraction provider error: {type(e).__name__}")

    async def deduplicate_llm(self, new_report: str, active_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self._mock_deduplicator:
            return await self._mock_deduplicator(new_report, active_incidents)

        api_key = self.get_api_key()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Provider API key is not configured. Deduplication requires live AI credentials."
            )

        system_instruction = (
            "You are an expert crisis data deduplication engine. Compare a new emergency report against a list of active incidents. "
            "Determine if the new report describes the exact same physical event/emergency. "
            "Reports may be in any language or script. Output valid JSON with keys: is_duplicate (boolean), "
            "matched_incident_id (string or null), similarity_reason (string)."
        )

        try:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                from langchain_core.prompts import ChatPromptTemplate
                llm = ChatGoogleGenerativeAI(
                    model=DEFAULT_MODEL,
                    temperature=0,
                    max_retries=AI_MAX_RETRIES,
                    google_api_key=api_key
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_instruction),
                    ("human", "New Report:\n{new_report}\n\nActive Incidents List:\n{active_list}")
                ])
                chain = prompt | llm
                response = await asyncio.wait_for(
                    chain.ainvoke({"new_report": new_report, "active_list": json.dumps(active_incidents)}),
                    timeout=AI_TIMEOUT_SECONDS
                )
                raw_content = response.content if hasattr(response, "content") else str(response)
                cleaned = raw_content.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1].split("```")[0].strip()
                return json.loads(cleaned)
            except ImportError:
                import httpx
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_MODEL}:generateContent"
                payload = {
                    "contents": [{"parts": [{"text": f"{system_instruction}\n\nNew Report:\n{new_report}\n\nActive Incidents:\n{json.dumps(active_incidents)}"}]}],
                    "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
                }
                headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code != 200:
                        raise RuntimeError(f"Provider returned status {resp.status_code}")
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(raw_text)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Deduplication provider timed out.")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Deduplication provider error: {type(e).__name__}")

    async def translate_llm(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        if self._mock_translator:
            return await self._mock_translator(text, source_lang, target_lang)

        api_key = self.get_api_key()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Provider API key is not configured. Translation requires live AI credentials."
            )

        prompt_str = (
            f"You are a professional crisis translator. Translate the following emergency report from "
            f"{source_lang or 'detected language'} into {target_lang}. Preserve all critical emergency facts, "
            f"counts, addresses, and medical details without omissions. Output only the translated text.\n\n"
            f"Text:\n{text}"
        )

        try:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model=DEFAULT_MODEL,
                    temperature=0,
                    max_retries=AI_MAX_RETRIES,
                    google_api_key=api_key
                )
                response = await asyncio.wait_for(llm.ainvoke(prompt_str), timeout=AI_TIMEOUT_SECONDS)
                return (response.content if hasattr(response, "content") else str(response)).strip()
            except ImportError:
                import httpx
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_MODEL}:generateContent"
                payload = {"contents": [{"parts": [{"text": prompt_str}]}], "generationConfig": {"temperature": 0.0}}
                headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code != 200:
                        raise RuntimeError(f"Provider returned status {resp.status_code}")
                    data = resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except asyncio.TimeoutError:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Translation provider timed out.")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Translation provider error: {type(e).__name__}")

provider_client = ProviderClient()


# ==========================================
# 1. CONFIGURATION / HARDENED HEALTH DIAGNOSTICS
# ==========================================
@app.get("/ai/health")
async def health_check():
    api_key_configured = bool(provider_client.get_api_key())
    provider_reachable = False
    smoke_result = "skipped: credentials not configured"

    if api_key_configured:
        reachable = await provider_client.ping_provider()
        provider_reachable = reachable
        smoke_result = "passed" if reachable else "failed: provider unreachable or timeout"

    status_str = "healthy" if (api_key_configured and provider_reachable) else "degraded"

    return {
        "status": status_str,
        "service": "ReliefMesh AI Engine",
        "port": SERVICE_PORT,
        "model": DEFAULT_MODEL,
        "api_key_configured": api_key_configured,
        "provider_reachable": provider_reachable,
        "smoke_test": {
            "executed": api_key_configured,
            "result": smoke_result
        }
    }


# ==========================================
# 2. HARDENED EXTRACTION CONTRACT
# ==========================================
class ReportRequest(SafeBaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Raw unstructured emergency report text")

class ExtractedIncident(SafeBaseModel):
    location: str = Field(..., max_length=500, description="Extracted geographic location or address")
    incident_type: str = Field(..., description="Normalized incident type, e.g. flood_rescue, building_collapse, medical, fire, supplies")
    people_affected: int = Field(ge=0, description="Estimated count of people needing assistance")
    needs: List[str] = Field(default_factory=list, description="Operational needs, e.g. ['medical', 'rescue', 'supplies']")
    vulnerabilities: List[str] = Field(default_factory=list, description="Unique normalized vulnerability codes")
    vulnerable_groups: List[str] = Field(default_factory=list, description="Backward-compatible alias of vulnerabilities")
    vulnerability_evidence: List[str] = Field(default_factory=list, description="Direct textual evidence for identified vulnerabilities")
    medical_urgency: bool = Field(description="True if medical assistance is explicitly required")
    severity_score: int = Field(ge=1, le=5, description="Severity score from 1 (low) to 5 (critical)")
    time_sensitivity_hours: float = Field(ge=0.0, description="Estimated hours before condition deteriorates")
    environmental_threat: bool = Field(description="True if active fire, rapid flooding, or collapse is occurring")
    confidence_score: float = Field(ge=0.0, le=1.0, description="AI extraction confidence score between 0.0 and 1.0")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Metadata regarding extraction model and method")
    uncertainty_notes: Optional[str] = Field(None, description="Explicit notes distinguishing confirmed facts from estimates")

    @validator("severity_score")
    def validate_severity(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("severity_score must be between 1 and 5 inclusive")
        return v

    @validator("confidence_score")
    def validate_confidence(cls, v):
        if not math.isfinite(v) or not (0.0 <= v <= 1.0):
            raise ValueError("confidence_score must be a finite float between 0.0 and 1.0")
        return v

    @validator("time_sensitivity_hours")
    def validate_time(cls, v):
        if not math.isfinite(v) or v < 0.0:
            raise ValueError("time_sensitivity_hours must be a non-negative finite float")
        return v

@app.post("/ai/extract-incident", response_model=ExtractedIncident)
async def extract_incident(report: ReportRequest):
    raw_text = report.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Report text cannot be empty.")

    try:
        raw_data = await provider_client.extract_incident_llm(raw_text)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Extraction error: %s", type(e).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Extraction provider error: {type(e).__name__}")

    raw_type = raw_data.get("incident_type", "other")
    normalized_type = normalize_incident_type(raw_type)

    raw_vulns = raw_data.get("vulnerabilities") or raw_data.get("vulnerable_groups") or []
    norm_vulns, norm_evidence = normalize_vulnerabilities_and_evidence(raw_text, raw_vulns)

    raw_needs = raw_data.get("needs") or []
    normalized_needs = set()
    for n in raw_needs:
        n_clean = n.strip().lower()
        if n_clean in ("supply", "supplies", "food", "water"):
            normalized_needs.add("supplies")
        elif n_clean in ("medical", "ambulance", "doctor", "medicine"):
            normalized_needs.add("medical")
        elif n_clean in ("rescue", "flood_rescue", "evacuation", "boat"):
            normalized_needs.add("rescue")
        else:
            normalized_needs.add(n_clean)

    if raw_data.get("medical_urgency", False):
        normalized_needs.add("medical")
    if normalized_type in ("flood_rescue", "building_collapse"):
        normalized_needs.add("rescue")

    severity = int(raw_data.get("severity_score", 3))
    severity = max(1, min(5, severity))

    confidence = float(raw_data.get("confidence_score", 0.85))
    confidence = max(0.0, min(1.0, confidence)) if math.isfinite(confidence) else 0.85

    time_hours = float(raw_data.get("time_sensitivity_hours", 2.0))
    time_hours = max(0.0, time_hours) if math.isfinite(time_hours) else 2.0

    people_count = int(raw_data.get("people_affected", 1))
    people_count = max(0, people_count)

    provenance_info = {
        "model": DEFAULT_MODEL,
        "pipeline": "structured_extraction",
        "raw_text_length": len(raw_text)
    }

    return ExtractedIncident(
        location=str(raw_data.get("location", "Unknown Location")),
        incident_type=normalized_type,
        people_affected=people_count,
        needs=sorted(list(normalized_needs)),
        vulnerabilities=norm_vulns,
        vulnerable_groups=norm_vulns,
        vulnerability_evidence=norm_evidence,
        medical_urgency=bool(raw_data.get("medical_urgency", False)),
        severity_score=severity,
        time_sensitivity_hours=time_hours,
        environmental_threat=bool(raw_data.get("environmental_threat", False)),
        confidence_score=confidence,
        provenance=provenance_info,
        uncertainty_notes=raw_data.get("uncertainty_notes", "Casualty and time estimates derived from unstructured report text.")
    )


# ==========================================
# 4. DETERMINISTIC PRIORITY SCORING
# ==========================================
class AdvancedScoreRequest(SafeBaseModel):
    location: str = Field(default="Unknown")
    incident_type: str = Field(...)
    people_affected: int = Field(ge=0)
    vulnerabilities: Optional[List[str]] = Field(default=None)
    vulnerable_groups: Optional[List[str]] = Field(default=None)
    medical_urgency: bool = Field(...)
    severity_score: int = Field(ge=1, le=5)
    environmental_threat: bool = Field(...)
    time_sensitivity_hours: float = Field(ge=0.0)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    needs: Optional[List[str]] = Field(default=None)

    @validator("severity_score")
    def check_severity(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("severity_score must be between 1 and 5")
        return v

    @validator("confidence_score")
    def check_confidence(cls, v):
        if not math.isfinite(v) or not (0.0 <= v <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        return v

class ScoringBreakdown(SafeBaseModel):
    severity_points: float
    medical_points: float
    vulnerable_points: float
    env_points: float
    time_points: float
    scale_points: float
    confidence_score: float
    critical_type_override: bool

class AdvancedPriorityResponse(SafeBaseModel):
    priority_score: int = Field(ge=0, le=100)
    risk_level: str
    requires_human_review: bool
    scoring_breakdown: ScoringBreakdown

@app.post("/ai/score-incident", response_model=AdvancedPriorityResponse)
async def score_incident(incident: AdvancedScoreRequest):
    severity_points = (incident.severity_score / 5.0) * 35.0
    medical_points = 25.0 if incident.medical_urgency else 0.0

    vuln_set = set()
    if incident.vulnerabilities:
        vuln_set.update(incident.vulnerabilities)
    if incident.vulnerable_groups:
        vuln_set.update(incident.vulnerable_groups)
    vulnerable_points = min(len(vuln_set) * 7.5, 15.0)

    env_points = 10.0 if incident.environmental_threat else 0.0
    decay_val = math.exp(-0.35 * max(0.0, incident.time_sensitivity_hours))
    time_points = round(10.0 * decay_val, 1)
    time_points = max(time_points, 1.0)

    if incident.people_affected > 1:
        scale_points = min(round(math.log10(incident.people_affected) * 5.0, 1), 10.0)
    else:
        scale_points = 0.0

    raw_total = severity_points + medical_points + vulnerable_points + env_points + time_points + scale_points

    norm_type = normalize_incident_type(incident.incident_type)
    is_critical_type = norm_type in CRITICAL_INCIDENT_TYPES

    if is_critical_type:
        score_before_penalty = max(raw_total, 85.0)
    else:
        score_before_penalty = raw_total

    if incident.confidence_score < 0.6:
        score_after_penalty = score_before_penalty * 0.85
    else:
        score_after_penalty = score_before_penalty

    final_score = int(round(min(max(score_after_penalty, 0.0), 100.0)))
    requires_review = incident.confidence_score < 0.75

    if final_score >= 80:
        risk_level = "Critical"
    elif final_score >= 60:
        risk_level = "High"
    elif final_score >= 40:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return AdvancedPriorityResponse(
        priority_score=final_score,
        risk_level=risk_level,
        requires_human_review=requires_review,
        scoring_breakdown=ScoringBreakdown(
            severity_points=round(severity_points, 1),
            medical_points=medical_points,
            vulnerable_points=round(vulnerable_points, 1),
            env_points=env_points,
            time_points=time_points,
            scale_points=scale_points,
            confidence_score=incident.confidence_score,
            critical_type_override=is_critical_type
        )
    )


# ==========================================
# 5. RESOURCE-AWARE RECOMMENDATION ENGINE
# ==========================================
class CandidateResource(SafeBaseModel):
    id: str = Field(..., description="Unique resource identifier, e.g. AMB-02")
    name: Optional[str] = Field(None, description="Optional name of the resource")
    type: Optional[str] = Field(None, description="Resource type, e.g. ambulance, rescue_boat")
    capabilities: List[str] = Field(default_factory=list, description="Capabilities, e.g. ['medical', 'transport', 'triage']")
    status: Optional[str] = Field("available", description="Operational status, e.g. available, responding, delayed")
    eta_minutes: Optional[float] = Field(None, description="Estimated time of arrival in minutes")

class ReplacementContext(SafeBaseModel):
    replaced_resource_id: Optional[str] = Field(None, description="Resource ID that requires replacement")
    reason: Optional[str] = Field(None, description="Reason for replacement, e.g. obstruction delay")
    old_eta_minutes: Optional[float] = None
    new_eta_minutes: Optional[float] = None

class RecommendationRequest(SafeBaseModel):
    incident_id: Optional[str] = Field("INC-1042", description="Incident ID")
    incident_type: Optional[str] = Field(None, description="Type of incident")
    priority_score: Optional[int] = Field(None, ge=0, le=100, description="Priority score")
    needs: List[str] = Field(default_factory=list, description="Operational needs, e.g. ['medical', 'rescue']")
    vulnerabilities: Optional[List[str]] = Field(default_factory=list)
    candidate_resources: List[CandidateResource] = Field(default_factory=list, description="Available candidate resources")
    continuing_assignments: Optional[List[Any]] = Field(default_factory=list, description="Continuing responders (IDs or objects)")
    replacement_context: Optional[ReplacementContext] = Field(None, description="Context for replacement recommendation")
    blocked_resources: Optional[List[str]] = Field(default_factory=list, description="Blocked or excluded resource IDs")

class StructuredReason(SafeBaseModel):
    reason_code: str = Field(description="Standardized code: AVAILABLE, CAPABILITY_MATCH, ETA_MINUTES, CONTINUING_ASSIGNMENT, BLOCKED_RESOURCE_EXCLUDED, REQUIRED_COVERAGE, INSUFFICIENT_COVERAGE")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Supporting parameters")

class CoverageResult(SafeBaseModel):
    status: str = Field(description="'satisfied', 'partial', or 'insufficient'")
    covered_needs: List[str] = Field(default_factory=list)
    missing_needs: List[str] = Field(default_factory=list)

class RecommendationResponse(SafeBaseModel):
    incident_id: Optional[str] = None
    recommended_resources: List[str] = Field(description="Full desired set of recommended resource IDs")
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: List[str] = Field(description="High-level reason codes")
    structured_explanations: List[StructuredReason] = Field(description="Global structured explanations")
    resource_reasons: Dict[str, List[StructuredReason]] = Field(description="Resource-specific explanations")
    coverage_result: CoverageResult
    insufficient_coverage: bool = False
    approval_required: bool = True

def capability_matches_need(capabilities: List[str], need: str) -> bool:
    need_clean = need.strip().lower()
    caps_clean = {c.strip().lower() for c in capabilities}

    if need_clean == "medical":
        return bool(caps_clean & {"medical", "ambulance", "triage", "paramedic", "transport"})
    elif need_clean in ("rescue", "flood_rescue"):
        return bool(caps_clean & {"rescue", "flood_rescue", "water_rescue", "evacuation", "boat", "rescue_boat"})
    elif need_clean == "supplies":
        return bool(caps_clean & {"supplies", "food", "water", "supply_transport", "transport"})
    elif need_clean == "fire":
        return bool(caps_clean & {"fire", "firefighting", "extinguish", "water_cannon"})
    elif need_clean == "hazmat":
        return bool(caps_clean & {"hazmat", "hazmat_unit", "decontamination", "chemical_containment"})
    return need_clean in caps_clean

@app.post("/ai/recommendation", response_model=RecommendationResponse)
async def generate_recommendation(payload: RecommendationRequest):
    blocked_set: Set[str] = set(payload.blocked_resources or [])
    if payload.replacement_context and payload.replacement_context.replaced_resource_id:
        blocked_set.add(payload.replacement_context.replaced_resource_id)

    continuing_resources: Dict[str, CandidateResource] = {}
    if payload.continuing_assignments:
        for item in payload.continuing_assignments:
            if isinstance(item, str):
                continuing_resources[item] = CandidateResource(id=item, status="responding")
            elif isinstance(item, dict):
                r_id = item.get("id")
                if r_id:
                    continuing_resources[r_id] = CandidateResource(
                        id=r_id,
                        name=item.get("name"),
                        type=item.get("type"),
                        capabilities=item.get("capabilities", []),
                        status=item.get("status", "responding"),
                        eta_minutes=item.get("eta_minutes")
                    )
            elif hasattr(item, "id"):
                continuing_resources[item.id] = CandidateResource(
                    id=item.id,
                    name=getattr(item, "name", None),
                    type=getattr(item, "type", None),
                    capabilities=getattr(item, "capabilities", []),
                    status=getattr(item, "status", "responding"),
                    eta_minutes=getattr(item, "eta_minutes", None)
                )

    for cand in payload.candidate_resources:
        if cand.id in continuing_resources:
            if not continuing_resources[cand.id].capabilities and cand.capabilities:
                continuing_resources[cand.id].capabilities = cand.capabilities

    required_needs = list(payload.needs or [])
    if not required_needs:
        norm_type = normalize_incident_type(payload.incident_type or "")
        if norm_type == "flood_rescue":
            required_needs = ["medical", "rescue"]
        elif norm_type == "building_collapse":
            required_needs = ["rescue", "medical"]
        elif norm_type == "medical":
            required_needs = ["medical"]
        elif norm_type == "fire":
            required_needs = ["fire", "medical"]
        elif norm_type == "supplies":
            required_needs = ["supplies"]
        else:
            required_needs = ["rescue"]

    covered_needs: Set[str] = set()
    resource_reasons: Dict[str, List[StructuredReason]] = {}
    global_explanations: List[StructuredReason] = []
    global_reason_codes: Set[str] = set()

    for b_id in sorted(list(blocked_set)):
        global_reason_codes.add("BLOCKED_RESOURCE_EXCLUDED")
        reason_params = {"resource_id": b_id}
        if payload.replacement_context and payload.replacement_context.replaced_resource_id == b_id:
            reason_params["reason"] = payload.replacement_context.reason or "obstruction_delay"
            if payload.replacement_context.new_eta_minutes is not None:
                reason_params["new_eta_minutes"] = payload.replacement_context.new_eta_minutes
        else:
            reason_params["reason"] = "blocked_or_excluded"

        exp = StructuredReason(reason_code="BLOCKED_RESOURCE_EXCLUDED", parameters=reason_params)
        global_explanations.append(exp)
        if b_id not in resource_reasons:
            resource_reasons[b_id] = []
        resource_reasons[b_id].append(exp)

    full_desired_plan: List[str] = []
    for c_id, c_res in continuing_resources.items():
        if c_id in blocked_set:
            continue
        full_desired_plan.append(c_id)
        global_reason_codes.add("CONTINUING_ASSIGNMENT")

        c_reasons = [
            StructuredReason(
                reason_code="CONTINUING_ASSIGNMENT",
                parameters={"resource_id": c_id, "status": c_res.status or "responding"}
            )
        ]

        for need in required_needs:
            caps = c_res.capabilities
            if not caps:
                if "RESCUE" in c_id or "BOAT" in c_id:
                    caps = ["rescue", "flood_rescue"]
                elif "AMB" in c_id:
                    caps = ["medical"]

            if capability_matches_need(caps, need):
                covered_needs.add(need)
                global_reason_codes.add("CAPABILITY_MATCH")
                c_reasons.append(
                    StructuredReason(
                        reason_code="CAPABILITY_MATCH",
                        parameters={"need": need, "capabilities": caps}
                    )
                )

        resource_reasons[c_id] = c_reasons

    valid_candidates = []
    for cand in payload.candidate_resources:
        if cand.id in blocked_set:
            continue
        if cand.id in continuing_resources:
            continue
        status_clean = (cand.status or "available").lower()
        if status_clean not in ("available", "ready", "idle"):
            continue
        valid_candidates.append(cand)

    uncovered_needs = [n for n in required_needs if n not in covered_needs]
    selected_candidate_ids = []

    for need in uncovered_needs:
        matching = [c for c in valid_candidates if capability_matches_need(c.capabilities, need)]
        if not matching:
            continue

        matching.sort(key=lambda c: (
            c.eta_minutes if (c.eta_minutes is not None and math.isfinite(c.eta_minutes)) else 9999.0,
            c.id
        ))

        best = matching[0]
        selected_candidate_ids.append(best.id)
        covered_needs.add(need)
        valid_candidates = [c for c in valid_candidates if c.id != best.id]

        global_reason_codes.add("AVAILABLE")
        global_reason_codes.add("CAPABILITY_MATCH")
        b_reasons = [
            StructuredReason(reason_code="AVAILABLE", parameters={"resource_id": best.id, "status": best.status or "available"}),
            StructuredReason(reason_code="CAPABILITY_MATCH", parameters={"resource_id": best.id, "need": need, "capabilities": best.capabilities})
        ]
        if best.eta_minutes is not None:
            global_reason_codes.add("ETA_MINUTES")
            b_reasons.append(
                StructuredReason(reason_code="ETA_MINUTES", parameters={"resource_id": best.id, "eta_minutes": best.eta_minutes})
            )

        resource_reasons[best.id] = b_reasons

    for r_id in selected_candidate_ids:
        if r_id not in full_desired_plan:
            full_desired_plan.append(r_id)

    full_desired_plan.sort()

    missing_needs = [n for n in required_needs if n not in covered_needs]
    insufficient = len(missing_needs) > 0

    if insufficient:
        coverage_status = "insufficient"
        global_reason_codes.add("INSUFFICIENT_COVERAGE")
        global_explanations.append(
            StructuredReason(
                reason_code="INSUFFICIENT_COVERAGE",
                parameters={"missing_needs": missing_needs, "covered_needs": sorted(list(covered_needs))}
            )
        )
        confidence = 0.50
    else:
        coverage_status = "satisfied"
        global_reason_codes.add("REQUIRED_COVERAGE")
        global_explanations.append(
            StructuredReason(
                reason_code="REQUIRED_COVERAGE",
                parameters={"covered_needs": sorted(list(covered_needs)), "status": "satisfied"}
            )
        )
        confidence = 0.95

    return RecommendationResponse(
        incident_id=payload.incident_id or "INC-1042",
        recommended_resources=full_desired_plan,
        confidence=confidence,
        reason_codes=sorted(list(global_reason_codes)),
        structured_explanations=global_explanations,
        resource_reasons=resource_reasons,
        coverage_result=CoverageResult(
            status=coverage_status,
            covered_needs=sorted(list(covered_needs)),
            missing_needs=sorted(missing_needs)
        ),
        insufficient_coverage=insufficient,
        approval_required=True
    )

@app.post("/ai/analyze-incident")
async def analyze_incident_legacy(payload: Optional[Dict[str, Any]] = None):
    if not payload or "candidate_resources" not in payload:
        req = RecommendationRequest(
            incident_id=payload.get("incident_id", "INC-1042") if payload else "INC-1042",
            needs=["medical", "rescue"],
            candidate_resources=[
                CandidateResource(id="AMB-02", capabilities=["medical", "triage", "transport"], status="available", eta_minutes=6.0),
                CandidateResource(id="RESCUE-01", capabilities=["rescue", "flood_rescue", "evacuation"], status="available", eta_minutes=12.0),
                CandidateResource(id="AMB-01", capabilities=["medical"], status="available", eta_minutes=15.0)
            ]
        )
        rec = await generate_recommendation(req)
        return {
            "incident_id": rec.incident_id,
            "priority_score": 94,
            "confidence": rec.confidence,
            "recommended_resources": rec.recommended_resources,
            "reason": "Medical emergency involving a vulnerable person",
            "approval_required": True,
            "coverage_result": rec.coverage_result.model_dump(),
            "reason_codes": rec.reason_codes
        }

    rec = await generate_recommendation(RecommendationRequest(**payload))
    return {
        "incident_id": rec.incident_id,
        "priority_score": payload.get("priority_score", 85),
        "confidence": rec.confidence,
        "recommended_resources": rec.recommended_resources,
        "reason": "Structured resource recommendation based on candidate availability and needs",
        "approval_required": True,
        "coverage_result": rec.coverage_result.model_dump(),
        "reason_codes": rec.reason_codes
    }


# ==========================================
# 9. SEMANTIC DEDUPLICATION ENGINE
# ==========================================
class ActiveIncidentSummary(SafeBaseModel):
    incident_id: str = Field(..., description="Unique ID of active incident")
    location: str = Field(..., description="Location of incident")
    incident_type: str = Field(..., description="Type of incident")
    summary_text: str = Field(..., description="Summary of incident situation")

class DeduplicationRequest(SafeBaseModel):
    new_report_text: str = Field(..., min_length=1, max_length=10000)
    active_incidents: List[ActiveIncidentSummary] = Field(default_factory=list)

class DeduplicationResponse(SafeBaseModel):
    is_duplicate: bool
    matched_incident_id: Optional[str] = Field(None, description="Matched incident ID from active candidates only")
    similarity_reason: str = Field(description="Structured explanation of deduplication decision")

@app.post("/ai/deduplicate-incident", response_model=DeduplicationResponse)
async def deduplicate_incident(payload: DeduplicationRequest):
    if not payload.active_incidents:
        return DeduplicationResponse(
            is_duplicate=False,
            matched_incident_id=None,
            similarity_reason="No active incidents provided to compare against."
        )

    active_dict_list = [inc.model_dump() for inc in payload.active_incidents]
    active_ids: Set[str] = {inc.incident_id for inc in payload.active_incidents}

    try:
        result_data = await provider_client.deduplicate_llm(payload.new_report_text, active_dict_list)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Deduplication error: %s", type(e).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Deduplication provider error: {type(e).__name__}")

    is_dup = bool(result_data.get("is_duplicate", False))
    matched_id = result_data.get("matched_incident_id")
    reason = str(result_data.get("similarity_reason", "Deduplication comparison evaluated."))

    if is_dup:
        if not matched_id or matched_id not in active_ids:
            logger.warning("Deduplication model hallucinated or returned invalid ID: %s", matched_id)
            is_dup = False
            matched_id = None
            reason = "Model suggested duplicate but returned an invalid incident ID not in active candidates."
    else:
        matched_id = None

    return DeduplicationResponse(
        is_duplicate=is_dup,
        matched_incident_id=matched_id,
        similarity_reason=reason
    )


# ==========================================
# 10. MULTILINGUAL TRANSLATION SERVICE
# ==========================================
class TranslationRequest(SafeBaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Emergency report text to translate")
    source_language: Optional[str] = Field("auto", description="Source language if known or 'auto'")
    target_language: str = Field(..., description="Target ReliefMesh language, e.g. English, Hindi, Tamil")

class TranslationResponse(SafeBaseModel):
    translated_text: str = Field(description="Translated emergency report text")
    source_language: str = Field(description="Detected or provided source language")
    target_language: str = Field(description="Target language")
    provenance: Dict[str, Any] = Field(description="Model provenance metadata")

@app.post("/ai/translate-report", response_model=TranslationResponse)
async def translate_report(payload: TranslationRequest):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text to translate cannot be empty.")

    target_clean = payload.target_language.strip().lower()
    if target_clean not in SUPPORTED_RELIEFMESH_LANGUAGES:
        supported_list = ", ".join(sorted(list(SUPPORTED_RELIEFMESH_LANGUAGES)))
        raise HTTPException(
            status_code=400,
            detail=f"Target language '{payload.target_language}' is not supported. Supported languages: {supported_list}"
        )

    source_clean = (payload.source_language or "auto").strip().lower()

    if source_clean == target_clean:
        return TranslationResponse(
            translated_text=text,
            source_language=payload.source_language or "unknown",
            target_language=payload.target_language,
            provenance={"model": "identity_passthrough", "provider": "local"}
        )

    try:
        translated = await provider_client.translate_llm(text, source_clean, payload.target_language)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Translation error: %s", type(e).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Translation provider error: {type(e).__name__}")

    return TranslationResponse(
        translated_text=translated,
        source_language=payload.source_language or "detected",
        target_language=payload.target_language,
        provenance={"model": DEFAULT_MODEL, "provider": "google-gemini"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=SERVICE_PORT, reload=True)
