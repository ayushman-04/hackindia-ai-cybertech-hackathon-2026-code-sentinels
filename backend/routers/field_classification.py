"""Field report classifier API surface."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.models import CrowdsourceReportModel
from backend.ml.field_report_classifier import classify_field_image

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _find_report(db: Session, report_id: str) -> Optional[CrowdsourceReportModel]:
    cleaned = "".join(c for c in str(report_id or "").strip() if c.isalnum() or c in ("-", "_"))
    if not cleaned:
        return None
    return (
        db.query(CrowdsourceReportModel)
        .filter(
            (CrowdsourceReportModel.id == cleaned)
            | (CrowdsourceReportModel.clientReportId == cleaned)
        )
        .first()
    )


@router.post("/classify")
async def classify_report(
    report_id: str = Form(...),
    image: UploadFile = File(...),
    hazard_type: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    state: Optional[str] = Form(None),
    zone_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    timestamp: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Classify field evidence only; this never calls location-risk inference."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="image must be an image upload")
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="image is empty")

    existing = _find_report(db, report_id)

    try:
        result = classify_field_image(report_id, payload, hazard_type)
        if existing is not None:
            if hazard_type and not existing.hazardType:
                existing.hazardType = hazard_type.strip()
            if zone_id and not existing.zoneId:
                existing.zoneId = zone_id.strip()
            if state and not existing.state:
                existing.state = state.strip().lower()
            if timestamp and not existing.capturedAt:
                existing.capturedAt = timestamp
            existing.predictedClass = result["predicted_class"]
            existing.classification = result["predicted_class"]
            existing.aiClassificationStatus = "classified"
            existing.classificationSource = "onnx_v2"
            existing.confidence = float(result["confidence"])
            existing.aiConfidence = float(result["confidence"])
            existing.classificationSeverity = result["severity"]
            existing.modelVersion = result["model_version"]
            existing.processedAt = result["processed_at"]
            existing.cvRisk = f"{round(float(result['confidence']) * 100, 1)}%"
            existing.cvLabel = f"ONNX v2 Predicted: {result['predicted_class']} ({result['severity']})"
            existing.cvModel = f"YOLO-classification-ONNX ({result['model_version']})"
            db.commit()
        return result
    except ValueError as exc:
        if existing is not None:
            existing.aiClassificationStatus = "classification_failed"
            existing.classificationSource = "classification_failed"
            existing.processedAt = datetime.now(timezone.utc).isoformat()
            db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if existing is not None:
            existing.aiClassificationStatus = "classification_unavailable"
            existing.classificationSource = "classification_unavailable"
            existing.processedAt = datetime.now(timezone.utc).isoformat()
            db.commit()
        raise HTTPException(status_code=503, detail="classification unavailable/error") from exc
    except Exception as exc:
        if existing is not None:
            existing.aiClassificationStatus = "classification_failed"
            existing.classificationSource = "classification_failed"
            existing.processedAt = datetime.now(timezone.utc).isoformat()
            db.commit()
        raise HTTPException(status_code=500, detail="field image classification failed") from exc

