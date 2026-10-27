import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.models import (
    AuditLogModel,
    CapAlertModel,
    CrowdsourceReportModel,
    HazardZoneModel,
    ReliefShelterModel,
    TacticalUnitModel,
)

router = APIRouter(prefix="/api/alerts", tags=["Alert Engine & Tactical Dispatch"])

VALID_ROAD_BLOCKAGE_STATUSES = {"OPEN", "SINGLE_LANE", "BLOCKED", "CLEARING_IN_PROGRESS"}
VALID_ROAD_BLOCKAGE_SOURCES = {"authority_verified", "citizen_report", "authority_telemetry"}
VALID_SHELTER_STATUSES = {"AVAILABLE", "STABLE", "CRITICAL", "FULL", "CLOSED"}
VALID_UNIT_STATUSES = {"EN ROUTE", "ON SCENE", "ACTIVE", "DEBRIS CLEARING", "STANDBY"}
VALID_DISPATCH_PRIORITIES = {"CRITICAL", "URGENT", "ROUTINE"}


class DispatchRequest(BaseModel):
    unit_id: str
    destination: str
    priority: str = "URGENT"
    status: Optional[str] = "EN ROUTE"
    eta: Optional[str] = None
    zone_id: Optional[str] = None


class SirenTriggerRequest(BaseModel):
    corridor: str
    towers: int = 6
    stage: int = 3


class RoadBlockageUpdateRequest(BaseModel):
    status: str
    source: Optional[str] = "authority_verified"
    verified: Optional[bool] = None
    assigned_unit_id: Optional[str] = None
    estimated_clearance_time: Optional[str] = None
    notes: Optional[str] = None


class ShelterUpdateRequest(BaseModel):
    capacityCurrent: Optional[int] = None
    capacityMax: Optional[int] = None
    status: Optional[str] = None
    rationsDays: Optional[str] = None
    gensetStatus: Optional[str] = None
    waterSupply: Optional[str] = None
    medicalActive: Optional[bool] = None


def serialize_road_blockage(zone: HazardZoneModel, db: Session) -> Dict[str, Any]:
    unit = None
    if zone.assignedUnitId:
        unit = (
            db.query(TacticalUnitModel)
            .filter(TacticalUnitModel.id == zone.assignedUnitId)
            .first()
        )

    # Find citizen roadBlockage reports matching this zone or state
    reports_query = (
        db.query(CrowdsourceReportModel)
        .filter(CrowdsourceReportModel.status != "REJECTED")
        .filter(CrowdsourceReportModel.status != "dismissed")
        .filter(
            (CrowdsourceReportModel.hazardType == "roadBlockage")
            | (CrowdsourceReportModel.predictedClass == "roadBlockage")
            | (CrowdsourceReportModel.classification == "roadBlockage")
        )
    )
    zone_reports = [
        r
        for r in reports_query.all()
        if (r.zoneId and r.zoneId == zone.id)
        or (not r.zoneId and r.state and r.state.lower() == zone.state.lower())
    ]

    citizen_reports = []
    verified_citizen_count = 0
    unverified_citizen_count = 0
    for r in zone_reports:
        is_ver = bool(r.isVerified) or r.verificationStatus == "CONFIRMED"
        if is_ver:
            verified_citizen_count += 1
        else:
            unverified_citizen_count += 1
        citizen_reports.append(
            {
                "id": r.id,
                "code": r.code,
                "location": r.location,
                "hazard_type": r.hazardType,
                "predicted_class": r.predictedClass,
                "verified": is_ver,
                "verification_status": r.verificationStatus,
                "reported_time": r.reportedTime,
                "description": r.description,
            }
        )

    status_val = (zone.roadBlockageStatus or "OPEN").upper()
    source_val = zone.roadBlockageSource or "authority_telemetry"
    is_verified = True if zone.roadBlockageVerified is None else bool(zone.roadBlockageVerified)

    return {
        "zone_id": zone.id,
        "zone_name": zone.name,
        "sub_division": zone.subDivision,
        "corridor": zone.corridor,
        "highway_segment": zone.highwaySegment,
        "bridges_exposed": zone.bridgesExposed,
        "state": zone.state,
        "coords": zone.coords,
        "status": status_val,
        "source": source_val,
        "verified": is_verified,
        "verification_label": (
            "AUTHORITY_VERIFIED" if is_verified else "CITIZEN_REPORTED_UNVERIFIED"
        ),
        "updated_at": zone.roadBlockageUpdatedAt,
        "assigned_unit_id": zone.assignedUnitId,
        "assigned_unit_name": unit.name if unit else None,
        "assigned_unit_status": unit.status if unit else None,
        "estimated_clearance_time": zone.estimatedClearanceTime,
        "notes": zone.blockageNotes,
        "unverified_citizen_reports_count": unverified_citizen_count,
        "verified_citizen_reports_count": verified_citizen_count,
        "citizen_reports": citizen_reports,
    }


@router.get("/cap")
def get_cap_alert():
    """
    Returns latest Common Alerting Protocol (CAP 1.2) alert in structured JSON and XML representation.
    """
    sent_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+05:30")
    cap_json = {
        "identifier": f"IN-GSI-LEWS-NER-{datetime.utcnow().strftime('%Y%m%d')}-0092",
        "sender": "lews.gsi.gov.in/ner-disaster-command",
        "sent": sent_iso,
        "status": "Actual",
        "msgType": "Alert",
        "scope": "Public",
        "category": "Geo",
        "event": "Critical Slope Debris Flow Imminent",
        "urgency": "Immediate",
        "severity": "Extreme",
        "certainty": "Observed",
        "headline": "MANDATORY EVACUATION: NH-10 KM 34-42 TEESTA BASIN CORRIDOR",
        "description": "Borehole piezometers SN-SK-01 breach 284 kPa limit. Shear creep exceeds 14.2 mm/hr. Deep-seated rotational slide failure expected within 3h 45m.",
        "instruction": "All civilian traffic diverted at Rangpo Checkpost. Immediate evacuation of Lower Singtam riverbank settlements to designated relief shelters.",
        "areaDesc": "NH-10 Km 34.2 to 41.8, Lower Singtam, Mangan Sub-Division, Sikkim",
        "circle": "27.5312,88.5134,5.0"
    }

    raw_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>{cap_json['identifier']}</identifier>
  <sender>{cap_json['sender']}</sender>
  <sent>{cap_json['sent']}</sent>
  <status>{cap_json['status']}</status>
  <msgType>{cap_json['msgType']}</msgType>
  <scope>{cap_json['scope']}</scope>
  <info>
    <category>{cap_json['category']}</category>
    <event>{cap_json['event']}</event>
    <urgency>{cap_json['urgency']}</urgency>
    <severity>{cap_json['severity']}</severity>
    <certainty>{cap_json['certainty']}</certainty>
    <headline>{cap_json['headline']}</headline>
    <description>{cap_json['description']}</description>
    <instruction>{cap_json['instruction']}</instruction>
    <area>
      <areaDesc>{cap_json['areaDesc']}</areaDesc>
      <circle>{cap_json['circle']}</circle>
    </area>
  </info>
</alert>"""

    return {
        "alert": cap_json,
        "raw_xml": raw_xml
    }


@router.get("/road-blockages")
def list_road_blockages(
    state: Optional[str] = Query(None, description="Filter by state"),
    status: Optional[str] = Query(None, description="Filter by blockage status"),
    db: Session = Depends(get_db),
):
    query = db.query(HazardZoneModel)
    if state and state.strip().lower() != "all":
        query = query.filter(HazardZoneModel.state == state.strip().lower())
    if status and status.strip().upper() != "ALL":
        normalized_status = status.strip().upper()
        if normalized_status not in VALID_ROAD_BLOCKAGE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid road blockage status '{status}'. Allowed: {sorted(VALID_ROAD_BLOCKAGE_STATUSES)}",
            )
        query = query.filter(HazardZoneModel.roadBlockageStatus == normalized_status)

    zones = query.all()
    return [serialize_road_blockage(z, db) for z in zones]


@router.put("/road-blockages/{zone_id}")
def update_road_blockage(
    zone_id: str,
    req: RoadBlockageUpdateRequest,
    db: Session = Depends(get_db),
):
    zone = db.query(HazardZoneModel).filter(HazardZoneModel.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Hazard zone '{zone_id}' not found")

    normalized_status = (req.status or "").strip().upper()
    if normalized_status not in VALID_ROAD_BLOCKAGE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid road blockage status '{req.status}'. Allowed: {sorted(VALID_ROAD_BLOCKAGE_STATUSES)}",
        )

    normalized_source = (req.source or "authority_verified").strip()
    if normalized_source not in VALID_ROAD_BLOCKAGE_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid source '{req.source}'. Allowed: {sorted(VALID_ROAD_BLOCKAGE_SOURCES)}",
        )

    now_iso = datetime.now(timezone.utc).isoformat()

    assigned_unit = None
    if req.assigned_unit_id is not None:
        cleaned_unit_id = req.assigned_unit_id.strip()
        if cleaned_unit_id:
            assigned_unit = (
                db.query(TacticalUnitModel)
                .filter(TacticalUnitModel.id == cleaned_unit_id)
                .first()
            )
            if not assigned_unit:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tactical unit '{cleaned_unit_id}' not found",
                )
            zone.assignedUnitId = assigned_unit.id
            assigned_unit.assignedZoneId = zone.id
            assigned_unit.destination = f"{zone.corridor} ({zone.highwaySegment})"
            assigned_unit.updatedAt = now_iso
            if normalized_status in {"BLOCKED", "CLEARING_IN_PROGRESS"}:
                assigned_unit.status = "DEBRIS CLEARING"
                assigned_unit.statusLabel = f"CLEARING {zone.highwaySegment}"
        else:
            zone.assignedUnitId = None

    if req.verified is not None:
        is_verified = bool(req.verified)
    else:
        is_verified = normalized_source != "citizen_report"

    zone.roadBlockageStatus = normalized_status
    zone.roadBlockageSource = normalized_source
    zone.roadBlockageVerified = is_verified
    zone.roadBlockageUpdatedAt = now_iso
    if req.estimated_clearance_time is not None:
        zone.estimatedClearanceTime = req.estimated_clearance_time.strip() or None
    if req.notes is not None:
        zone.blockageNotes = req.notes.strip() or None

    db.add(
        AuditLogModel(
            id=f"log-{uuid.uuid4().hex[:6]}",
            code=f"CORR-{uuid.uuid4().hex[:4].upper()}",
            title=f"Corridor Status: {zone.highwaySegment} -> {normalized_status}",
            timestamp=datetime.now().strftime("%H:%M:%S IST"),
            message=(
                f"Corridor {zone.corridor} set to {normalized_status} "
                f"(source={normalized_source}, verified={is_verified}, "
                f"unit={zone.assignedUnitId or 'unassigned'}, ETA={zone.estimatedClearanceTime or 'N/A'})."
            ),
            authority="Disaster Operations Command",
            type="corridor",
            highlight=normalized_status in {"BLOCKED", "CLEARING_IN_PROGRESS"},
        )
    )
    db.commit()
    db.refresh(zone)
    return serialize_road_blockage(zone, db)


@router.get("/units")
def list_tactical_units(db: Session = Depends(get_db)):
    return db.query(TacticalUnitModel).all()


@router.get("/shelters")
def list_relief_shelters(
    state: Optional[str] = Query(None, description="Optional state filter"),
    db: Session = Depends(get_db),
):
    query = db.query(ReliefShelterModel)
    if state and state.strip().lower() != "all":
        query = query.filter(ReliefShelterModel.state == state.strip().lower())
    return query.all()


@router.put("/shelters/{shelter_id}")
def update_relief_shelter(
    shelter_id: str,
    req: ShelterUpdateRequest,
    db: Session = Depends(get_db),
):
    shelter = db.query(ReliefShelterModel).filter(ReliefShelterModel.id == shelter_id).first()
    if not shelter:
        raise HTTPException(status_code=404, detail=f"Relief shelter '{shelter_id}' not found")

    new_max = req.capacityMax if req.capacityMax is not None else shelter.capacityMax
    new_current = req.capacityCurrent if req.capacityCurrent is not None else shelter.capacityCurrent

    if new_max is None or new_max <= 0:
        raise HTTPException(status_code=422, detail="capacityMax must be greater than 0")
    if new_current is None or new_current < 0:
        raise HTTPException(status_code=422, detail="capacityCurrent cannot be negative")
    if new_current > new_max:
        raise HTTPException(
            status_code=422,
            detail=f"capacityCurrent ({new_current}) cannot exceed capacityMax ({new_max})",
        )

    if req.status is not None:
        normalized_status = req.status.strip().upper()
        if normalized_status not in VALID_SHELTER_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid shelter status '{req.status}'. Allowed: {sorted(VALID_SHELTER_STATUSES)}",
            )
        shelter.status = normalized_status
    else:
        occupancy_ratio = new_current / new_max
        if new_current == new_max:
            shelter.status = "FULL"
        elif occupancy_ratio >= 0.85:
            shelter.status = "CRITICAL"
        else:
            shelter.status = "AVAILABLE"

    shelter.capacityMax = new_max
    shelter.capacityCurrent = new_current
    shelter.occupancyPercent = int(round((new_current / new_max) * 100))

    if req.rationsDays is not None:
        shelter.rationsDays = req.rationsDays.strip()
    if req.gensetStatus is not None:
        shelter.gensetStatus = req.gensetStatus.strip()
    if req.waterSupply is not None:
        shelter.waterSupply = req.waterSupply.strip()
    if req.medicalActive is not None:
        shelter.medicalActive = bool(req.medicalActive)

    shelter.updatedAt = datetime.now(timezone.utc).isoformat()

    db.add(
        AuditLogModel(
            id=f"log-{uuid.uuid4().hex[:6]}",
            code=f"SHLT-{uuid.uuid4().hex[:4].upper()}",
            title=f"Shelter Updated: {shelter.name}",
            timestamp=datetime.now().strftime("%H:%M:%S IST"),
            message=(
                f"Occupancy updated to {shelter.capacityCurrent}/{shelter.capacityMax} "
                f"({shelter.occupancyPercent}%) | Status: {shelter.status} | Rations: {shelter.rationsDays}"
            ),
            authority="Shelter Operations Coordinator",
            type="order",
            highlight=shelter.status in {"CRITICAL", "FULL"},
        )
    )
    db.commit()
    db.refresh(shelter)
    return shelter


@router.get("/audit-logs")
def list_audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLogModel).order_by(AuditLogModel.created_at.desc()).limit(25).all()
    if not logs:
        return [
            {
                "id": "log-01",
                "code": "CAP-DISPATCH-981",
                "title": "Stage 3 CAP Evacuation Order Authenticated",
                "timestamp": "14:32:08 IST",
                "message": "Digital signature verified via GSI C-DAC PKI token. Disseminated to Sikkim SDMA & NDRF.",
                "authority": "Duty Officer (NER Hub)",
                "type": "broadcast",
                "highlight": True,
            },
            {
                "id": "log-02",
                "code": "SIREN-ACT-04",
                "title": "Acoustic Tower Mesh Siren Active",
                "timestamp": "14:30:15 IST",
                "message": "6 Siren Towers along NH-10 Singtam-Rangpo activated. 130dB Wailing Signal sequence initiated.",
                "authority": "Automatic Alert Engine",
                "type": "siren",
                "highlight": True,
            },
        ]
    return logs


@router.post("/siren")
def trigger_siren(req: SirenTriggerRequest, db: Session = Depends(get_db)):
    if req.towers <= 0:
        raise HTTPException(status_code=422, detail="towers must be greater than 0")
    new_log = AuditLogModel(
        id=f"log-{uuid.uuid4().hex[:6]}",
        code=f"SIREN-SIM-{uuid.uuid4().hex[:4].upper()}",
        title=f"Simulated Acoustic Siren Sequence ({req.towers} Towers)",
        timestamp=datetime.now().strftime("%H:%M:%S IST"),
        message=(
            f"[SIMULATED HARDWARE TRIGGER] Stage {req.stage} Acoustic Warning Siren logged "
            f"across {req.towers} towers along {req.corridor}."
        ),
        authority="Disaster Operations Command",
        type="siren",
        highlight=True,
    )
    db.add(new_log)
    db.commit()
    return {
        "status": "active",
        "simulated": True,
        "towers_activated": req.towers,
        "corridor": req.corridor,
        "message": (
            f"Simulated Stage {req.stage} Acoustic Warning Siren logged across {req.towers} towers "
            f"along {req.corridor} (no physical siren hardware connected)."
        ),
    }


@router.post("/dispatch")
def dispatch_order(req: DispatchRequest, db: Session = Depends(get_db)):
    cleaned_dest = (req.destination or "").strip()
    if not cleaned_dest:
        raise HTTPException(status_code=422, detail="destination cannot be empty")

    normalized_priority = (req.priority or "URGENT").strip().upper()
    if normalized_priority not in VALID_DISPATCH_PRIORITIES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid priority '{req.priority}'. Allowed: {sorted(VALID_DISPATCH_PRIORITIES)}",
        )

    normalized_status = (req.status or "EN ROUTE").strip().upper()
    if normalized_status not in VALID_UNIT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid unit status '{req.status}'. Allowed: {sorted(VALID_UNIT_STATUSES)}",
        )

    unit = db.query(TacticalUnitModel).filter(TacticalUnitModel.id == req.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail=f"Tactical unit '{req.unit_id}' not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    unit.destination = cleaned_dest
    unit.status = normalized_status
    if req.eta is not None and req.eta.strip():
        unit.eta = req.eta.strip()
    unit.statusLabel = (
        f"{normalized_status} ({unit.eta})"
        if unit.eta and normalized_status == "EN ROUTE"
        else f"{normalized_status} — {cleaned_dest[:28]}"
    )
    if req.zone_id is not None:
        unit.assignedZoneId = req.zone_id.strip() or None
    unit.updatedAt = now_iso

    db.add(
        AuditLogModel(
            id=f"log-{uuid.uuid4().hex[:6]}",
            code=f"DISP-{uuid.uuid4().hex[:4].upper()}",
            title=f"Tactical Dispatch: {unit.name}",
            timestamp=datetime.now().strftime("%H:%M:%S IST"),
            message=(
                f"Unit {unit.id} ({unit.name}) assigned to '{cleaned_dest}' | "
                f"Status: {normalized_status} | Priority: {normalized_priority} "
                f"(Command DB updated; external SATCOM/VHF relay is simulated)."
            ),
            authority="Disaster Operations Command",
            type="order",
            highlight=normalized_priority == "CRITICAL",
        )
    )
    db.commit()
    db.refresh(unit)
    return {
        "status": "success",
        "dispatch_mode": "command_db_recorded_simulated_uplink",
        "simulated_external_uplink": True,
        "unit": {
            "id": unit.id,
            "name": unit.name,
            "status": unit.status,
            "statusLabel": unit.statusLabel,
            "eta": unit.eta,
            "personnel": unit.personnel,
            "description": unit.description,
            "destination": unit.destination,
            "satcomStatus": unit.satcomStatus,
            "equipment": unit.equipment,
            "progressPercent": unit.progressPercent,
            "type": unit.type,
            "assignedZoneId": unit.assignedZoneId,
            "updatedAt": unit.updatedAt,
        },
        "message": (
            f"Tactical order recorded in command database for {unit.name} to {cleaned_dest} "
            f"({normalized_priority}). External field radio uplink is simulated."
        ),
    }

class SmsBroadcastRequest(BaseModel):
    headline: str
    instruction: str
    phone_numbers: Optional[List[str]] = None
    state: Optional[str] = "sikkim"
    sender_id: Optional[str] = None
    dlt_entity_id: Optional[str] = None
    template_id: Optional[str] = None


@router.get("/sms-status")
def get_sms_status():
    from backend.services.sms_service import sms_service
    return sms_service.get_status()

@router.post("/sms-broadcast")
def broadcast_emergency_sms(req: SmsBroadcastRequest, db: Session = Depends(get_db)):
    from backend.services.sms_service import sms_service
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="SMS message cannot be empty.")

    result = sms_service.send_broadcast_alert(
        headline=req.headline,
        instruction=req.instruction,
        phone_numbers=req.phone_numbers,
        state=req.state or "sikkim",
        sender_id=req.sender_id,
        dlt_entity_id=req.dlt_entity_id,
        template_id=req.template_id,
    )
    db.add(AuditLogModel(
        id=f"log-{uuid.uuid4().hex[:6]}",
        code=result.get("request_id", f"SMS-{uuid.uuid4().hex[:6].upper()}"),
        title="Emergency SMS Broadcast",
        timestamp=datetime.now().strftime("%H:%M:%S IST"),
        message=(
            f"Target: {req.state or 'unspecified'} | Recipients: {result.get('recipients_count', 0)} | "
            f"Status: {result.get('status', 'dispatch_failed')} | Provider: {result.get('gateway', 'SMSHorizon')}"
        ),
        authority="Disaster Operations Command",
        type="broadcast",
        highlight=result.get("status") in {"sent", "demo"},
    ))
    db.commit()
    return result


