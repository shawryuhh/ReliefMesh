# ReliefMesh AI/ML Engine 🧠
Lead AI/ML Engineer & Maintainer: Arkin Sharma
Service Port: 8001
Microservice Architecture: Independent stateless intelligence layer (FastAPI, Pydantic, Gemini).

---

## 🎯 Architectural Mission & Boundaries
The ReliefMesh AI Engine is an emergency response intelligence microservice operating on port 8001. It solves the core bottlenecks in disaster dispatch:
1. Unstructured Data Ingestion: Multilingual emergency report extraction into structured operational data schemas.
2. Deterministic Priority Scoring: Pure-math reproducible scoring (0–100) guaranteeing safety, predictability, and verifiable triage.
3. Candidate-Aware Resource Recommendation: Intelligent matching of incident needs to available resources, supporting initial dispatch and real-time obstacle replacement plans.
4. Semantic Deduplication: Cross-lingual event deduplication preventing redundant dispatches.
5. Multilingual Translation: High-fidelity crisis translation across 13 major Indian and global languages.

### 🛡️ System Boundaries
- AI Thinks, Backend Decides: The AI service does NOT own operational state, does NOT assign recommendation version numbers, and does NOT perform dispatches or mutate database models.
- Human-in-the-loop Dispatch Safety: All recommendation outputs flag approval_required: true.
- Credential Hygiene: API keys (GOOGLE_API_KEY, GEMINI_API_KEY) are loaded intentionally from .env and are strictly excluded from logs and external responses.

---

## 📡 API Contract Specification

### 1. Hardened Health Check
GET /ai/health
Distinguishes between service execution, key presence, and actual provider reachability.

### 2. Structured Incident Extraction
POST /ai/extract-incident
Extracts structured crisis entities from raw multilingual text with vocabulary normalization and evidence preservation.

### 3. Deterministic Priority Scoring
POST /ai/score-incident
Computes an objective, reproducible triage score between 0 and 100. Canonical scenario yields priority = 94.

### 4. Candidate-Aware Resource Recommendation
POST /ai/recommendation
Produces a full desired plan using only supplied candidates and continuing responders.
Initial: AMB-02 + RESCUE-01
Replacement: AMB-05 + RESCUE-01 (when AMB-02 is blocked).

### 5. Semantic Deduplication
POST /ai/deduplicate-incident
Compares new unstructured reports against active incidents across languages. Validates matched IDs.

### 6. Multilingual Translation
POST /ai/translate-report
Translates emergency reports across 13 ReliefMesh languages without altering original source text.

---

## 🧪 Testing & Verification
Comprehensive 23-test suite covering health, extraction, scoring (94), candidate recommendations, replacements, deduplication, translation, and error sanitization.
Run tests:
python3 run_tests.py
# or
python3 -m unittest test_main.py
