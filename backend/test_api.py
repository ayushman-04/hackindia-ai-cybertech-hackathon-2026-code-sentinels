"""
Test Suite for Slope Signal Backend API
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from backend.main import app
from backend.services import earthquake_service as earthquake_module
from backend.services.chatbot_service import generate_offline_response

client = TestClient(app)

def test_health():
    res1 = client.get("/api/health")
    assert res1.status_code == 200
    assert res1.json()["status"] == "healthy"
    res2 = client.get("/health")
    assert res2.status_code == 200
    assert res2.json()["status"] == "healthy"
    print("[PASS] Health check endpoints (/health, /api/health) passed")


def test_map_geojson_layers():
    risk = client.get("/api/map/risk-polygons?state=sikkim")
    assert risk.status_code == 200, risk.text
    risk_payload = risk.json()
    assert risk_payload["type"] == "FeatureCollection"
    assert len(risk_payload["features"]) >= 1
    first = risk_payload["features"][0]
    assert first["geometry"]["type"] == "Polygon"
    assert "risk_score" in first["properties"]

    bounds = client.get("/api/map/boundaries?level=state")
    assert bounds.status_code == 200, bounds.text
    bounds_payload = bounds.json()
    assert bounds_payload["type"] == "FeatureCollection"
    assert len(bounds_payload["features"]) >= 1
    boundary = bounds_payload["features"][0]
    assert boundary["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    assert "state" in boundary["properties"]

    print("[PASS] GeoJSON risk/boundary map layers passed")


def test_live_contextual_map_contracts():
    weather = client.get("/api/weather/live?state=sikkim")
    assert weather.status_code == 200, weather.text
    weather_payload = weather.json()
    assert "current_rainfall_mm_hr" in weather_payload
    assert "last_updated" in weather_payload

    earthquakes = client.get("/api/earthquakes?latitude=27.5&longitude=88.5&radius_km=500&limit=5")
    assert earthquakes.status_code == 200, earthquakes.text
    eq_payload = earthquakes.json()
    assert isinstance(eq_payload.get("events", []), list)
    assert "earthquake_data_available" in eq_payload

    reports = client.get("/api/reports")
    assert reports.status_code == 200, reports.text
    report_list = reports.json()
    assert len(report_list) >= 1
    first_report = report_list[0]
    assert "classification" in first_report or "aiClassificationStatus" in first_report
    assert first_report.get("state") in {"sikkim", "assam", "meghalaya", "arunachal", "manipur", "nagaland", "mizoram", "tripura"} or first_report.get("state") is not None

    map_reports = client.get("/api/map/reports?state=sikkim")
    assert map_reports.status_code == 200, map_reports.text
    map_payload = map_reports.json()
    assert map_payload["type"] == "FeatureCollection"
    assert len(map_payload["features"]) >= 1

    print("[PASS] Live contextual map contracts passed: rainfall, earthquake, public reports, and map report GeoJSON")


def test_chatbot_language_support():
    response = client.post("/api/chat", json={
        "message": "What is the risk in Sikkim?",
        "history": [],
        "language": "hi"
    })
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["reply"], str)
    assert "" != payload["reply"].strip()
    print(f"[PASS] Chatbot language support passed: {payload['source']} in hi mode")


def test_chatbot_all_language_responses():
    language_markers = {
        "en": "Slope Signal Assistant can analyze",
        "hi": "Slope Signal सहायक",
        "as": "Slope Signal সহায়কে",
        "bn": "Slope Signal সহায়ক",
        "brx": "Slope Signal सहायक",
        "ks": "Slope Signal madadgar",
        "mni": "Slope Signal assistant-na",
        "lus": "Slope Signal assistant chuan",
        "ne": "Slope Signal सहायकले",
    }
    english_reply = None
    for language, marker in language_markers.items():
        response = client.post("/api/chat", json={"message": "hello", "language": language})
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert marker in reply
        if language == "en":
            english_reply = reply
        else:
            assert reply != english_reply

    structured = generate_offline_response(
        "North Cachar Hills risk?",
        loc_context={
            "location": {"name": "North Cachar Hills", "zone_id": "zone-test", "lat": 25.2, "lon": 93.0},
            "risk_details": {
                "final_risk_score": 42,
                "risk_level": "MODERATE",
                "base_ml_probability": 0.42,
                "inputs": {
                    "rainfall": {"rainfall_3d_mm": 120},
                    "slope_deg": 35,
                    "elevation_m": 900,
                    "seismic": {"seismic_trigger_score": 0.1},
                    "soil_details": {"soil_name": "Loam"},
                },
                "location": {"latitude": 25.2, "longitude": 93.0},
            },
        },
        language="hi",
    )
    assert "कुल भूस्खलन जोखिम स्कोर" in structured["reply"]
    assert "42 / 100" in structured["reply"]
    print("[PASS] Chatbot responses and structured location-risk localization passed for all 9 languages")


def test_chatbot_navigation_commands():
    commands = {
        "Show me the risk map": "risk-map",
        "Open earthquake monitor": "earthquake-monitor",
        "Show weather": "dashboard",
        "Open Hills": "hills-regions",
        "Open Hills and Mountain Regions": "hills-regions",
        "Show mountain regions": "hills-regions",
        "Go to hills": "hills-regions",
        "Open Regions": "hills-regions",
        "Show regions": "hills-regions",
        "Go to regions": "hills-regions",
        "Show hills in Meghalaya": "hills-regions",
        "Open alerts": "alerts",
        "Report a hazard": "crowdsource-cv-verification",
        "Go home": "home",
    }
    for message, module in commands.items():
        response = client.post("/api/chat", json={"message": message, "language": "en"})
        assert response.status_code == 200
        action = response.json()["action"]
        assert action["type"] == "NAVIGATE"
        assert action["module"] == module
    print("[PASS] Chatbot navigation commands preserved shared action routing")


def test_hazard_zones():
    response = client.get("/api/zones")
    assert response.status_code == 200
    zones = response.json()
    assert len(zones) >= 5
    assert any(z["id"] == "zone-sk-01" for z in zones)
    print(f"[PASS] Hazard zones endpoint passed ({len(zones)} zones loaded)")


def test_field_classifier_requires_v2_onnx_artifact():
    from backend.ml.field_report_classifier import classify_field_image

    image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\x09\x09\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' ",#\x1c\x1c(7),01444\x1f'9=82<.342\x ff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x3a\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\xff\xd9"
    try:
        classify_field_image("report-v2-test", image_bytes)
        raise AssertionError("v1 fallback should not be used when the v2 ONNX artifact is missing")
    except RuntimeError as exc:
        assert "classification unavailable/error" in str(exc)
        print("[PASS] v2 classifier enforces ONNX artifact requirement without falling back to v1")


def test_field_report_dataset_guard_rejects_invalid_split_coverage():
    from pathlib import Path

    from backend.ml.train_field_report_classifier import validate_split_coverage

    dataset_root = Path(__file__).resolve().parent / "ml" / "datasets" / "field_report_classifier"
    assert dataset_root.exists(), "field_report_classifier dataset directory is missing"

    try:
        validate_split_coverage(dataset_root)
        raise AssertionError("invalid field-report splits should be rejected before training")
    except ValueError as exc:
        text = str(exc)
        assert "roadBlockage" in text or "flood" in text or "Invalid field-report dataset split" in text
        print("[PASS] invalid field-report splits are rejected before training begins")


def test_field_classifier_ignores_hazard_type_override_for_low_confidence(monkeypatch):
    import backend.ml.field_report_classifier as classifier_module

    class FakeSession:
        def get_inputs(self):
            return [type("Input", (), {"name": "input"})()]

        def run(self, *_args, **_kwargs):
            logits = np.array([[1.4, 0.0, -1.0, -0.5]], dtype=np.float32)
            return [logits]

    monkeypatch.setattr(classifier_module, "_SESSION", None)
    monkeypatch.setattr(classifier_module, "MODEL_THRESHOLD", 0.7)
    monkeypatch.setattr(classifier_module, "MODEL_CLASSES", ("landslide", "roadBlockage", "flood", "other"))
    monkeypatch.setattr(classifier_module, "_ensure_v2_ready", lambda: FakeSession())

    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(128, 90, 50)).save(buffer, format="JPEG")
    payload = buffer.getvalue()

    result = classifier_module.classify_field_image("report-hazard-override", payload, hazard_type="landslide")

    assert result["predicted_class"] == "other"
    assert result["severity"] == "UNKNOWN"
    assert result["confidence"] < 0.7
    print("[PASS] hazard_type is ignored when the image evidence is below the conservative threshold")


def test_field_classifier_preserves_explicit_rainfall_selection(monkeypatch):
    import backend.ml.field_report_classifier as classifier_module

    class FakeSession:
        def get_inputs(self):
            return [type("Input", (), {"name": "input"})()]

        def run(self, *_args, **_kwargs):
            logits = np.array([[4.0, 0.0, -1.0, -2.0]], dtype=np.float32)
            return [logits]

    monkeypatch.setattr(classifier_module, "_SESSION", None)
    monkeypatch.setattr(classifier_module, "_ensure_v2_ready", lambda: FakeSession())

    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(128, 90, 50)).save(buffer, format="JPEG")
    result = classifier_module.classify_field_image(
        "report-rainfall-selection", buffer.getvalue(), hazard_type="rainfall"
    )

    assert result["hazard_type"] == "rainfall"
    assert result["predicted_class"] == "landslide"
    assert result["predicted_class"] != result["hazard_type"]
    print("[PASS] explicit rainfall selection is preserved separately from a landslide visual prediction")


def test_susceptibility_calculation():
    payload = {
        "slope_deg": 48.5,
        "soil_saturation_pct": 85.0,
        "elevation_m": 1420.0
    }
    response = client.post("/api/zones/calculate-susceptibility", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "susceptibility_index" in data
    assert data["risk_status"] in ["CRITICAL RED", "ADVISORY ORANGE", "NOMINAL GREEN"]
    print(f"[PASS] Susceptibility calculation passed: {data['risk_status']} ({data['susceptibility_index']})")

def test_predict_lstm():
    response = client.get("/api/predict/lstm?extra_rainfall=25")
    assert response.status_code == 200
    data = response.json()
    assert "hazard_score" in data
    assert "simulated_fos" in data
    assert "simulated_pwp" in data
    assert "lead_time_display" in data
    print(f"[PASS] LSTM dynamic trigger passed: Hazard Score={data['hazard_score']}, FoS={data['simulated_fos']}, Lead Time={data['lead_time_display']}")

def test_crowdsource_reports():
    response = client.get("/api/reports")
    assert response.status_code == 200
    reports = response.json()
    assert len(reports) >= 1
    print(f"[PASS] Crowdsource reports passed ({len(reports)} reports)")

def test_report_submission_and_cv():
    payload = {
        "location": "NH-10 Near Dikchu Bend (Km 36.2)",
        "subDivision": "Mangan Sub-Division",
        "state": "sikkim",
        "latitude": 27.2388,
        "longitude": 88.5012,
        "description": "Active rotational blowout with tension cracks across roadway."
    }
    response = client.post("/api/reports/submit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["urgency"] == "CRITICAL"
    assert data["classification"] == "landslide"
    assert data["confidence"] > 0
    print(f"[PASS] Citizen report upload + AI CV vision passed: {data['code']} ({data['cvLabel']})")

def test_sensor_nodes():
    response = client.get("/api/sensors")
    assert response.status_code == 200
    sensors = response.json()
    assert len(sensors) >= 4
    print(f"[PASS] IoT Sensor telemetry nodes passed ({len(sensors)} sensors)")

def test_cap_alert():
    response = client.get("/api/alerts/cap")
    assert response.status_code == 200
    data = response.json()
    assert "alert" in data
    assert "raw_xml" in data
    assert "MANDATORY EVACUATION" in data["alert"]["headline"]
    print(f"[PASS] CAP 1.2 Alert generation passed: {data['alert']['identifier']}")

def test_live_weather():
    response = client.get("/api/weather/live?state=sikkim")
    assert response.status_code == 200
    data = response.json()
    assert "current_temperature_c" in data
    assert "soil_saturation_pct" in data
    print(f"[PASS] Live meteorological & soil moisture feed passed: {data['station_name']} ({data['current_temperature_c']}C, {data['soil_saturation_pct']}% Saturation)")

def test_sms_broadcast():
    from backend import config

    # 1. Test Demo Mode (default)
    payload = {
        "headline": "MANDATORY EVACUATION NH-10",
        "instruction": "Move to Singtam Relief Camp immediately.",
        "phone_numbers": ["+919800012345"],
        "state": "sikkim"
    }
    config.SMS_DEMO_MODE = True
    response = client.post("/api/alerts/sms-broadcast", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "demo"
    assert data["gateway"] == "SMSHorizon DEMO"
    assert data["recipients_count"] == 0
    assert "Demo dispatch only" in data["message"]

    # 2. Test Provider Not Configured (when demo mode is false and keys missing)
    config.SMS_DEMO_MODE = False
    config.SMSHORIZON_API_KEY = ""
    config.SMSHORIZON_SENDER_ID = ""
    res_unconf = client.post("/api/alerts/sms-broadcast", json=payload)
    assert res_unconf.status_code == 200
    data_unconf = res_unconf.json()
    assert data_unconf["status"] == "provider_not_configured"
    assert "SMSHorizon is not configured" in data_unconf["message"]

    # 3. Test Missing Recipients (when config present)
    config.SMSHORIZON_API_KEY = "test_key"
    config.SMSHORIZON_SENDER_ID = "TESTSD"
    config.SMSHORIZON_DLT_ENTITY_ID = "1001"
    config.SMSHORIZON_TEMPLATE_ID = "2002"
    res_norecip = client.post("/api/alerts/sms-broadcast", json={"headline": "Alert", "instruction": "Flee", "phone_numbers": []})
    assert res_norecip.status_code == 200
    assert res_norecip.json()["status"] == "dispatch_failed"

    # 4. Test Mocked Successful Provider Response (status: sent)
    from backend.services import sms_service as sms_module
    orig_post = sms_module.requests.post
    
    class MockSuccessResponse:
        status_code = 200
        text = "MSG_ID_987654"

    sms_module.requests.post = lambda *args, **kwargs: MockSuccessResponse()
    try:
        res_sent = client.post("/api/alerts/sms-broadcast", json=payload)
        assert res_sent.status_code == 200
        data_sent = res_sent.json()
        assert data_sent["status"] == "sent"
        assert data_sent["gateway"] == "SMSHorizon"
        assert data_sent["recipients_count"] == 1
    finally:
        sms_module.requests.post = orig_post

    # 5. Test Mocked Provider Unavailable Network Error
    def mock_timeout(*args, **kwargs):
        raise sms_module.requests.Timeout("Connection timed out")

    sms_module.requests.post = mock_timeout
    try:
        res_unavail = client.post("/api/alerts/sms-broadcast", json=payload)
        assert res_unavail.status_code == 200
        assert res_unavail.json()["status"] == "provider_unavailable"
    finally:
        sms_module.requests.post = orig_post
        config.SMS_DEMO_MODE = True  # Restore default

    print(f"[PASS] Truthful SMS Broadcast provider states (demo, provider_not_configured, sent, provider_unavailable, dispatch_failed) passed")


def test_ml_predict():
    payload = {
        "elevation": 1450.0,
        "slope": 38.0,
        "aspect": 190.0,
        "soil_id": "4276.0",
        "landcover_class": "50.0",
        "rainfall_1d": 65.0,
        "rainfall_3d": 120.0,
        "rainfall_7d": 195.0,
        "rainfall_15d": 260.0,
        "rainfall_30d": 380.0
    }
    # Test both /api/ml/predict and /predict alias
    response = client.post("/api/ml/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "prediction" in data

    res_alias = client.post("/predict", json=payload)
    assert res_alias.status_code == 200
    assert "prediction" in res_alias.json()

    print(f"[PASS] ML Pipeline Inference passed: {data['prediction_label']} ({data['probability_percentage']}% Prob, {data['risk_level']})")

def test_model_info():
    res1 = client.get("/api/ml/model-info")
    assert res1.status_code == 200
    assert "model_name" in res1.json()
    res2 = client.get("/model-info")
    assert res2.status_code == 200
    assert "model_name" in res2.json()
    print("[PASS] Model info endpoints (/model-info, /api/ml/model-info) passed")

def test_predict_invalid_rainfall():
    # Violate cumulative rainfall constraint: rainfall_3d < rainfall_1d
    invalid_payload = {
        "elevation": 1450.0,
        "slope": 38.0,
        "aspect": 190.0,
        "soil_id": "4276.0",
        "landcover_class": "50.0",
        "rainfall_1d": 120.0,
        "rainfall_3d": 50.0,  # Invalid: 50 < 120
        "rainfall_7d": 195.0,
        "rainfall_15d": 260.0,
        "rainfall_30d": 380.0
    }
    response = client.post("/predict", json=invalid_payload)
    assert response.status_code == 422
    assert "Cumulative rainfall constraint violated" in response.json()["detail"]
    print("[PASS] Invalid rainfall validation (422) caught correctly")

def test_ml_metrics():
    response = client.get("/api/ml/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "roc_auc" in data
    assert "accuracy" in data
    print(f"[PASS] ML Pipeline Metrics passed: ROC-AUC {round(data['roc_auc'], 3)}, Accuracy {round(data['accuracy'], 3)}")

def test_ml_comparison():
    response = client.get("/api/ml/comparison")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    models = [m["model"] for m in data]
    assert "Random Forest" in models
    assert "Logistic Regression" in models
    print(f"[PASS] ML Model Comparison passed: {len(data)} models evaluated")

def test_ml_datasets():
    response = client.get("/api/ml/datasets")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 15
    print(f"[PASS] Landslide Datasets Inventory passed: {len(data)} datasets integrated")

def test_gis_historical_training_events():
    response = client.get("/api/zones/historical-training-events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 30
    assert any("rainfall_3d" in evt for evt in events)
    assert any("top_pct" in evt and "left_pct" in evt for evt in events)
    print(f"[PASS] GIS Historical Training Events passed: {len(events)} real ground-truth events loaded with canvas coordinates")

def test_gis_zone_ml_risk():
    response = client.get("/api/zones/zone-sk-01/ml-risk?extra_rainfall=30")
    assert response.status_code == 200
    data = response.json()
    assert data["zone_id"] == "zone-sk-01"
    assert "probability_percentage" in data
    assert "historical_precedents_count" in data
    assert "risk_tier" in data
    print(f"[PASS] GIS Zone ML Risk Inference passed: {data['zone_name']} -> {data['probability_percentage']}% ({data['risk_tier']}, {data['historical_precedents_count']} precedents)")

def test_gis_ml_heatmap_points():
    response = client.get("/api/zones/ml-heatmap-points?extra_rainfall=25")
    assert response.status_code == 200
    data = response.json()
    assert "points" in data
    assert len(data["points"]) >= 50
    assert any(p["category"] == "zone_susceptibility" for p in data["points"])
    assert any(p["category"] == "historical_ground_truth" for p in data["points"])
    assert all(0.0 <= p["weight"] <= 1.0 for p in data["points"])
    print(f"[PASS] GIS ML Pattern Heatmap passed: {len(data['points'])} weighted points generated from ML model & training data")

def test_official_earthquake_contract():
    response = client.get("/api/earthquakes?latitude=27.53&longitude=88.51&radius_km=500")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "National Center for Seismology"
    assert "earthquake_data_available" in data
    assert "earthquake_trigger_score" in data
    assert isinstance(data["events"], list)
    if data["events"]:
        event = data["events"][0]
        assert set(("id", "magnitude", "latitude", "longitude", "depth_km", "location", "event_time", "source", "status")) <= set(event)
        assert event["source"] == "National Center for Seismology"
    print(f"[PASS] Official NCS earthquake feed contract passed ({len(data['events'])} nearby events)")

    no_nearby = client.get("/api/earthquakes?latitude=0&longitude=0&radius_km=1")
    assert no_nearby.status_code == 200
    no_nearby_data = no_nearby.json()
    if no_nearby_data["earthquake_data_available"]:
        assert no_nearby_data["events"] == []
        assert no_nearby_data["earthquake_trigger_score"] == 0.0
    print("[PASS] No-nearby-earthquake state keeps the trigger at zero")

def test_earthquake_parser_and_safe_fallback():
    html = """
    <li data-json='{"event_id":"ncs-1","event_name":"M: 4.2 - Sikkim","origin_time":"2026-09-09 10:01:25 IST","lat_long":"27.531, 88.513","magnitude_depth":"M: 4.2 , D: 20km","event_type":"Reviewed"}'></li>
    <li data-json='{"event_id":"ncs-1","event_name":"M: 4.2 - Sikkim","origin_time":"2026-09-09 10:01:25 IST","lat_long":"27.531, 88.513","magnitude_depth":"M: 4.2 , D: 20km","event_type":"Reviewed"}'></li>
    <li data-json='not-json'></li>
    """
    events = earthquake_module.EarthquakeService._parse_ncs_html(html)
    assert len(events) == 1
    assert events[0]["location"] == "Sikkim"
    assert events[0]["event_time"].endswith("+05:30")

    original_get = earthquake_module.requests.get
    earthquake_module.earthquake_service._cache = None
    earthquake_module.requests.get = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline"))
    try:
        response = earthquake_module.earthquake_service.get_earthquakes()
        assert response["earthquake_data_available"] is False
        assert response["source_status"] == "temporarily_unavailable"
        assert response["events"] == []
        assert response["earthquake_trigger_score"] == 0.0
    finally:
        earthquake_module.requests.get = original_get
        earthquake_module.earthquake_service._cache = None
    print("[PASS] Earthquake deduplication, validation, and unavailable fallback passed")

def test_chatbot():
    res = client.post("/api/chat", json={"message": "What is the landslide risk at Teesta Basin?"})
    assert res.status_code == 200
    data = res.json()
    assert "Teesta Basin" in data["reply"]
    assert "final_risk_score" in data["reply"] or "Score" in data["reply"]
    assert data["source"] in ["slope-signal-live-ml", "terraguard-live-ml", "gemini-1.5-flash"]
    assert data["action"]["type"] == "SELECT_REGION"

    # Test offline FAQ answer
    res2 = client.post("/api/chat", json={"message": "Show me the risk map"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["action"]["type"] == "NAVIGATE"
    assert data2["action"]["module"] == "risk-map"

    # Test emergency SOS question
    res3 = client.post("/api/chat", json={"message": "What is the emergency helpline number?"})
    assert res3.status_code == 200
    data3 = res3.json()
    assert "1078" in data3["reply"]
    print("[PASS] Chatbot /api/chat grounded location risk, FAQ, and Emergency SOS tests passed")


def test_sqlite_schema_migration_preserves_existing_records():
    import tempfile
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from backend.database.database import ensure_sqlite_schema_migrations
    from backend.database.models import CrowdsourceReportModel

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "legacy_test.db"
        temp_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        try:
            with temp_engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE crowdsource_reports (
                            id VARCHAR PRIMARY KEY,
                            code VARCHAR UNIQUE,
                            location VARCHAR NOT NULL,
                            subDivision VARCHAR NOT NULL,
                            state VARCHAR NOT NULL,
                            timeAgo VARCHAR,
                            reportedTime VARCHAR NOT NULL,
                            urgency VARCHAR NOT NULL,
                            verifiedBy VARCHAR,
                            imageUrl VARCHAR NOT NULL,
                            imageAlt VARCHAR,
                            cvRisk VARCHAR NOT NULL,
                            cvLabel VARCHAR NOT NULL,
                            cvModel VARCHAR,
                            summary TEXT NOT NULL,
                            description TEXT NOT NULL,
                            coordinates VARCHAR NOT NULL,
                            latitude FLOAT,
                            longitude FLOAT,
                            deviceId VARCHAR,
                            elevation VARCHAR,
                            slope VARCHAR,
                            precipitation VARCHAR,
                            exifStatus VARCHAR,
                            audioLanguage VARCHAR,
                            audioDuration VARCHAR,
                            vernacularText TEXT,
                            englishTranslation TEXT,
                            sensorCorroboration JSON,
                            boundingBoxes JSON,
                            imageStorageKey VARCHAR,
                            imageOriginalName VARCHAR,
                            imageMimeType VARCHAR,
                            imageSizeBytes INTEGER,
                            aiClassificationStatus VARCHAR,
                            aiConfidence FLOAT,
                            verificationStatus VARCHAR,
                            classification VARCHAR,
                            confidence FLOAT,
                            alertStatus VARCHAR,
                            smsStatus VARCHAR,
                            selectedRecipientsCount INTEGER,
                            alertRadiusKm FLOAT,
                            verifiedAt DATETIME,
                            status VARCHAR
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO crowdsource_reports (
                            id, code, location, subDivision, state, reportedTime, urgency,
                            imageUrl, cvRisk, cvLabel, summary, description, coordinates, status
                        ) VALUES (
                            'legacy-rep-01', 'NER-LEGACY-0001', 'Singtam Old Bridge', 'East Sikkim',
                            'sikkim', '09:15 IST', 'URGENT', 'https://example.com/img.jpg',
                            '82.0%', 'Legacy Slide', 'Legacy summary', 'Legacy description',
                            '27.2388 N, 88.5012 E', 'PENDING_VERIFICATION'
                        )
                        """
                    )
                )

            added_cols = ensure_sqlite_schema_migrations(temp_engine)
            assert "crowdsource_reports.hazardType" in added_cols
            assert "crowdsource_reports.zoneId" in added_cols
            assert "crowdsource_reports.predictedClass" in added_cols
            assert "crowdsource_reports.isVerified" in added_cols

            # Idempotent second run adds no duplicate columns
            second_run = ensure_sqlite_schema_migrations(temp_engine)
            assert second_run == []

            TempSession = sessionmaker(bind=temp_engine)
            with TempSession() as session:
                legacy_row = session.query(CrowdsourceReportModel).filter_by(id="legacy-rep-01").first()
                assert legacy_row is not None
                assert legacy_row.code == "NER-LEGACY-0001"
                assert legacy_row.location == "Singtam Old Bridge"
                assert legacy_row.isVerified is False
                assert legacy_row.classificationSource == "unclassified"
        finally:
            temp_engine.dispose()
    print("[PASS] Non-destructive SQLite schema migration preserved existing records and added Phase 2A columns")


def test_phase_2a_report_persistence_and_metadata_preservation():
    import uuid
    import backend.ml.field_report_classifier as classifier_module

    class FakeHighConfSession:
        def get_inputs(self):
            return [type("Input", (), {"name": "input"})()]

        def run(self, *_args, **_kwargs):
            # High confidence for class 0 ('landslide')
            return [np.array([[5.0, -1.0, -1.5, -2.0]], dtype=np.float32)]

    orig_ensure = classifier_module._ensure_v2_ready
    orig_session = classifier_module._SESSION
    classifier_module._SESSION = None
    classifier_module._ensure_v2_ready = lambda: FakeHighConfSession()

    try:
        buffer = BytesIO()
        Image.new("RGB", (64, 64), color=(110, 85, 60)).save(buffer, format="JPEG")
        img_bytes = buffer.getvalue()

        custom_id = f"phase2a-meta-{uuid.uuid4().hex[:8]}"
        res = client.post(
            "/api/reports/submit",
            data={
                "report_id": custom_id,
                "hazard_type": "rainfall",
                "state": "Assam",
                "zone_id": "zone-as-03",
                "timestamp": "2026-10-27T10:00:00Z",
                "location": "Haflong Hill Section",
                "subDivision": "Dima Hasao",
                "description": "Heavy monsoon rainfall observed near culvert.",
                "latitude": "25.1632",
                "longitude": "93.0128",
            },
            files={"file": ("evidence.jpg", img_bytes, "image/jpeg")},
        )
        assert res.status_code == 200, res.text
        payload = res.json()

        # 1. Report ID, state, zone, and user-selected hazard_type are preserved
        assert payload["report_id"] == custom_id
        assert payload["state"] == "assam"
        assert payload["zone_id"] == "zone-as-03"
        assert payload["hazard_type"] == "rainfall"

        # 2. ONNX predicted_class is stored separately from user hazard_type
        assert payload["predicted_class"] == "landslide"
        assert payload["hazard_type"] != payload["predicted_class"]
        assert payload["classification_source"] == "onnx_v2"
        assert payload["confidence"] > 0.90

        # 3. Not marked verified merely because classifier returned high-confidence prediction
        assert payload["verified"] is False
        assert payload["verification_status"] == "PENDING_VERIFICATION"
        assert payload["alert_status"] == "not_triggered"

        # 4. Persisted in database and retrievable via GET /api/reports/{report_id}
        fetched = client.get(f"/api/reports/{custom_id}")
        assert fetched.status_code == 200
        db_row = fetched.json()
        assert db_row["id"] == custom_id
        assert db_row["hazardType"] == "rainfall"
        assert db_row["predictedClass"] == "landslide"
        assert db_row["zoneId"] == "zone-as-03"
        assert db_row["state"] == "assam"
        assert db_row["isVerified"] is False
        assert db_row["verificationStatus"] == "PENDING_VERIFICATION"

        # 5. Authority escalation explicitly transitions report to verified/CONFIRMED
        esc = client.post(f"/api/reports/{custom_id}/escalate")
        assert esc.status_code == 200
        assert esc.json()["verified"] is True
        fetched_after = client.get(f"/api/reports/{custom_id}").json()
        assert fetched_after["isVerified"] is True
        assert fetched_after["verificationStatus"] == "CONFIRMED"
    finally:
        classifier_module._ensure_v2_ready = orig_ensure
        classifier_module._SESSION = orig_session

    print("[PASS] Phase 2A report persistence, metadata preservation, hazard_type vs predicted_class separation, and unverified-by-default guard passed")


def test_phase_2a_mobile_two_step_sync_updates_persisted_report():
    import uuid
    import backend.ml.field_report_classifier as classifier_module

    class FakeRoadBlockSession:
        def get_inputs(self):
            return [type("Input", (), {"name": "input"})()]

        def run(self, *_args, **_kwargs):
            # High confidence for class 1 ('roadBlockage')
            return [np.array([[-1.0, 4.5, -1.0, -2.0]], dtype=np.float32)]

    orig_ensure = classifier_module._ensure_v2_ready
    orig_session = classifier_module._SESSION
    classifier_module._SESSION = None
    classifier_module._ensure_v2_ready = lambda: FakeRoadBlockSession()

    try:
        mobile_id = f"mob-sync-{uuid.uuid4().hex[:8]}"
        # Step 1: Mobile JSON upload without image
        step1 = client.post(
            "/api/reports/submit",
            json={
                "report_id": mobile_id,
                "hazard_type": "rainfall",
                "state": "uttarakhand",
                "zone_id": "zone-uk-01",
                "location": "Joshimath Bypass",
                "description": "Heavy rain and debris on highway.",
                "latitude": 30.5562,
                "longitude": 79.5644,
            },
        )
        assert step1.status_code == 200
        assert step1.json()["report_id"] == mobile_id
        assert step1.json()["hazard_type"] == "rainfall"

        # Step 2: Mobile calls /api/reports/classify with image
        buffer = BytesIO()
        Image.new("RGB", (64, 64), color=(90, 90, 90)).save(buffer, format="JPEG")
        step2 = client.post(
            "/api/reports/classify",
            data={
                "report_id": mobile_id,
                "hazard_type": "rainfall",
                "state": "uttarakhand",
                "zone_id": "zone-uk-01",
            },
            files={"image": ("road.jpg", buffer.getvalue(), "image/jpeg")},
        )
        assert step2.status_code == 200
        clf_data = step2.json()
        assert clf_data["predicted_class"] == "roadBlockage"
        assert clf_data["hazard_type"] == "rainfall"

        # Verify persisted DB row was updated with ONNX result while preserving hazardType and unverified status
        persisted = client.get(f"/api/reports/{mobile_id}").json()
        assert persisted["hazardType"] == "rainfall"
        assert persisted["predictedClass"] == "roadBlockage"
        assert persisted["aiClassificationStatus"] == "classified"
        assert persisted["isVerified"] is False
    finally:
        classifier_module._ensure_v2_ready = orig_ensure
        classifier_module._SESSION = orig_session

    print("[PASS] Phase 2A mobile two-step sync updates persisted report with ONNX classification without overwriting hazard_type")


def test_phase_2a_report_persists_when_classifier_unavailable():
    import uuid
    import backend.ml.field_report_classifier as classifier_module

    orig_ensure = classifier_module._ensure_v2_ready
    classifier_module._ensure_v2_ready = lambda: (_ for _ in ()).throw(
        RuntimeError("classification unavailable/error")
    )

    try:
        buffer = BytesIO()
        Image.new("RGB", (48, 48), color=(60, 100, 140)).save(buffer, format="JPEG")
        unavail_id = f"phase2a-unavail-{uuid.uuid4().hex[:8]}"

        res = client.post(
            "/api/reports/submit",
            data={
                "report_id": unavail_id,
                "hazard_type": "flood",
                "state": "sikkim",
                "zone_id": "zone-sk-01",
                "location": "Rangpo Bazar",
                "description": "Flash flood water rising near bridge abutment.",
                "latitude": "27.1764",
                "longitude": "88.5294",
            },
            files={"file": ("flood.jpg", buffer.getvalue(), "image/jpeg")},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["report_id"] == unavail_id
        assert data["hazard_type"] == "flood"
        assert data["predicted_class"] is None
        assert data["classification_status"] == "classification_unavailable"
        assert data["confidence"] is None
        assert data["verified"] is False

        fetched = client.get(f"/api/reports/{unavail_id}")
        assert fetched.status_code == 200
        row = fetched.json()
        assert row["hazardType"] == "flood"
        assert row["predictedClass"] is None
        assert row["aiClassificationStatus"] == "classification_unavailable"
        assert row["imageStorageKey"] is not None
    finally:
        classifier_module._ensure_v2_ready = orig_ensure

    print("[PASS] Phase 2A classification failure resilience: report and image persist truthfully when ONNX classifier is unavailable")


def test_phase_2a_duplicate_report_submission_is_idempotent():
    import uuid

    dup_id = f"phase2a-dup-{uuid.uuid4().hex[:8]}"
    payload = {
        "report_id": dup_id,
        "hazard_type": "roadBlockage",
        "state": "sikkim",
        "zone_id": "zone-sk-02",
        "location": "JN Road Km 18",
        "description": "Boulder blocking single lane on JN Road.",
        "latitude": 27.3516,
        "longitude": 88.6667,
    }

    first = client.post("/api/reports/submit", json=payload)
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["duplicate"] is False
    assert first_data["report_id"] == dup_id

    second = client.post("/api/reports/submit", json=payload)
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["duplicate"] is True
    assert second_data["report_id"] == dup_id
    assert second_data["code"] == first_data["code"]

    all_reports = client.get("/api/reports").json()
    matching = [r for r in all_reports if r["id"] == dup_id]
    assert len(matching) == 1
    print("[PASS] Phase 2A duplicate report submission is idempotent and prevents duplicate DB records")


def test_phase_2b_road_blockages_crud_and_citizen_vs_authority_separation():
    import uuid

    # 1. List road blockages
    res_list = client.get("/api/alerts/road-blockages?state=sikkim")
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) >= 2
    assert any(item["zone_id"] == "zone-sk-02" for item in items)

    # 2. Submit an unverified citizen roadBlockage report on zone-sk-02
    citizen_rep_id = f"phase2b-rb-{uuid.uuid4().hex[:8]}"
    rep_res = client.post(
        "/api/reports/submit",
        json={
            "report_id": citizen_rep_id,
            "hazard_type": "roadBlockage",
            "state": "sikkim",
            "zone_id": "zone-sk-02",
            "location": "JN Road Km 21",
            "description": "Rockfall blocking one lane near Kyongnosla.",
            "latitude": 27.3516,
            "longitude": 88.6667,
        },
    )
    assert rep_res.status_code == 200

    # Verify citizen report is listed as unverified on zone-sk-02 road-blockage record
    zone_rb = client.get("/api/zones/zone-sk-02/road-blockage")
    assert zone_rb.status_code == 200
    rb_data = zone_rb.json()
    assert rb_data["unverified_citizen_reports_count"] >= 1
    assert any(r["id"] == citizen_rep_id and r["verified"] is False for r in rb_data["citizen_reports"])

    # 3. Cycle through SINGLE_LANE, BLOCKED, CLEARING_IN_PROGRESS, OPEN
    for st in ("SINGLE_LANE", "BLOCKED", "CLEARING_IN_PROGRESS", "OPEN"):
        upd = client.put(
            "/api/alerts/road-blockages/zone-sk-02",
            json={
                "status": st,
                "source": "authority_verified",
                "verified": True,
                "assigned_unit_id": "tu-bro-02",
                "estimated_clearance_time": "1h 45m",
                "notes": f"Testing status {st}",
            },
        )
        assert upd.status_code == 200, upd.text
        upd_data = upd.json()
        assert upd_data["status"] == st
        assert upd_data["verified"] is True
        assert upd_data["verification_label"] == "AUTHORITY_VERIFIED"
        assert upd_data["assigned_unit_id"] == "tu-bro-02"
        assert upd_data["assigned_unit_name"] == "BRO Project Swastik Task Force"
        assert upd_data["estimated_clearance_time"] == "1h 45m"
        assert upd_data["updated_at"] is not None

    # 4. Citizen-sourced corridor status defaults to unverified
    cit_upd = client.put(
        "/api/alerts/road-blockages/zone-sk-02",
        json={"status": "SINGLE_LANE", "source": "citizen_report"},
    )
    assert cit_upd.status_code == 200
    assert cit_upd.json()["verified"] is False
    assert cit_upd.json()["verification_label"] == "CITIZEN_REPORTED_UNVERIFIED"

    # 5. Error cases: invalid status (422), unknown zone (404), unknown unit (404)
    bad_status = client.put("/api/alerts/road-blockages/zone-sk-02", json={"status": "DESTROYED"})
    assert bad_status.status_code == 422

    bad_zone = client.put("/api/alerts/road-blockages/zone-does-not-exist", json={"status": "OPEN"})
    assert bad_zone.status_code == 404

    bad_unit = client.put(
        "/api/alerts/road-blockages/zone-sk-02",
        json={"status": "BLOCKED", "assigned_unit_id": "unit-nonexistent"},
    )
    assert bad_unit.status_code == 404

    print("[PASS] Phase 2B road-blockage monitoring, status transitions, unit assignment, and citizen vs authority provenance passed")


def test_phase_2b_shelter_persistence_and_safe_occupancy_updates():
    # 1. List persisted shelters
    res = client.get("/api/alerts/shelters")
    assert res.status_code == 200
    shelters = res.json()
    assert len(shelters) >= 2
    sh01 = next((s for s in shelters if s["id"] == "sh-01"), None)
    assert sh01 is not None
    assert sh01["latitude"] is not None
    assert sh01["coordinatesVerified"] is False
    assert sh01["coordinateType"] == "approximate"

    orig_current = sh01["capacityCurrent"]
    orig_max = sh01["capacityMax"]
    orig_status = sh01["status"]

    try:
        # 2. Safe occupancy & status update
        upd = client.put(
            "/api/alerts/shelters/sh-01",
            json={"capacityCurrent": 450, "capacityMax": 600, "status": "STABLE"},
        )
        assert upd.status_code == 200, upd.text
        upd_data = upd.json()
        assert upd_data["capacityCurrent"] == 450
        assert upd_data["capacityMax"] == 600
        assert upd_data["occupancyPercent"] == 75
        assert upd_data["status"] == "STABLE"
        assert upd_data["updatedAt"] is not None

        # 3. Validation error cases
        neg_occ = client.put("/api/alerts/shelters/sh-01", json={"capacityCurrent": -5})
        assert neg_occ.status_code == 422

        over_occ = client.put("/api/alerts/shelters/sh-01", json={"capacityCurrent": 9999, "capacityMax": 600})
        assert over_occ.status_code == 422

        zero_max = client.put("/api/alerts/shelters/sh-01", json={"capacityCurrent": 0, "capacityMax": 0})
        assert zero_max.status_code == 422

        bad_status = client.put("/api/alerts/shelters/sh-01", json={"status": "INVALID_STATUS"})
        assert bad_status.status_code == 422

        not_found = client.put("/api/alerts/shelters/shelter-nonexistent", json={"capacityCurrent": 10})
        assert not_found.status_code == 404
    finally:
        client.put(
            "/api/alerts/shelters/sh-01",
            json={"capacityCurrent": orig_current, "capacityMax": orig_max, "status": orig_status},
        )

    print("[PASS] Phase 2B shelter persistence, coordinate provenance, safe occupancy updates, and validation guards passed")


def test_phase_2b_tactical_dispatch_and_simulation_flags():
    units_res = client.get("/api/alerts/units")
    assert units_res.status_code == 200
    units = units_res.json()
    assert len(units) >= 2

    # 1. Valid tactical unit dispatch
    disp = client.post(
        "/api/alerts/dispatch",
        json={
            "unit_id": "tu-ndrf-01",
            "destination": "NH-10 Km 38.4 Lower Singtam Slide",
            "status": "ON SCENE",
            "priority": "CRITICAL",
            "zone_id": "zone-sk-01",
        },
    )
    assert disp.status_code == 200, disp.text
    disp_data = disp.json()
    assert disp_data["status"] == "success"
    assert disp_data["simulated_external_uplink"] is True
    assert disp_data["unit"]["destination"] == "NH-10 Km 38.4 Lower Singtam Slide"
    assert disp_data["unit"]["status"] == "ON SCENE"
    assert disp_data["unit"]["assignedZoneId"] == "zone-sk-01"

    # 2. Siren trigger explicitly marks hardware activation as simulated
    siren_res = client.post("/api/alerts/siren", json={"corridor": "NH-10", "towers": 6, "stage": 3})
    assert siren_res.status_code == 200
    assert siren_res.json()["simulated"] is True

    # 3. Dispatch validation & error cases
    missing_unit = client.post(
        "/api/alerts/dispatch",
        json={"unit_id": "unit-unknown-999", "destination": "NH-10"},
    )
    assert missing_unit.status_code == 404

    empty_dest = client.post(
        "/api/alerts/dispatch",
        json={"unit_id": "tu-ndrf-01", "destination": "   "},
    )
    assert empty_dest.status_code == 422

    bad_priority = client.post(
        "/api/alerts/dispatch",
        json={"unit_id": "tu-ndrf-01", "destination": "NH-10", "priority": "SUPER_HIGH"},
    )
    assert bad_priority.status_code == 422

    bad_unit_status = client.post(
        "/api/alerts/dispatch",
        json={"unit_id": "tu-ndrf-01", "destination": "NH-10", "status": "TELEPORTING"},
    )
    assert bad_unit_status.status_code == 422

    print("[PASS] Phase 2B tactical unit dispatch, audit logging, validation guards, and truthful simulation flags passed")


if __name__ == "__main__":
    print("\nRunning LandslideGuard Backend API Tests...\n")
    class DummyMonkeypatch:
        def setattr(self, target, name, value):
            setattr(target, name, value)

    mp = DummyMonkeypatch()
    test_health()
    test_hazard_zones()
    test_susceptibility_calculation()
    test_predict_lstm()
    test_crowdsource_reports()
    test_report_submission_and_cv()
    test_sensor_nodes()
    test_cap_alert()
    test_live_weather()
    test_sms_broadcast()
    test_ml_predict()
    test_model_info()
    test_predict_invalid_rainfall()
    test_ml_metrics()
    test_ml_comparison()
    test_ml_datasets()
    test_gis_historical_training_events()
    test_gis_zone_ml_risk()
    test_gis_ml_heatmap_points()
    test_official_earthquake_contract()
    test_earthquake_parser_and_safe_fallback()
    test_chatbot()
    test_chatbot_all_language_responses()
    test_chatbot_navigation_commands()
    test_field_classifier_ignores_hazard_type_override_for_low_confidence(mp)
    test_field_classifier_preserves_explicit_rainfall_selection(mp)
    test_sqlite_schema_migration_preserves_existing_records()
    test_phase_2a_report_persistence_and_metadata_preservation()
    test_phase_2a_mobile_two_step_sync_updates_persisted_report()
    test_phase_2a_report_persists_when_classifier_unavailable()
    test_phase_2a_duplicate_report_submission_is_idempotent()
    test_phase_2b_road_blockages_crud_and_citizen_vs_authority_separation()
    test_phase_2b_shelter_persistence_and_safe_occupancy_updates()
    test_phase_2b_tactical_dispatch_and_simulation_flags()
    print("\nAll 34 Slope Signal Backend API tests passed successfully!\n")
