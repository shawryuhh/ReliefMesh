import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

"""
Comprehensive Test Suite for ReliefMesh AI/ML Engine
Validates all requirements from the integration handoff.
"""

import os
import unittest
import asyncio
from fastapi.testclient import TestClient
import main
from main import (
    app,
    provider_client,
    normalize_vulnerabilities_and_evidence,
    ExtractedIncident,
    AdvancedScoreRequest
)

class TestReliefMeshAIEngine(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        provider_client.set_mock_extractor(None)
        provider_client.set_mock_deduplicator(None)
        provider_client.set_mock_translator(None)
        provider_client.set_mock_reachable(None)

    def tearDown(self):
        provider_client.set_mock_extractor(None)
        provider_client.set_mock_deduplicator(None)
        provider_client.set_mock_translator(None)
        provider_client.set_mock_reachable(None)

    # 1. Health checks
    def test_health_no_key(self):
        old_g = os.environ.pop('GOOGLE_API_KEY', None)
        old_gem = os.environ.pop('GEMINI_API_KEY', None)
        try:
            resp = self.client.get('/ai/health')
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data['status'], 'degraded')
            self.assertFalse(data['api_key_configured'])
            self.assertFalse(data['provider_reachable'])
            self.assertIn('skipped', data['smoke_test']['result'])
            self.assertEqual(data['port'], 8001)
            self.assertNotIn('key', str(data).lower().replace('api_key_configured', ''))
        finally:
            if old_g: os.environ['GOOGLE_API_KEY'] = old_g
            if old_gem: os.environ['GEMINI_API_KEY'] = old_gem

    def test_health_with_key_and_reachable(self):
        os.environ['GEMINI_API_KEY'] = 'mock-secret-key-12345'
        provider_client.set_mock_reachable(True)
        try:
            resp = self.client.get('/ai/health')
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data['status'], 'healthy')
            self.assertTrue(data['api_key_configured'])
            self.assertTrue(data['provider_reachable'])
            self.assertEqual(data['smoke_test']['result'], 'passed')
            self.assertNotIn('mock-secret-key', str(data))
        finally:
            os.environ.pop('GEMINI_API_KEY', None)

    def test_health_with_key_unreachable(self):
        os.environ['GEMINI_API_KEY'] = 'mock-secret-key-12345'
        provider_client.set_mock_reachable(False)
        try:
            resp = self.client.get('/ai/health')
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data['status'], 'degraded')
            self.assertTrue(data['api_key_configured'])
            self.assertFalse(data['provider_reachable'])
            self.assertIn('failed', data['smoke_test']['result'])
        finally:
            os.environ.pop('GEMINI_API_KEY', None)

    # 2. Vocabulary & Extraction
    def test_vocabulary_alignment_elderly_vs_mobility(self):
        vulns, ev = normalize_vulnerabilities_and_evidence('My grandmother needs food.')
        self.assertIn('elderly', vulns)
        self.assertNotIn('limited_mobility', vulns)
        self.assertIn('grandmother', ev)

        vulns2, ev2 = normalize_vulnerabilities_and_evidence('A young man cannot walk after injury.')
        self.assertIn('limited_mobility', vulns2)
        self.assertNotIn('elderly', vulns2)
        self.assertIn('cannot walk', ev2)

        vulns3, ev3 = normalize_vulnerabilities_and_evidence('Grandmother cannot walk and is trapped on 2nd floor.')
        self.assertIn('elderly', vulns3)
        self.assertIn('limited_mobility', vulns3)
        self.assertIn('grandmother', ev3)
        self.assertIn('cannot walk', ev3)

    def test_extraction_endpoint_valid(self):
        async def mock_extract(text):
            return {
                'location': 'Sector 4, Rohini',
                'incident_type': 'flood',
                'people_affected': 3,
                'needs': ['medical', 'supply'],
                'vulnerabilities': ['elderly', 'cannot_walk'],
                'medical_urgency': True,
                'severity_score': 5,
                'time_sensitivity_hours': 1.0,
                'environmental_threat': True,
                'confidence_score': 0.91,
                'uncertainty_notes': 'Estimated 3 people based on family report'
            }
        provider_client.set_mock_extractor(mock_extract)

        payload = {'text': 'Grandmother cannot walk and is trapped with 2 others in flood, water level 4ft.'}
        resp = self.client.post('/ai/extract-incident', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data['incident_type'], 'flood_rescue')
        self.assertIn('supplies', data['needs'])
        self.assertIn('rescue', data['needs'])
        self.assertIn('medical', data['needs'])
        self.assertIn('elderly', data['vulnerabilities'])
        self.assertIn('limited_mobility', data['vulnerabilities'])
        self.assertIn('grandmother', data['vulnerability_evidence'])
        self.assertIn('cannot walk', data['vulnerability_evidence'])
        self.assertEqual(data['severity_score'], 5)
        self.assertEqual(data['people_affected'], 3)
        self.assertEqual(data['time_sensitivity_hours'], 1.0)
        self.assertEqual(data['confidence_score'], 0.91)
        self.assertIn('provenance', data)

    def test_extraction_empty_text(self):
        resp = self.client.post('/ai/extract-incident', json={'text': '   '})
        self.assertEqual(resp.status_code, 400)

    def test_extracted_incident_pydantic_validation(self):
        with self.assertRaises(ValueError):
            ExtractedIncident(
                location='Delhi',
                incident_type='medical',
                people_affected=1,
                medical_urgency=True,
                severity_score=3,
                time_sensitivity_hours=1.0,
                environmental_threat=False,
                confidence_score=1.5
            )

    # 3. Deterministic Priority Scoring
    def test_canonical_priority_94(self):
        payload = {
            'location': 'Sector 4, Rohini',
            'incident_type': 'flood_rescue',
            'people_affected': 3,
            'vulnerabilities': ['elderly', 'limited_mobility'],
            'medical_urgency': True,
            'severity_score': 5,
            'environmental_threat': True,
            'time_sensitivity_hours': 1.0,
            'confidence_score': 0.91
        }
        resp = self.client.post('/ai/score-incident', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['priority_score'], 94)
        self.assertEqual(data['risk_level'], 'Critical')
        self.assertFalse(data['requires_human_review'])
        self.assertEqual(data['scoring_breakdown']['severity_points'], 35.0)
        self.assertEqual(data['scoring_breakdown']['medical_points'], 25.0)
        self.assertEqual(data['scoring_breakdown']['vulnerable_points'], 15.0)
        self.assertEqual(data['scoring_breakdown']['env_points'], 10.0)
        self.assertEqual(data['scoring_breakdown']['time_points'], 7.0)
        self.assertEqual(data['scoring_breakdown']['scale_points'], 2.4)

    def test_priority_boundary_cases(self):
        payload_low = {
            'location': 'Civic Center',
            'incident_type': 'supplies',
            'people_affected': 1,
            'vulnerabilities': [],
            'medical_urgency': False,
            'severity_score': 1,
            'environmental_threat': False,
            'time_sensitivity_hours': 24.0,
            'confidence_score': 1.0
        }
        resp = self.client.post('/ai/score-incident', json=payload_low)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['risk_level'], 'Low')
        self.assertLess(resp.json()['priority_score'], 40)

        payload_crit = {
            'location': 'Block C',
            'incident_type': 'building_collapse',
            'people_affected': 1,
            'vulnerabilities': [],
            'medical_urgency': False,
            'severity_score': 2,
            'environmental_threat': False,
            'time_sensitivity_hours': 12.0,
            'confidence_score': 1.0
        }
        resp_crit = self.client.post('/ai/score-incident', json=payload_crit)
        self.assertEqual(resp_crit.status_code, 200)
        self.assertGreaterEqual(resp_crit.json()['priority_score'], 85)

        payload_pen = {
            'location': 'Unknown',
            'incident_type': 'medical',
            'people_affected': 1,
            'vulnerabilities': [],
            'medical_urgency': True,
            'severity_score': 4,
            'environmental_threat': False,
            'time_sensitivity_hours': 4.0,
            'confidence_score': 0.50
        }
        resp_pen = self.client.post('/ai/score-incident', json=payload_pen)
        self.assertEqual(resp_pen.status_code, 200)
        self.assertTrue(resp_pen.json()['requires_human_review'])

    # 4. Resource-Aware Recommendation
    def test_canonical_initial_plan(self):
        payload = {
            'incident_id': 'INC-1042',
            'incident_type': 'flood_rescue',
            'needs': ['medical', 'rescue'],
            'candidate_resources': [
                {'id': 'AMB-02', 'type': 'ambulance', 'capabilities': ['medical', 'triage', 'transport'], 'status': 'available', 'eta_minutes': 6.0},
                {'id': 'RESCUE-01', 'type': 'rescue_boat', 'capabilities': ['rescue', 'flood_rescue', 'evacuation'], 'status': 'available', 'eta_minutes': 12.0},
                {'id': 'AMB-01', 'type': 'ambulance', 'capabilities': ['medical'], 'status': 'available', 'eta_minutes': 15.0},
                {'id': 'TRUCK-01', 'type': 'supply_truck', 'capabilities': ['supplies'], 'status': 'available', 'eta_minutes': 5.0}
            ]
        }
        resp = self.client.post('/ai/recommendation', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data['recommended_resources'], ['AMB-02', 'RESCUE-01'])
        self.assertEqual(data['confidence'], 0.95)
        self.assertEqual(data['coverage_result']['status'], 'satisfied')
        self.assertFalse(data['insufficient_coverage'])
        self.assertTrue(data['approval_required'])
        self.assertIn('AVAILABLE', data['reason_codes'])
        self.assertIn('CAPABILITY_MATCH', data['reason_codes'])
        self.assertIn('ETA_MINUTES', data['reason_codes'])
        self.assertIn('AMB-02', data['resource_reasons'])
        self.assertIn('RESCUE-01', data['resource_reasons'])

    def test_replacement_plan(self):
        payload = {
            'incident_id': 'INC-1042',
            'needs': ['medical', 'rescue'],
            'continuing_assignments': [
                {'id': 'RESCUE-01', 'capabilities': ['rescue'], 'status': 'responding'}
            ],
            'blocked_resources': ['AMB-02'],
            'replacement_context': {
                'replaced_resource_id': 'AMB-02',
                'reason': 'obstruction delay ETA 6 -> 24',
                'old_eta_minutes': 6.0,
                'new_eta_minutes': 24.0
            },
            'candidate_resources': [
                {'id': 'AMB-05', 'capabilities': ['medical', 'transport'], 'status': 'available', 'eta_minutes': 9.0},
                {'id': 'AMB-02', 'capabilities': ['medical'], 'status': 'delayed', 'eta_minutes': 24.0}
            ]
        }
        resp = self.client.post('/ai/recommendation', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data['recommended_resources'], ['AMB-05', 'RESCUE-01'])
        self.assertIn('CONTINUING_ASSIGNMENT', data['reason_codes'])
        self.assertIn('BLOCKED_RESOURCE_EXCLUDED', data['reason_codes'])
        self.assertEqual(data['coverage_result']['status'], 'satisfied')

    def test_insufficient_coverage(self):
        payload = {
            'incident_id': 'INC-1042',
            'needs': ['hazmat', 'rescue'],
            'candidate_resources': [
                {'id': 'AMB-02', 'capabilities': ['medical'], 'status': 'available', 'eta_minutes': 6.0}
            ]
        }
        resp = self.client.post('/ai/recommendation', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertTrue(data['insufficient_coverage'])
        self.assertEqual(data['coverage_result']['status'], 'insufficient')
        self.assertIn('hazmat', data['coverage_result']['missing_needs'])
        self.assertIn('INSUFFICIENT_COVERAGE', data['reason_codes'])

    def test_ai_only_selects_supplied_candidate_ids(self):
        payload = {
            'incident_id': 'INC-1042',
            'needs': ['medical'],
            'candidate_resources': [
                {'id': 'CUSTOM-AMB-99', 'capabilities': ['medical'], 'status': 'available', 'eta_minutes': 4.0}
            ]
        }
        resp = self.client.post('/ai/recommendation', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['recommended_resources'], ['CUSTOM-AMB-99'])
        self.assertNotIn('AMB-02', data['recommended_resources'])
        self.assertNotIn('AMB-05', data['recommended_resources'])

    # 5. Deduplication
    def test_dedup_empty_candidates(self):
        payload = {
            'new_report_text': 'Flooding near main market',
            'active_incidents': []
        }
        resp = self.client.post('/ai/deduplicate-incident', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['is_duplicate'])
        self.assertIsNone(data['matched_incident_id'])
        self.assertIn('No active incidents', data['similarity_reason'])

    def test_dedup_duplicate_valid(self):
        async def mock_dedup(report, active):
            return {
                'is_duplicate': True,
                'matched_incident_id': 'INC-1042',
                'similarity_reason': 'Same physical flood event at Sector 4'
            }
        provider_client.set_mock_deduplicator(mock_dedup)

        payload = {
            'new_report_text': 'Water rising at Sector 4 Rohini, elderly person stranded',
            'active_incidents': [
                {'incident_id': 'INC-1042', 'location': 'Sector 4, Rohini', 'incident_type': 'flood_rescue', 'summary_text': 'Flood with trapped grandmother'}
            ]
        }
        resp = self.client.post('/ai/deduplicate-incident', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['is_duplicate'])
        self.assertEqual(data['matched_incident_id'], 'INC-1042')

    def test_dedup_cross_language(self):
        async def mock_dedup(report, active):
            if 'રોહિણી' in report or 'रोहिणी' in report:
                return {
                    'is_duplicate': True,
                    'matched_incident_id': 'INC-1042',
                    'similarity_reason': 'Cross-lingual match: Report in Gujarati matches English incident INC-1042 at Rohini.'
                }
            return {'is_duplicate': False, 'matched_incident_id': None, 'similarity_reason': 'No match'}
        provider_client.set_mock_deduplicator(mock_dedup)

        payload = {
            'new_report_text': 'રોહિણી સેક્ટર 4 માં પૂરના પાણી ઘરોમાં ઘૂસી ગયા છે',
            'active_incidents': [
                {'incident_id': 'INC-1042', 'location': 'Sector 4, Rohini', 'incident_type': 'flood_rescue', 'summary_text': 'Rising flood waters at Rohini Sector 4'}
            ]
        }
        resp = self.client.post('/ai/deduplicate-incident', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['is_duplicate'])
        self.assertEqual(data['matched_incident_id'], 'INC-1042')
        self.assertIn('Cross-lingual', data['similarity_reason'])

    def test_dedup_nonduplicate(self):
        async def mock_dedup(report, active):
            return {
                'is_duplicate': False,
                'matched_incident_id': None,
                'similarity_reason': 'Distinct incident in another city'
            }
        provider_client.set_mock_deduplicator(mock_dedup)

        payload = {
            'new_report_text': 'Small fire in Mumbai kitchen',
            'active_incidents': [
                {'incident_id': 'INC-1042', 'location': 'Sector 4, Rohini', 'incident_type': 'flood_rescue', 'summary_text': 'Flood in Delhi'}
            ]
        }
        resp = self.client.post('/ai/deduplicate-incident', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['is_duplicate'])
        self.assertIsNone(data['matched_incident_id'])

    def test_dedup_invalid_hallucinated_id(self):
        async def mock_dedup(report, active):
            return {
                'is_duplicate': True,
                'matched_incident_id': 'INC-HALLUCINATED-999',
                'similarity_reason': 'Matches another event'
            }
        provider_client.set_mock_deduplicator(mock_dedup)

        payload = {
            'new_report_text': 'Water rising at Sector 4',
            'active_incidents': [
                {'incident_id': 'INC-1042', 'location': 'Sector 4', 'incident_type': 'flood_rescue', 'summary_text': 'Flood'}
            ]
        }
        resp = self.client.post('/ai/deduplicate-incident', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['is_duplicate'])
        self.assertIsNone(data['matched_incident_id'])
        self.assertIn('invalid incident ID', data['similarity_reason'])

    # 6. Translation
    def test_translation_valid(self):
        async def mock_trans(text, src, tgt):
            return 'Flood water is rising rapidly'
        provider_client.set_mock_translator(mock_trans)

        payload = {
            'text': 'बाढ़ का पानी तेजी से बढ़ रहा है',
            'source_language': 'Hindi',
            'target_language': 'English'
        }
        resp = self.client.post('/ai/translate-report', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['translated_text'], 'Flood water is rising rapidly')
        self.assertEqual(data['target_language'], 'English')

    def test_translation_unsupported_language(self):
        payload = {
            'text': 'Emergency assistance needed',
            'target_language': 'Klingon'
        }
        resp = self.client.post('/ai/translate-report', json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not supported', resp.json()['detail'])

    def test_translation_identity_passthrough(self):
        payload = {
            'text': 'Medical supplies needed at shelter',
            'source_language': 'English',
            'target_language': 'English'
        }
        resp = self.client.post('/ai/translate-report', json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['translated_text'], 'Medical supplies needed at shelter')

    # 7. Error Sanitization
    def test_provider_failure_sanitization(self):
        async def mock_fail(text):
            raise RuntimeError('SecretKeyError: raw_token_key_ABC12345 leaked in trace')
        provider_client.set_mock_extractor(mock_fail)

        resp = self.client.post('/ai/extract-incident', json={'text': 'Trapped in flood'})
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn('ABC12345', resp.text)
        self.assertIn('detail', resp.json())

    # 8. Legacy backward compatibility
    def test_legacy_analyze_incident(self):
        resp = self.client.post('/ai/analyze-incident', json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['incident_id'], 'INC-1042')
        self.assertEqual(data['recommended_resources'], ['AMB-02', 'RESCUE-01'])
        self.assertTrue(data['approval_required'])

if __name__ == '__main__':
    unittest.main()
