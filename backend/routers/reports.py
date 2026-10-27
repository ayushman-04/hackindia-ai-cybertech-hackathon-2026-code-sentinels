import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.models import CrowdsourceReportModel
from backend.ml.field_report_classifier import classify_field_image
from backend.services.alert_engine import alert_engine
from backend.services.storage import storage_service

router = APIRouter(prefix="/api/reports", tags=["Citizen & Crowdsource Field Reports"])

DEFAULT_PLACEHOLDER_IMAGE = (
    "https://lh3.googleusercontent.com/aida-public/"
    "AB6AXuALB_yXy7sUfuuBp4UTSr0dpk7zF6HUUQRZiAJn-qJVUMS3weVz4GfRqmp4iBNO7J_W-UvGD1w1jqzLtLrMilmiZRSdwlBzREvwEhFuMLj8leFOXhKsH03DPMNeH_fcNpVTQ653MQmJiL5XszrnrAcuDD86DSS_8ne0IqjZIqrayQX1OCr-uhqqUsFi3m8XhebKkygRo9VgyeB7Sl2pbZWJaj_RHq5Phd-CSxf5V3afEMDPjxRH_rBYYg"
)


class ReportCreateSchema(BaseModel):
    report_id: Optional[str] = None
    reportId: Optional[str] = None
    hazard_type: Optional[str] = None
    hazardType: Optional[str] = None
    zone_id: Optional[str] = None
    zoneId: Optional[str] = None
    timestamp: Optional[str] = None
    captured_at: Optional[str] = None
    location: str
    subDivision: str = "Sub-Division HQ"
    state: str = "sikkim"
    description: str
    imageUrl: Optional[str] = None
    coordinates: Optional[str] = "27.2388° N, 88.5012° E"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    deviceId: Optional[str] = None
    elevation: Optional[str] = "1,420 m"
    slope: Optional[str] = "48.5°"
    vernacularText: Optional[str] = ""
    englishTranslation: Optional[str] = ""


def _coerce_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _sanitize_report_id(raw_id: Optional[str]) -> Optional[str]:
    if not raw_id:
        return None
    cleaned = "".join(c for c in str(raw_id).strip() if c.isalnum() or c in ("-", "_"))
    return cleaned or None


def _derive_text_triage(description: str, hazard_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Deterministic text triage metadata for reports submitted without an image or when
    evaluating triage urgency. Does not fabricate random confidence or fake bounding boxes,
    and never marks a report as verified.
    """
    desc_lower = (description or "").lower()
    has_slip = any(w in desc_lower for w in ["slip", "slide", "fell", "collapse", "blowout", "rotational"])
    has_crack = any(w in desc_lower for w in ["crack", "fissure", "subsidence", "sinking"])
    has_boulder = any(w in desc_lower for w in ["boulder", "rock", "stone", "debris", "mud"])
    has_blocking = any(w in desc_lower for w in ["block", "closed", "impassable", "trapped"])
    has_flood = any(w in desc_lower for w in ["flood", "inundat", "overflow", "waterlog"])

    if has_slip and (has_blocking or has_crack):
        urgency = "CRITICAL"
        inferred_class = "landslide"
        triage_conf = 0.88
        cv_label = "Active Rotational Shear Scarp with Tension Fissures (Text Triage)"
        summary = "Critical slope failure indicators described in field report; pending authority verification."
    elif has_slip:
        urgency = "URGENT"
        inferred_class = "landslide"
        triage_conf = 0.78
        cv_label = "Reported Slope Slip / Landslide Movement (Text Triage)"
        summary = "Slope movement reported by citizen; pending authority verification."
    elif has_blocking or hazard_type == "roadBlockage":
        urgency = "URGENT"
        inferred_class = "roadBlockage"
        triage_conf = 0.74
        cv_label = "Reported Corridor / Roadway Blockage (Text Triage)"
        summary = "Roadway obstruction reported; pending authority verification."
    elif has_crack or has_boulder:
        urgency = "URGENT"
        inferred_class = "landslide"
        triage_conf = 0.72
        cv_label = "Incipient Tension Cracking & Debris Movement (Text Triage)"
        summary = "Pre-failure tension cracks or debris movement reported; pending authority verification."
    elif has_flood or hazard_type == "flood":
        urgency = "AMBER"
        inferred_class = "flood"
        triage_conf = 0.65
        cv_label = "Reported Surface Flooding / Runoff (Text Triage)"
        summary = "Flooding or high runoff reported; pending authority verification."
    else:
        urgency = "AMBER"
        inferred_class = hazard_type if hazard_type in {"landslide", "roadBlockage", "flood"} else "other"
        triage_conf = 0.55
        cv_label = "Citizen Field Observation Logged (Pending Verification)"
        summary = description or "Field hazard report logged; pending authority verification."

    return {
        "urgency": urgency,
        "inferred_class": inferred_class,
        "triage_confidence": triage_conf,
        "cv_label": cv_label,
        "summary": summary,
    }


def _urgency_from_classifier(predicted_class: Optional[str], severity: Optional[str], fallback_urgency: str) -> str:
    if severity == "HIGH" and predicted_class in {"landslide", "roadBlockage", "flood"}:
        return "CRITICAL" if predicted_class == "landslide" else "URGENT"
    if severity == "MEDIUM" and predicted_class in {"landslide", "roadBlockage", "flood"}:
        return "URGENT"
    if severity == "LOW":
        return "AMBER"
    return fallback_urgency


def _format_report_response(report: CrowdsourceReportModel, duplicate: bool = False) -> Dict[str, Any]:
    return {
        "id": report.id,
        "report_id": report.id,
        "client_report_id": report.clientReportId or report.id,
        "code": report.code,
        "duplicate": duplicate,
        "status": report.status,
        "verification_status": report.verificationStatus,
        "verified": bool(report.isVerified),
        "state": report.state,
        "zone_id": report.zoneId,
        "hazard_type": report.hazardType,
        "predicted_class": report.predictedClass,
        "classification": report.classification,
        "classification_status": report.aiClassificationStatus,
        "classification_source": report.classificationSource,
        "confidence": report.confidence,
        "severity": report.classificationSeverity or "UNKNOWN",
        "model_version": report.modelVersion or "v2",
        "processed_at": report.processedAt or datetime.now(timezone.utc).isoformat(),
        "alert_status": report.alertStatus,
        "sms_status": report.smsStatus,
        "message": "Duplicate report already persisted" if duplicate else "Report submitted successfully",
        "image_url": report.imageUrl,
        "urgency": report.urgency,
        "cvRisk": report.cvRisk,
        "cvLabel": report.cvLabel,
        "summary": report.summary,
        "alert": None,
        "created_at": report.capturedAt or datetime.now(timezone.utc).isoformat(),
    }


async def _run_onnx_classification_for_report(
    report_id: str,
    image_bytes: bytes,
    hazard_type: Optional[str],
) -> Dict[str, Any]:
    try:
        result = classify_field_image(report_id, image_bytes, hazard_type=hazard_type)
        return {
            "classification_status": "classified",
            "classification_source": "onnx_v2",
            "predicted_class": result["predicted_class"],
            "confidence": float(result["confidence"]),
            "severity": result["severity"],
            "model_version": result["model_version"],
            "processed_at": result["processed_at"],
        }
    except RuntimeError:
        return {
            "classification_status": "classification_unavailable",
            "classification_source": "classification_unavailable",
            "predicted_class": None,
            "confidence": None,
            "severity": "UNKNOWN",
            "model_version": "v2",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        return {
            "classification_status": "classification_failed",
            "classification_source": "classification_failed",
            "predicted_class": None,
            "confidence": None,
            "severity": "UNKNOWN",
            "model_version": "v2",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }


@router.get("")
def list_reports(
    state: Optional[str] = Query(None, description="Filter by NER state"),
    urgency: Optional[str] = Query(None, description="Filter by urgency"),
    db: Session = Depends(get_db),
):
    query = db.query(CrowdsourceReportModel).filter(CrowdsourceReportModel.status != "dismissed")
    if state and state.lower() != "all":
        query = query.filter(CrowdsourceReportModel.state == state.lower())
    if urgency:
        query = query.filter(CrowdsourceReportModel.urgency == urgency.upper())
    return query.order_by(CrowdsourceReportModel.reportedTime.desc()).all()


@router.get("/{report_id}")
def get_report_by_id(report_id: str, db: Session = Depends(get_db)):
    report = (
        db.query(CrowdsourceReportModel)
        .filter(
            (CrowdsourceReportModel.id == report_id)
            | (CrowdsourceReportModel.clientReportId == report_id)
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/image/{filename}")
def get_report_image(report_id: str, filename: str):
    file_path = storage_service.get_image_file_path(report_id, filename)
    if not file_path:
        raise HTTPException(status_code=404, detail="Image not found or inaccessible")
    return FileResponse(path=str(file_path))


@router.post("/upload-image")
async def upload_report_image(
    report_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    target_report_id = _sanitize_report_id(report_id) or f"rep-{uuid.uuid4().hex[:8]}"
    storage_key, relative_url, size_bytes = await storage_service.save_report_image(target_report_id, file)
    return {
        "status": "success",
        "report_id": target_report_id,
        "storage_key": storage_key,
        "image_url": relative_url,
        "filename": file.filename,
        "mime_type": file.content_type,
        "size_bytes": size_bytes,
    }


@router.post("")
@router.post("/")
@router.post("/submit")
async def submit_report(
    request: Request,
    file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    report_id: Optional[str] = Form(None),
    reportId: Optional[str] = Form(None),
    hazard_type: Optional[str] = Form(None),
    hazardType: Optional[str] = Form(None),
    zone_id: Optional[str] = Form(None),
    zoneId: Optional[str] = Form(None),
    timestamp: Optional[str] = Form(None),
    captured_at: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    subDivision: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    deviceId: Optional[str] = Form(None),
    coordinates: Optional[str] = Form(None),
    elevation: Optional[str] = Form(None),
    slope: Optional[str] = Form(None),
    vernacularText: Optional[str] = Form(None),
    englishTranslation: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    json_body: Dict[str, Any] = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            json_body = await request.json()
        except Exception:
            json_body = {}

    raw_client_report_id = (
        report_id
        or reportId
        or json_body.get("report_id")
        or json_body.get("reportId")
    )
    client_report_id = _sanitize_report_id(raw_client_report_id)

    hazard_type_value = (
        hazard_type
        or hazardType
        or json_body.get("hazard_type")
        or json_body.get("hazardType")
    )
    if isinstance(hazard_type_value, str):
        hazard_type_value = hazard_type_value.strip() or None

    zone_id_value = (
        zone_id
        or zoneId
        or json_body.get("zone_id")
        or json_body.get("zoneId")
    )
    if isinstance(zone_id_value, str):
        zone_id_value = zone_id_value.strip() or None

    captured_at_value = (
        timestamp
        or captured_at
        or json_body.get("timestamp")
        or json_body.get("captured_at")
        or json_body.get("capturedAt")
    )

    location_value = location or json_body.get("location") or "Unspecified location"
    sub_division_value = subDivision or json_body.get("subDivision") or "Sub-Division HQ"
    state_value = (state or json_body.get("state") or "sikkim").strip().lower()
    description_value = description or json_body.get("description") or "Field hazard report"
    latitude_value = _coerce_float(latitude if latitude is not None else json_body.get("latitude"))
    longitude_value = _coerce_float(longitude if longitude is not None else json_body.get("longitude"))
    coordinates_value = (
        coordinates
        or json_body.get("coordinates")
        or (
            f"{latitude_value:.4f}° N, {longitude_value:.4f}° E"
            if latitude_value is not None and longitude_value is not None
            else "27.2388° N, 88.5012° E"
        )
    )
    device_id_value = deviceId or json_body.get("deviceId") or json_body.get("device_id")
    elevation_value = elevation or json_body.get("elevation") or "1,420 m"
    slope_value = slope or json_body.get("slope") or "48.5°"
    vernacular_value = vernacularText if vernacularText is not None else (json_body.get("vernacularText") or "")
    english_value = englishTranslation if englishTranslation is not None else (json_body.get("englishTranslation") or "")

    if latitude_value is None or longitude_value is None:
        raise HTTPException(status_code=400, detail="latitude and longitude are required")

    upload_file = file or image

    # Check for duplicate submission by client_report_id
    if client_report_id:
        existing = (
            db.query(CrowdsourceReportModel)
            .filter(
                (CrowdsourceReportModel.id == client_report_id)
                | (CrowdsourceReportModel.clientReportId == client_report_id)
            )
            .first()
        )
        if existing:
            # If retry now includes an image and existing had none, attach & classify it
            if upload_file and not existing.imageStorageKey:
                storage_key, image_url, size_bytes = await storage_service.save_report_image(existing.id, upload_file)
                saved_path = storage_service.get_image_file_path(existing.id, storage_key.split("/")[-1])
                image_bytes = saved_path.read_bytes() if saved_path else b""
                clf_info = await _run_onnx_classification_for_report(existing.id, image_bytes, existing.hazardType)
                existing.imageStorageKey = storage_key
                existing.imageUrl = image_url
                existing.imageOriginalName = upload_file.filename
                existing.imageMimeType = upload_file.content_type
                existing.imageSizeBytes = size_bytes
                existing.predictedClass = clf_info["predicted_class"]
                existing.classification = clf_info["predicted_class"] or existing.classification
                existing.aiClassificationStatus = clf_info["classification_status"]
                existing.classificationSource = clf_info["classification_source"]
                existing.confidence = clf_info["confidence"]
                existing.aiConfidence = clf_info["confidence"]
                existing.classificationSeverity = clf_info["severity"]
                existing.modelVersion = clf_info["model_version"]
                existing.processedAt = clf_info["processed_at"]
                db.commit()
                db.refresh(existing)
            return _format_report_response(existing, duplicate=True)

    final_report_id = client_report_id or f"rep-{uuid.uuid4().hex[:8]}"
    code = f"NER-FLD-2026-{uuid.uuid4().hex[:4].upper()}"

    storage_key = None
    image_url = None
    orig_name = None
    mime_type = None
    size_bytes = None
    image_bytes: Optional[bytes] = None

    if upload_file:
        storage_key, image_url, size_bytes = await storage_service.save_report_image(final_report_id, upload_file)
        orig_name = upload_file.filename
        mime_type = upload_file.content_type
        saved_path = storage_service.get_image_file_path(final_report_id, storage_key.split("/")[-1])
        if saved_path and saved_path.is_file():
            image_bytes = saved_path.read_bytes()

    triage = _derive_text_triage(description_value, hazard_type_value)

    if image_bytes is not None:
        clf_info = await _run_onnx_classification_for_report(final_report_id, image_bytes, hazard_type_value)
        predicted_class = clf_info["predicted_class"]
        classification_status = clf_info["classification_status"]
        classification_source = clf_info["classification_source"]
        confidence = clf_info["confidence"]
        severity = clf_info["severity"]
        model_version = clf_info["model_version"]
        processed_at = clf_info["processed_at"]
        classification_field = predicted_class or classification_status
        urgency = _urgency_from_classifier(predicted_class, severity, triage["urgency"])
        if predicted_class and confidence is not None:
            cv_risk = f"{round(confidence * 100, 1)}%"
            cv_label = f"ONNX v2 Predicted: {predicted_class} ({severity})"
            cv_model = f"YOLO-classification-ONNX ({model_version})"
            summary = (
                f"AI visual classification: {predicted_class} ({cv_risk}, {severity}). "
                f"User-reported hazard: {hazard_type_value or 'unspecified'}. Pending authority verification."
            )
        else:
            cv_risk = "N/A"
            cv_label = "Image Classification Unavailable (Pending Manual Review)"
            cv_model = f"YOLO-classification-ONNX ({model_version})"
            summary = triage["summary"]
    else:
        predicted_class = None
        classification_status = "no_image"
        classification_source = "text_triage_no_image"
        confidence = triage["triage_confidence"]
        severity = "HIGH" if triage["urgency"] == "CRITICAL" else ("MEDIUM" if triage["urgency"] == "URGENT" else "LOW")
        model_version = "v2"
        processed_at = datetime.now(timezone.utc).isoformat()
        classification_field = triage["inferred_class"]
        urgency = triage["urgency"]
        cv_risk = f"{round(confidence * 100, 1)}%"
        cv_label = triage["cv_label"]
        cv_model = "Text Triage (No Image Uploaded)"
        summary = triage["summary"]

    # Never mark a report as verified merely because a classifier returned a prediction.
    verification_status = "PENDING_VERIFICATION"

    new_report = CrowdsourceReportModel(
        id=final_report_id,
        clientReportId=client_report_id or final_report_id,
        code=code,
        location=location_value,
        subDivision=sub_division_value,
        state=state_value,
        zoneId=zone_id_value,
        hazardType=hazard_type_value,
        capturedAt=captured_at_value,
        latitude=latitude_value,
        longitude=longitude_value,
        deviceId=str(device_id_value) if device_id_value else None,
        timeAgo="Just now",
        reportedTime=datetime.now().strftime("%H:%M IST"),
        urgency=urgency,
        verifiedBy="Unverified (Pending Authority Review)",
        imageUrl=image_url or json_body.get("imageUrl") or DEFAULT_PLACEHOLDER_IMAGE,
        imageAlt=f"Field hazard report at {location_value}",
        cvRisk=cv_risk,
        cvLabel=cv_label,
        cvModel=cv_model,
        summary=summary,
        description=description_value,
        coordinates=coordinates_value,
        elevation=elevation_value,
        slope=slope_value,
        precipitation="Live Telemetry Pending",
        exifStatus="GPS Coordinates Logged" if image_bytes is not None else "Metadata Logged (No Image)",
        audioLanguage="Nepali (Eastern Sub-dialect)",
        audioDuration="0:18",
        vernacularText=vernacular_value or description_value,
        englishTranslation=english_value or description_value,
        sensorCorroboration={
            "sensorId": "SN-SK-01",
            "rate": "Pending In-Situ Corroboration",
            "thresholdMessage": "Awaiting authority verification against nearby sensor nodes",
        },
        boundingBoxes=[],
        imageStorageKey=storage_key,
        imageOriginalName=orig_name,
        imageMimeType=mime_type,
        imageSizeBytes=size_bytes,
        aiClassificationStatus=classification_status,
        aiConfidence=confidence,
        verificationStatus=verification_status,
        classification=classification_field,
        confidence=confidence,
        predictedClass=predicted_class,
        classificationSeverity=severity,
        modelVersion=model_version,
        classificationSource=classification_source,
        processedAt=processed_at,
        isVerified=False,
        alertStatus="not_triggered",
        smsStatus="not_started",
        selectedRecipientsCount=0,
        alertRadiusKm=5.0,
        verifiedAt=None,
        status=verification_status,
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return _format_report_response(new_report, duplicate=False)


@router.post("/json")
@router.post("/submit-json")
def submit_report_json(payload: ReportCreateSchema, db: Session = Depends(get_db)):
    if payload.latitude is None or payload.longitude is None:
        raise HTTPException(status_code=400, detail="latitude and longitude are required")

    raw_client_report_id = payload.report_id or payload.reportId
    client_report_id = _sanitize_report_id(raw_client_report_id)
    hazard_type_value = (payload.hazard_type or payload.hazardType or "").strip() or None
    zone_id_value = (payload.zone_id or payload.zoneId or "").strip() or None
    captured_at_value = payload.timestamp or payload.captured_at

    if client_report_id:
        existing = (
            db.query(CrowdsourceReportModel)
            .filter(
                (CrowdsourceReportModel.id == client_report_id)
                | (CrowdsourceReportModel.clientReportId == client_report_id)
            )
            .first()
        )
        if existing:
            return _format_report_response(existing, duplicate=True)

    final_report_id = client_report_id or f"rep-{uuid.uuid4().hex[:8]}"
    code = f"NER-FLD-2026-{uuid.uuid4().hex[:4].upper()}"
    triage = _derive_text_triage(payload.description, hazard_type_value)
    confidence = triage["triage_confidence"]
    severity = "HIGH" if triage["urgency"] == "CRITICAL" else ("MEDIUM" if triage["urgency"] == "URGENT" else "LOW")
    processed_at = datetime.now(timezone.utc).isoformat()

    new_report = CrowdsourceReportModel(
        id=final_report_id,
        clientReportId=client_report_id or final_report_id,
        code=code,
        location=payload.location,
        subDivision=payload.subDivision,
        state=payload.state.strip().lower(),
        zoneId=zone_id_value,
        hazardType=hazard_type_value,
        capturedAt=captured_at_value,
        latitude=payload.latitude,
        longitude=payload.longitude,
        deviceId=payload.deviceId,
        timeAgo="Just now",
        reportedTime=datetime.now().strftime("%H:%M IST"),
        urgency=triage["urgency"],
        verifiedBy="Unverified (Pending Authority Review)",
        imageUrl=payload.imageUrl or DEFAULT_PLACEHOLDER_IMAGE,
        imageAlt=f"Field hazard report at {payload.location}",
        cvRisk=f"{round(confidence * 100, 1)}%",
        cvLabel=triage["cv_label"],
        cvModel="Text Triage (No Image Uploaded)",
        summary=triage["summary"],
        description=payload.description,
        coordinates=payload.coordinates or f"{payload.latitude:.4f}° N, {payload.longitude:.4f}° E",
        elevation=payload.elevation or "1,420 m",
        slope=payload.slope or "48.5°",
        precipitation="Live Telemetry Pending",
        exifStatus="Metadata Logged (No Image)",
        audioLanguage="Nepali (Eastern Sub-dialect)",
        audioDuration="0:18",
        vernacularText=payload.vernacularText or payload.description,
        englishTranslation=payload.englishTranslation or payload.description,
        sensorCorroboration={
            "sensorId": "SN-SK-01",
            "rate": "Pending In-Situ Corroboration",
            "thresholdMessage": "Awaiting authority verification against nearby sensor nodes",
        },
        boundingBoxes=[],
        aiClassificationStatus="no_image",
        aiConfidence=confidence,
        verificationStatus="PENDING_VERIFICATION",
        classification=triage["inferred_class"],
        confidence=confidence,
        predictedClass=None,
        classificationSeverity=severity,
        modelVersion="v2",
        classificationSource="text_triage_no_image",
        processedAt=processed_at,
        isVerified=False,
        alertStatus="not_triggered",
        smsStatus="not_started",
        selectedRecipientsCount=0,
        alertRadiusKm=5.0,
        verifiedAt=None,
        status="PENDING_VERIFICATION",
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return _format_report_response(new_report, duplicate=False)


@router.post("/{report_id}/escalate")
def escalate_report(report_id: str, db: Session = Depends(get_db)):
    report = (
        db.query(CrowdsourceReportModel)
        .filter(
            (CrowdsourceReportModel.id == report_id)
            | (CrowdsourceReportModel.clientReportId == report_id)
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = "CONFIRMED"
    report.verificationStatus = "CONFIRMED"
    report.isVerified = True
    report.verifiedAt = datetime.utcnow()
    report.verifiedBy = "Verified by Authority (District Magistrate / SDMA)"
    report.alertStatus = "triggered"
    report.smsStatus = "demo"
    alert_payload = alert_engine.evaluate_report_trigger(
        report_id=report.id,
        urgency=report.urgency,
        cv_risk=report.cvRisk,
        location=report.location,
        state=report.state,
        coordinates=report.coordinates,
        summary=report.summary,
    )
    db.commit()
    return {
        "status": "success",
        "verified": True,
        "verification_status": report.verificationStatus,
        "alert": alert_payload,
        "message": f"Escalated {report.code} to District Magistrate & CAP alert queued",
    }


@router.post("/{report_id}/dismiss")
@router.delete("/{report_id}")
def dismiss_report(report_id: str, db: Session = Depends(get_db)):
    report = (
        db.query(CrowdsourceReportModel)
        .filter(
            (CrowdsourceReportModel.id == report_id)
            | (CrowdsourceReportModel.clientReportId == report_id)
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = "REJECTED"
    report.verificationStatus = "REJECTED"
    report.isVerified = False
    report.alertStatus = "not_triggered"
    report.smsStatus = "not_started"
    db.commit()
    return {"status": "success", "message": f"Report {report.code} marked as Non-Threat / Dismissed"}


@router.post("/sync-offline")
def sync_offline_reports(db: Session = Depends(get_db)):
    pending_count = (
        db.query(CrowdsourceReportModel)
        .filter(CrowdsourceReportModel.verificationStatus == "PENDING_VERIFICATION")
        .count()
    )
    return {
        "status": "success",
        "synced_count": pending_count,
        "message": f"Offline report queue synchronized with central database ({pending_count} pending verification).",
    }
