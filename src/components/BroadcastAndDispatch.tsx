import React, { useState, useEffect } from 'react';
import {
  CAP_LANGUAGES,
  ALERT_TEMPLATES,
  HAZARD_ZONES,
  AUDIT_LOGS,
  ASSET_URLS,
} from '../data/mockData';
import {
  AuditLogEntry,
  TacticalUnit,
  ReliefShelter,
  RoadBlockageRecord,
  RoadBlockageStatus,
} from '../types';
import { sirenPlayer } from '../utils/audioSiren';
import { ApiError, LandslideApi } from '../services/api';
import {
  BellRing,
  Radio,
  Send,
  Languages,
  Users,
  ShieldAlert,
  Building2,
  Truck,
  CheckCircle2,
  AlertTriangle,
  MapPin,
  Clock,
  Compass,
  FileText,
  Volume2,
  VolumeX,
  Zap,
  X,
  RefreshCw,
} from 'lucide-react';

interface BroadcastAndDispatchProps {
  onSirenTriggered?: () => void;
}

export const BroadcastAndDispatch: React.FC<BroadcastAndDispatchProps> = ({
  onSirenTriggered,
}) => {
  const selectedTarget = HAZARD_ZONES.find((zone) => zone.state === 'sikkim') || HAZARD_ZONES[0];
  const [selectedLang, setSelectedLang] = useState<string>('en');
  const [messageText, setMessageText] = useState<string>(ALERT_TEMPLATES['en']);
  const [recipientText, setRecipientText] = useState<string>('');
  const [targetId, setTargetId] = useState<string>(selectedTarget.id);
  const [isArmed, setIsArmed] = useState<boolean>(true);
  const [auditList, setAuditList] = useState<AuditLogEntry[]>(AUDIT_LOGS);

  // Persisted API states (no static mock initialization for shelters/units/blockages)
  const [tacticalUnits, setTacticalUnits] = useState<TacticalUnit[]>([]);
  const [unitsLoading, setUnitsLoading] = useState<boolean>(true);
  const [unitsError, setUnitsError] = useState<string | null>(null);
  const [unitDispatchDrafts, setUnitDispatchDrafts] = useState<
    Record<string, { destination: string; status: TacticalUnit['status']; priority: 'CRITICAL' | 'URGENT' | 'ROUTINE' }>
  >({});
  const [dispatchingUnitId, setDispatchingUnitId] = useState<string | null>(null);

  const [reliefShelters, setReliefShelters] = useState<ReliefShelter[]>([]);
  const [sheltersLoading, setSheltersLoading] = useState<boolean>(true);
  const [sheltersError, setSheltersError] = useState<string | null>(null);
  const [updatingShelterId, setUpdatingShelterId] = useState<string | null>(null);

  const [roadBlockages, setRoadBlockages] = useState<RoadBlockageRecord[]>([]);
  const [blockagesLoading, setBlockagesLoading] = useState<boolean>(true);
  const [blockagesError, setBlockagesError] = useState<string | null>(null);
  const [corridorStatusDraft, setCorridorStatusDraft] = useState<RoadBlockageStatus>('OPEN');
  const [corridorUnitDraft, setCorridorUnitDraft] = useState<string>('');
  const [corridorEtaDraft, setCorridorEtaDraft] = useState<string>('');
  const [corridorNotesDraft, setCorridorNotesDraft] = useState<string>('');
  const [isSavingCorridor, setIsSavingCorridor] = useState<boolean>(false);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isSirenActive, setIsSirenActive] = useState<boolean>(false);
  const [isConfirmOpen, setIsConfirmOpen] = useState<boolean>(false);
  const [isDispatching, setIsDispatching] = useState<boolean>(false);
  const [dispatchResult, setDispatchResult] = useState<{
    status: 'sent' | 'demo' | 'provider_not_configured' | 'provider_unavailable' | 'dispatch_failed';
    gateway: string;
    message: string;
    request_id?: string;
    recipients_count: number;
  } | null>(null);
  const [dispatchError, setDispatchError] = useState<string | null>(null);
  const [smsStatus, setSmsStatus] = useState<{
    provider: string;
    demo_mode: boolean;
    configured: boolean;
    dlt_status: 'Configured' | 'Pending activation';
    sender_id: string | null;
    template_id: string | null;
  } | null>(null);

  const activeTarget = HAZARD_ZONES.find((zone) => zone.id === targetId) || selectedTarget;
  const activeCorridorBlockage = roadBlockages.find((b) => b.zone_id === targetId) || roadBlockages[0] || null;
  const recipientNumbers = recipientText.split(/[\s,;]+/).map((value) => value.trim()).filter(Boolean);
  const smsSegments = Math.max(1, Math.ceil(messageText.length / 160));

  useEffect(() => {
    return sirenPlayer.subscribe(setIsSirenActive);
  }, []);

  const refreshOperationalData = async () => {
    setUnitsLoading(true);
    setSheltersLoading(true);
    setBlockagesLoading(true);

    LandslideApi.getAuditLogs()
      .then((logs) => {
        if (logs && logs.length > 0) setAuditList(logs);
      })
      .catch(() => {});

    LandslideApi.getTacticalUnits()
      .then((units) => {
        setTacticalUnits(units || []);
        setUnitsError(null);
        const drafts: Record<string, { destination: string; status: TacticalUnit['status']; priority: 'CRITICAL' | 'URGENT' | 'ROUTINE' }> = {};
        (units || []).forEach((u) => {
          drafts[u.id] = {
            destination: u.destination || activeTarget.corridor,
            status: u.status || 'EN ROUTE',
            priority: 'URGENT',
          };
        });
        setUnitDispatchDrafts((prev) => ({ ...drafts, ...prev }));
      })
      .catch((err) => {
        setUnitsError(err instanceof Error ? err.message : 'Unable to load tactical units.');
      })
      .finally(() => setUnitsLoading(false));

    LandslideApi.getReliefShelters()
      .then((shelters) => {
        setReliefShelters(shelters || []);
        setSheltersError(null);
      })
      .catch((err) => {
        setSheltersError(err instanceof Error ? err.message : 'Unable to load relief shelters.');
      })
      .finally(() => setSheltersLoading(false));

    LandslideApi.getRoadBlockages()
      .then((records) => {
        setRoadBlockages(records || []);
        setBlockagesError(null);
      })
      .catch((err) => {
        setBlockagesError(err instanceof Error ? err.message : 'Unable to load road-blockage telemetry.');
      })
      .finally(() => setBlockagesLoading(false));

    LandslideApi.getSmsStatus()
      .then((status) => setSmsStatus(status))
      .catch(() => setSmsStatus(null));
  };

  useEffect(() => {
    refreshOperationalData();
  }, []);

  useEffect(() => {
    if (activeCorridorBlockage) {
      setCorridorStatusDraft(activeCorridorBlockage.status || 'OPEN');
      setCorridorUnitDraft(activeCorridorBlockage.assigned_unit_id || '');
      setCorridorEtaDraft(activeCorridorBlockage.estimated_clearance_time || '');
      setCorridorNotesDraft(activeCorridorBlockage.notes || '');
    }
  }, [activeCorridorBlockage?.zone_id, activeCorridorBlockage?.status, activeCorridorBlockage?.assigned_unit_id, activeCorridorBlockage?.estimated_clearance_time, activeCorridorBlockage?.notes]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4200);
  };

  const handleUpdateCorridorBlockage = async () => {
    if (!activeCorridorBlockage) return;
    setIsSavingCorridor(true);
    try {
      const updated = await LandslideApi.updateRoadBlockage(activeCorridorBlockage.zone_id, {
        status: corridorStatusDraft,
        source: 'authority_verified',
        verified: true,
        assigned_unit_id: corridorUnitDraft || null,
        estimated_clearance_time: corridorEtaDraft || null,
        notes: corridorNotesDraft || null,
      });
      setRoadBlockages((prev) =>
        prev.map((item) => (item.zone_id === updated.zone_id ? updated : item))
      );
      const [units, logs] = await Promise.all([
        LandslideApi.getTacticalUnits(),
        LandslideApi.getAuditLogs(),
      ]);
      setTacticalUnits(units);
      if (logs.length > 0) setAuditList(logs);
      showToast(
        `Corridor ${updated.highway_segment} updated to ${updated.status} (Authority Verified).`
      );
    } catch (err) {
      showToast(
        `Failed to update corridor blockage: ${err instanceof Error ? err.message : 'API error'}`
      );
    } finally {
      setIsSavingCorridor(false);
    }
  };

  const handleAdjustShelter = async (
    shelter: ReliefShelter,
    newOccupancy: number,
    newStatus?: ReliefShelter['status']
  ) => {
    const clampedOccupancy = Math.max(0, Math.min(shelter.capacityMax, newOccupancy));
    setUpdatingShelterId(shelter.id);
    try {
      const updated = await LandslideApi.updateReliefShelter(shelter.id, {
        capacityCurrent: clampedOccupancy,
        capacityMax: shelter.capacityMax,
        status: newStatus ?? shelter.status,
      });
      setReliefShelters((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      const logs = await LandslideApi.getAuditLogs();
      if (logs.length > 0) setAuditList(logs);
      showToast(
        `Shelter ${updated.name} updated: ${updated.capacityCurrent}/${updated.capacityMax} (${updated.status}).`
      );
    } catch (err) {
      showToast(
        `Shelter update failed: ${err instanceof Error ? err.message : 'Validation or network error'}`
      );
    } finally {
      setUpdatingShelterId(null);
    }
  };

  const handleDispatchUnit = async (unit: TacticalUnit) => {
    const draft = unitDispatchDrafts[unit.id] || {
      destination: activeTarget.corridor,
      status: 'EN ROUTE',
      priority: 'URGENT' as const,
    };
    if (!draft.destination.trim()) {
      showToast('Please enter a valid dispatch destination.');
      return;
    }
    setDispatchingUnitId(unit.id);
    try {
      const res = await LandslideApi.dispatchTacticalUnit({
        unit_id: unit.id,
        destination: draft.destination,
        status: draft.status,
        priority: draft.priority,
        zone_id: activeTarget.id,
      });
      setTacticalUnits((prev) => prev.map((u) => (u.id === res.unit.id ? res.unit : u)));
      const logs = await LandslideApi.getAuditLogs();
      if (logs.length > 0) setAuditList(logs);
      showToast(res.message);
    } catch (err) {
      showToast(`Unit dispatch failed: ${err instanceof Error ? err.message : 'API error'}`);
    } finally {
      setDispatchingUnitId(null);
    }
  };

  const handleLanguageChange = (langId: string) => {
    setSelectedLang(langId);
    setMessageText(ALERT_TEMPLATES[langId] || ALERT_TEMPLATES['en']);
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case 'sent':
        return 'SMS request accepted by provider.';
      case 'demo':
        return 'DEMO MODE — No real SMS was sent.';
      case 'provider_not_configured':
        return 'SMSHorizon is not configured or DLT activation is pending.';
      case 'provider_unavailable':
        return 'SMS provider is currently unavailable.';
      default:
        return 'SMS dispatch failed.';
    }
  };

  const handleExecuteDispatch = async () => {
    if (!messageText.trim()) {
      showToast('SMS message cannot be empty.');
      return;
    }

    setIsDispatching(true);
    setDispatchResult(null);
    setDispatchError(null);
    try {
      const smsRes = await LandslideApi.sendSmsBroadcast({
        headline: 'MANDATORY EVACUATION ALERT',
        instruction: messageText,
        phoneNumbers: recipientNumbers,
        state: activeTarget.state,
      });
      const normalizedResult = {
        ...smsRes,
        status: smsRes.status as 'sent' | 'demo' | 'provider_not_configured' | 'provider_unavailable' | 'dispatch_failed',
      };
      setDispatchResult(normalizedResult);
      showToast(statusLabel(smsRes.status));
      const refreshedLogs = await LandslideApi.getAuditLogs();
      if (refreshedLogs.length > 0) setAuditList(refreshedLogs);
      sirenPlayer.start();
      LandslideApi.triggerSiren(activeTarget.corridor, 6).catch(console.warn);
      if (onSirenTriggered) onSirenTriggered();
    } catch (err) {
      const httpStatus = err instanceof ApiError ? err.status : null;
      const errorMessage = httpStatus === 400
        ? 'Message validation failed. Review the SMS content.'
        : httpStatus === 401
        ? 'Operator authentication is required.'
        : httpStatus === 403
        ? 'Operator is not authorized to dispatch SMS.'
        : httpStatus === 408
        ? 'The SMS request timed out.'
        : httpStatus === 429
        ? 'Dispatch rate limit reached. Try again later.'
        : httpStatus && httpStatus >= 500
        ? 'SMS backend is currently unavailable.'
        : 'Unable to connect to the backend SMS service.';
      const failedResult = {
        status: httpStatus && httpStatus !== 408 ? 'dispatch_failed' as const : 'provider_unavailable' as const,
        gateway: 'SMSHorizon',
        message: errorMessage,
        recipients_count: 0,
      };
      setDispatchError(errorMessage);
      setDispatchResult(failedResult);
      showToast(errorMessage);
    } finally {
      setIsDispatching(false);
      setIsConfirmOpen(false);
    }
  };

  return (
    <div className="space-y-4 pb-12">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#122131] text-[#90cfec] border border-[#44d8f1] px-4 py-3 rounded-lg shadow-2xl shadow-cyan-950/80 flex items-center gap-3 font-sans text-xs sm:text-sm animate-bounce">
          <Zap className="w-4 h-4 text-[#ffb870] flex-shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {isConfirmOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="broadcast-confirm-title">
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-[#0d1c2d] border border-[#44d8f1]/50 rounded-xl p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[#1c2b3c] pb-3">
              <div>
                <h2 id="broadcast-confirm-title" className="text-base font-bold text-white">Confirm Emergency Broadcast</h2>
                <p className="text-xs text-[#8a9297] mt-1">Review the operator dispatch before sending the request.</p>
              </div>
              <button onClick={() => setIsConfirmOpen(false)} className="text-[#8a9297] hover:text-white" aria-label="Close confirmation">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-4 text-xs">
              <div><span className="text-[#8a9297] block">Target state / area</span><span className="text-white font-semibold">{activeTarget.state.toUpperCase()} / {activeTarget.name}</span></div>
              <div><span className="text-[#8a9297] block">Recipient count</span><span className="text-white font-semibold">{recipientNumbers.length} provided to backend</span></div>
              <div><span className="text-[#8a9297] block">Sender ID</span><span className="text-white font-semibold">{smsStatus?.sender_id || 'Not configured'}</span></div>
              <div><span className="text-[#8a9297] block">DLT template ID</span><span className="text-white font-semibold">{smsStatus?.template_id || 'Not configured'}</span></div>
              <div><span className="text-[#8a9297] block">Estimated SMS segments</span><span className="text-white font-semibold">{smsSegments}</span></div>
              <div><span className="text-[#8a9297] block">Dispatch mode</span><span className={`font-semibold ${smsStatus?.demo_mode ? 'text-[#ffb870]' : 'text-[#44d8f1]'}`}>{smsStatus?.demo_mode ? 'DEMO' : 'PRODUCTION'}</span></div>
            </div>
            <div className="bg-[#051424] border border-[#273647] rounded-lg p-3 text-sm text-[#d4e4fa] whitespace-pre-wrap break-words">{messageText}</div>
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 mt-4">
              <button onClick={() => setIsConfirmOpen(false)} className="px-4 py-2.5 rounded-lg border border-[#273647] text-xs font-bold text-[#bfc8cd] hover:text-white">CANCEL</button>
              <button onClick={handleExecuteDispatch} disabled={isDispatching} className="px-4 py-2.5 rounded-lg bg-[#93000a] hover:bg-[#b00020] disabled:opacity-50 text-white text-xs font-bold flex items-center justify-center gap-2">
                <Send className="w-4 h-4" /> {isDispatching ? 'DISPATCHING...' : 'CONFIRM DISPATCH'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stage 3 Critical Escalation Banner */}
      <div className="bg-[#0d1c2d] border border-[#93000a] rounded-xl p-4 sm:p-5 relative overflow-hidden shadow-2xl">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="bg-[#93000a] text-white text-[11px] font-mono font-bold px-2 py-0.5 rounded flex items-center gap-1.5 animate-pulse">
                <ShieldAlert className="w-3.5 h-3.5" />
                COMMON ALERTING PROTOCOL (CAP-CMSP)
              </span>
              <span className="text-[11px] font-mono text-[#44d8f1] bg-[#00363e] px-2 py-0.5 rounded border border-[#00bcd4]/30">
                DISASTER MANAGEMENT ACT 2005 (SEC 30)
              </span>
            </div>

            <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
              Emergency Broadcast &amp; Evacuation Corridor Management
            </h2>
            <p className="text-xs sm:text-sm text-[#bfc8cd] max-w-3xl">
              Authorized operators can prepare and review a multilingual emergency SMS request for the selected area. Provider acceptance and delivery are reported only when verified by SMSHorizon.
            </p>
          </div>

          {/* Broadcast Arm Control Button */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <button
              onClick={() => setIsArmed(!isArmed)}
              className={`px-3 py-2 rounded-lg text-xs font-mono font-bold border transition-all cursor-pointer ${
                isArmed
                  ? 'bg-[#93000a]/30 text-[#ffb4ab] border-[#ffb4ab]'
                  : 'bg-[#122131] text-[#8a9297] border-[#273647]'
              }`}
            >
              {isArmed ? 'TRANSMITTER: ARMED' : 'TRANSMITTER: STANDBY'}
            </button>

            <button
              onClick={() => setIsConfirmOpen(true)}
              disabled={!isArmed || !messageText.trim() || isDispatching}
              className={`px-4 py-2.5 rounded-lg text-xs sm:text-sm font-bold text-white flex items-center gap-2 shadow-lg transition-all cursor-pointer ${
                isArmed
                  ? 'bg-[#93000a] hover:bg-[#b00020] shadow-red-950/60 animate-pulse'
                  : 'bg-[#273647] opacity-50 cursor-not-allowed'
              }`}
            >
              <Send className="w-4 h-4" />
              <span>EXECUTE CAP BROADCAST</span>
            </button>

            {isSirenActive && (
              <button
                onClick={() => {
                  sirenPlayer.stop();
                  showToast('Emergency Acoustic Siren silenced.');
                }}
                className="px-3.5 py-2.5 rounded-lg text-xs sm:text-sm font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 flex items-center gap-1.5 shadow-lg shadow-amber-950/60 animate-pulse transition-all cursor-pointer"
                title="Silence Active Acoustic Siren"
              >
                <VolumeX className="w-4 h-4" />
                <span>SILENCE SIREN</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Multi-Lingual Alert & Geofence Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Multilingual Alert Composer (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-[#0d1c2d] border border-[#1c2b3c] rounded-xl p-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#1c2b3c] pb-3 mb-3">
              <div className="flex items-center gap-2">
                <Languages className="w-4 h-4 text-[#44d8f1]" />
                <h3 className="text-xs sm:text-sm font-bold text-white uppercase tracking-wider">
                  Multi-Lingual Alert Matrix (7 Regional Languages)
                </h3>
              </div>

            {smsStatus?.demo_mode && (
              <div className="mb-3 rounded-lg border border-[#ffb870]/60 bg-[#7d4800]/20 px-3 py-2 text-xs font-bold text-[#ffb870]">DEMO MODE — No real SMS will be sent.</div>
            )}

            {dispatchResult && (
              <div className={`mb-3 rounded-lg border px-3 py-2.5 text-xs ${dispatchResult.status === 'sent' ? 'border-[#44d8f1]/60 bg-[#00363e]/30 text-[#44d8f1]' : dispatchResult.status === 'demo' ? 'border-[#ffb870]/60 bg-[#7d4800]/20 text-[#ffb870]' : 'border-[#ffb4ab]/60 bg-[#93000a]/20 text-[#ffb4ab]'}`}>
                <div className="font-bold">{statusLabel(dispatchResult.status)}</div>
                <div className="mt-1 text-current/80">Request ID: {dispatchResult.request_id || 'Unavailable'} · Recipients: {dispatchResult.recipients_count}</div>
              </div>
            )}
            {dispatchError && <div className="mb-3 text-xs text-[#ffb4ab]">{dispatchError}</div>}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              <label className="text-[10px] font-mono uppercase text-[#8a9297]">Target area
                <select value={targetId} onChange={(event) => setTargetId(event.target.value)} className="mt-1 w-full bg-[#051424] text-white border border-[#273647] rounded-lg p-2.5 text-xs focus:outline-none focus:border-[#44d8f1]">
                  {HAZARD_ZONES.map((zone) => <option key={zone.id} value={zone.id}>{zone.state.toUpperCase()} / {zone.name}</option>)}
                </select>
              </label>
              <div className="rounded-lg border border-[#1c2b3c] bg-[#122131] p-2.5 text-xs">
                <span className="text-[10px] font-mono uppercase text-[#8a9297]">SMS Provider</span>
                <div className="text-white font-semibold mt-1">{smsStatus?.provider || 'SMSHorizon'}</div>
                <div className="text-[#bfc8cd] mt-0.5">DLT Status: <span className={smsStatus?.configured ? 'text-[#44d8f1]' : 'text-[#ffb870]'}>{smsStatus?.dlt_status || 'Status unavailable'}</span></div>
              </div>
            </div>
              <span className="text-[10px] font-mono text-[#90cfec] bg-[#0d5c75]/40 px-2 py-0.5 rounded border border-[#0d5c75]">
                BHASHINI VERIFIED
              </span>
            </div>

            {/* Language Selection Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-2">
              {CAP_LANGUAGES.map((lang) => (
                <button
                  key={lang.id}
                  onClick={() => handleLanguageChange(lang.id)}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all border cursor-pointer ${
                    selectedLang === lang.id
                      ? 'bg-[#1c2b3c] text-white border-[#44d8f1]'
                      : 'bg-[#122131] text-[#8a9297] border-[#1c2b3c] hover:text-white'
                  }`}
                >
                  <span>{lang.name}</span>
                </button>
              ))}
            </div>

            {/* Editable Text Area for SMS broadcast */}
            <div className="mt-3 relative">
              <textarea
                value={messageText}
                onChange={(e) => setMessageText(e.target.value)}
                rows={4}
                className="w-full bg-[#051424] text-xs sm:text-sm text-[#d4e4fa] border border-[#273647] rounded-lg p-3 focus:outline-none focus:border-[#44d8f1] font-sans resize-none leading-relaxed"
                placeholder="Compose or inspect emergency warning payload..."
              />
              <div className="flex items-center justify-between text-[11px] font-mono text-[#8a9297] mt-1.5">
                <span>GSM Standard: 160 Chars/Segment</span>
                <span
                  className={
                    messageText.length > 160 ? 'text-[#ffb870]' : 'text-[#44d8f1]'
                  }
                >
                  Length: {messageText.length} characters ({smsSegments} SMS)
                </span>
              </div>
            </div>

            {/* Quick Alert Presets */}
            <div className="mt-3 pt-3 border-t border-[#1c2b3c]">
              <span className="text-[10px] font-mono text-[#8a9297] block mb-2 uppercase">
                Quick Action Presets:
              </span>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() =>
                    setMessageText(
                      'STAGE 3 EVACUATION ORDER: Mangan & Dikchu residents must vacate immediately via Route E-3 to Singtam Stadium. NH-10 closed. Dial 1077 for SDRF assistance.'
                    )
                  }
                  className="text-[11px] font-mono px-2 py-1 rounded bg-[#122131] hover:bg-[#1c2b3c] text-[#ffb4ab] border border-[#93000a] cursor-pointer"
                >
                  Mandatory Evacuation
                </button>
                <button
                  onClick={() =>
                    setMessageText(
                      'TRAFFIC WARNING: NH-10 Teesta Corridor completely shut due to mud debris at Km 38.4. All heavy goods vehicles divert via Kalimpong-Algarah. BRO clearing underway.'
                    )
                  }
                  className="text-[11px] font-mono px-2 py-1 rounded bg-[#122131] hover:bg-[#1c2b3c] text-[#ffb870] border border-[#7d4800] cursor-pointer"
                >
                  Highway NH-10 Closure
                </button>
                <button
                  onClick={() =>
                    setMessageText(
                      'ALL CLEAR NOTICE: Slope stabilization completed at Km 38.4. Route E-3 open for two-way civilian movement. Continue monitoring LEWS app.'
                    )
                  }
                  className="text-[11px] font-mono px-2 py-1 rounded bg-[#122131] hover:bg-[#1c2b3c] text-[#90cfec] border border-[#0d5c75] cursor-pointer"
                >
                  All Clear Advisory
                </button>
              </div>
            </div>
          </div>

          {/* Safe Evacuation Corridor Profile (Route E-3) */}
          <div className="bg-[#0d1c2d] border border-[#1c2b3c] rounded-xl p-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#1c2b3c] pb-3 mb-3">
              <div className="flex items-center gap-2">
                <Compass className="w-4 h-4 text-[#44d8f1]" />
                <h3 className="text-xs sm:text-sm font-bold text-white uppercase tracking-wider">
                  Safe Evacuation Corridor: Route E-3 (Upper Singtam Ridge)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-[#00363e] bg-[#44d8f1] px-2 py-0.5 rounded font-bold">
                100% CLEAR
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
              {/* Route Map preview image */}
              <div className="md:col-span-5 relative rounded-lg overflow-hidden border border-[#1c2b3c] h-40">
                <img
                  src={ASSET_URLS.evacuationMapRoute}
                  alt="Route E-3 Evacuation Corridor Map"
                  className="w-full h-full object-cover"
                />
                <div className="absolute top-2 left-2 bg-[#051424]/90 text-[10px] font-mono text-[#44d8f1] px-1.5 py-0.5 rounded border border-[#273647]">
                  ROUTE E-3 ARTERY
                </div>
                <div className="absolute bottom-2 right-2 bg-[#00363e] text-[#44d8f1] text-[9px] font-mono font-bold px-1.5 py-0.5 rounded">
                  ONE-WAY UPHILL FLOW
                </div>
              </div>

              {/* Elevation Profile SVG & Specs */}
              <div className="md:col-span-7 flex flex-col justify-between space-y-2">
                <div>
                  <div className="flex items-center justify-between text-xs text-[#8a9297] font-mono">
                    <span>Elevation Profile (1,480m → 350m Singtam Valley)</span>
                    <span className="text-[#44d8f1]">Total Dist: 18.4 km</span>
                  </div>

                  {/* Elevation Line Chart */}
                  <div className="h-20 w-full mt-1">
                    <svg className="w-full h-full" viewBox="0 0 300 80" preserveAspectRatio="none">
                      <path
                        d="M 10 20 Q 80 25 150 45 T 290 70"
                        fill="none"
                        stroke="#44d8f1"
                        strokeWidth="2.5"
                      />
                      <path
                        d="M 10 20 Q 80 25 150 45 T 290 70 L 290 80 L 10 80 Z"
                        fill="#00bcd4"
                        opacity="0.1"
                      />
                      <circle cx="10" cy="20" r="4" fill="#ffb4ab" />
                      <circle cx="290" cy="70" r="4" fill="#44d8f1" />
                      <text x="15" y="24" fill="#ffb4ab" fontSize="8" fontFamily="monospace">
                        Mangan (1,480m)
                      </text>
                      <text x="180" y="65" fill="#44d8f1" fontSize="8" fontFamily="monospace">
                        Singtam Stadium (350m)
                      </text>
                    </svg>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="bg-[#122131] p-2 rounded">
                    <span className="text-[10px] text-[#8a9297] block">AVERAGE TRANSIT TIME</span>
                    <span className="text-white font-bold">32 mins (Civilian Bus)</span>
                  </div>
                  <div className="bg-[#122131] p-2 rounded">
                    <span className="text-[10px] text-[#8a9297] block">SDRF MARSHALS</span>
                    <span className="text-[#44d8f1] font-bold">6 Checkposts Active</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Geofence Stats, Relief Shelters, Tactical Units (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Target and provider status */}
          <div className="bg-[#0d1c2d] border border-[#1c2b3c] rounded-xl p-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#1c2b3c] pb-2.5 mb-3">
              <span className="font-mono text-xs font-bold uppercase text-white flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-[#44d8f1]" />
                Broadcast Target
              </span>
              <span className="text-[10px] font-mono text-[#ffb4ab] bg-[#93000a]/40 px-2 py-0.5 rounded">
                OPERATOR CONTROLLED
              </span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="bg-[#122131] p-2.5 rounded-lg border border-[#1c2b3c]"><span className="text-[10px] text-[#8a9297] block">STATE / AREA</span><span className="font-semibold text-white">{activeTarget.state.toUpperCase()} / {activeTarget.name}</span></div>
              <label className="block bg-[#122131] p-2.5 rounded-lg border border-[#1c2b3c] text-[10px] text-[#8a9297]">RECIPIENTS PROVIDED
                <input value={recipientText} onChange={(event) => setRecipientText(event.target.value)} placeholder="Phone numbers, separated by commas" className="mt-1 w-full bg-[#051424] text-white border border-[#273647] rounded p-2 text-xs focus:outline-none focus:border-[#44d8f1]" />
                <span className="block mt-1 text-[10px] text-[#bfc8cd]">{recipientNumbers.length} recipient(s) ready for review</span>
              </label>
            </div>
          </div>

          {/* Corridor Road-Blockage Monitoring & Control */}
          <div className="bg-[#0d1c2d] border border-[#1c2b3c] rounded-xl p-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#1c2b3c] pb-2.5 mb-3">
              <span className="font-mono text-xs font-bold uppercase text-white flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-[#ffb870]" />
                Corridor Road-Blockage Monitoring
              </span>
              {activeCorridorBlockage && (
                <span
                  className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                    activeCorridorBlockage.verified
                      ? 'bg-emerald-950/60 text-emerald-400 border-emerald-500/40'
                      : 'bg-amber-950/60 text-amber-300 border-amber-500/40'
                  }`}
                >
                  {activeCorridorBlockage.verified
                    ? 'AUTHORITY VERIFIED'
                    : 'CITIZEN REPORTED (UNVERIFIED)'}
                </span>
              )}
            </div>

            {blockagesLoading ? (
              <div className="text-xs text-[#8a9297] py-3 font-mono">Loading corridor road-blockage telemetry...</div>
            ) : blockagesError ? (
              <div className="text-xs text-[#ffb4ab] py-2">{blockagesError}</div>
            ) : !activeCorridorBlockage ? (
              <div className="text-xs text-[#8a9297] py-2">No corridor blockage record found for the selected zone.</div>
            ) : (
              <div className="space-y-3 text-xs">
                <div className="bg-[#122131] border border-[#1c2b3c] rounded-lg p-3 space-y-1.5">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-bold text-white">{activeCorridorBlockage.highway_segment}</div>
                      <div className="text-[11px] text-[#bfc8cd]">{activeCorridorBlockage.corridor}</div>
                    </div>
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                        activeCorridorBlockage.status === 'BLOCKED'
                          ? 'bg-[#93000a] text-white'
                          : activeCorridorBlockage.status === 'CLEARING_IN_PROGRESS'
                          ? 'bg-[#7d4800] text-[#ffb870]'
                          : activeCorridorBlockage.status === 'SINGLE_LANE'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'bg-[#00363e] text-[#44d8f1]'
                      }`}
                    >
                      {activeCorridorBlockage.status}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-1 text-[10px] font-mono text-[#8a9297]">
                    <div>
                      ASSIGNED UNIT:{' '}
                      <span className="text-white font-semibold">
                        {activeCorridorBlockage.assigned_unit_name || 'Unassigned'}
                      </span>
                    </div>
                    <div>
                      CLEARANCE ETA:{' '}
                      <span className="text-[#44d8f1] font-semibold">
                        {activeCorridorBlockage.estimated_clearance_time || 'Not set'}
                      </span>
                    </div>
                    <div>
                      SOURCE:{' '}
                      <span className="text-[#bfc8cd]">{activeCorridorBlockage.source}</span>
                    </div>
                    <div>
                      UPDATED:{' '}
                      <span className="text-[#bfc8cd]">
                        {activeCorridorBlockage.updated_at
                          ? new Date(activeCorridorBlockage.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          : 'Baseline'}
                      </span>
                    </div>
                  </div>
                  {activeCorridorBlockage.notes && (
                    <p className="text-[11px] text-[#d4e4fa] pt-1 border-t border-[#1c2b3c]">
                      {activeCorridorBlockage.notes}
                    </p>
                  )}
                </div>

                {/* Citizen road-blockage reports linked to this zone/state */}
                <div className="bg-[#122131]/70 border border-[#1c2b3c] rounded-lg p-2.5 space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-[#8a9297] uppercase">Linked Citizen Road-Blockage Reports</span>
                    <span className="text-[#bfc8cd]">
                      <strong className="text-emerald-400">{activeCorridorBlockage.verified_citizen_reports_count}</strong> Verified ·{' '}
                      <strong className="text-amber-400">{activeCorridorBlockage.unverified_citizen_reports_count}</strong> Unverified
                    </span>
                  </div>
                  {activeCorridorBlockage.citizen_reports.length === 0 ? (
                    <div className="text-[11px] text-[#8a9297]">No citizen road-blockage reports logged for this corridor.</div>
                  ) : (
                    <div className="space-y-1 max-h-28 overflow-y-auto">
                      {activeCorridorBlockage.citizen_reports.slice(0, 3).map((rep) => (
                        <div key={rep.id} className="flex items-center justify-between text-[10px] bg-[#051424] px-2 py-1 rounded border border-[#1c2b3c]">
                          <span className="truncate text-[#d4e4fa] max-w-[190px]">
                            <strong className="text-[#44d8f1] font-mono">{rep.code}</strong>: {rep.location}
                          </span>
                          <span className={rep.verified ? 'text-emerald-400 font-mono font-bold' : 'text-amber-400 font-mono'}>
                            {rep.verified ? 'VERIFIED' : 'UNVERIFIED'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Authority Corridor Update Form */}
                <div className="bg-[#122131] border border-[#1c2b3c] rounded-lg p-3 space-y-2">
                  <div className="text-[10px] font-mono uppercase text-[#90cfec] font-bold">
                    Authority Corridor Status Update
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="text-[10px] font-mono text-[#8a9297]">
                      STATUS
                      <select
                        value={corridorStatusDraft}
                        onChange={(e) => setCorridorStatusDraft(e.target.value as RoadBlockageStatus)}
                        className="mt-1 w-full bg-[#051424] text-white border border-[#273647] rounded p-1.5 text-xs"
                      >
                        <option value="OPEN">OPEN</option>
                        <option value="SINGLE_LANE">SINGLE_LANE</option>
                        <option value="BLOCKED">BLOCKED</option>
                        <option value="CLEARING_IN_PROGRESS">CLEARING_IN_PROGRESS</option>
                      </select>
                    </label>
                    <label className="text-[10px] font-mono text-[#8a9297]">
                      ASSIGN RESPONSE UNIT
                      <select
                        value={corridorUnitDraft}
                        onChange={(e) => setCorridorUnitDraft(e.target.value)}
                        className="mt-1 w-full bg-[#051424] text-white border border-[#273647] rounded p-1.5 text-xs"
                      >
                        <option value="">Unassigned</option>
                        {tacticalUnits.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={corridorEtaDraft}
                      onChange={(e) => setCorridorEtaDraft(e.target.value)}
                      placeholder="Clearance ETA (e.g. 2h 30m)"
                      className="bg-[#051424] text-white border border-[#273647] rounded p-1.5 text-xs"
                    />
                    <input
                      type="text"
                      value={corridorNotesDraft}
                      onChange={(e) => setCorridorNotesDraft(e.target.value)}
                      placeholder="Operational notes..."
                      className="bg-[#051424] text-white border border-[#273647] rounded p-1.5 text-xs"
                    />
                  </div>
                  <button
                    onClick={handleUpdateCorridorBlockage}
                    disabled={isSavingCorridor}
                    className="w-full py-1.5 px-3 rounded bg-[#00363e] hover:bg-[#0d5c75] text-[#44d8f1] border border-[#00bcd4]/40 font-mono font-bold text-[11px] transition-all cursor-pointer disabled:opacity-50"
                  >
                    {isSavingCorridor ? 'UPDATING CORRIDOR...' : 'UPDATE CORRIDOR STATUS (AUTHORITY VERIFIED)'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Designated Relief Shelters */}
          <div className="bg-[#0d1c2d] border border-[#1c2b3c] rounded-xl p-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#1c2b3c] pb-2.5 mb-3">
              <span className="font-mono text-xs font-bold uppercase text-white flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-[#90cfec]" />
                Designated Safe Relief Shelters
              </span>
              <span className="text-[10px] font-mono text-[#8a9297]">
                PERSISTED DB • {reliefShelters.length} SHELTERS
              </span>
            </div>

            {sheltersLoading ? (
              <div className="text-xs text-[#8a9297] py-3 font-mono">Loading persisted shelter records...</div>
            ) : sheltersError ? (
              <div className="text-xs text-[#ffb4ab] py-2">{sheltersError}</div>
            ) : reliefShelters.length === 0 ? (
              <div className="text-xs text-[#8a9297] py-2">No relief shelters registered in database.</div>
            ) : (
              <div className="space-y-2.5">
                {reliefShelters.map((shelter) => (
                  <div
                    key={shelter.id}
                    className="bg-[#122131] border border-[#1c2b3c] p-3 rounded-lg text-xs space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-semibold text-white">{shelter.name}</div>
                        <div className="text-[10px] text-[#8a9297]">
                          {shelter.location} ({shelter.state.toUpperCase()})
                        </div>
                        <div className="text-[9px] font-mono text-amber-300/90 mt-0.5">
                          {shelter.coordinatesVerified
                            ? 'Exact Coordinates Verified'
                            : `Approximate Locality Ref (${shelter.dataStatus || 'UNVERIFIED'})`}
                        </div>
                      </div>
                      <span
                        className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                          shelter.status === 'CRITICAL' || shelter.status === 'FULL'
                            ? 'bg-[#93000a] text-[#ffdad6]'
                            : shelter.status === 'CLOSED'
                            ? 'bg-slate-800 text-slate-400'
                            : 'bg-[#00363e] text-[#44d8f1]'
                        }`}
                      >
                        {shelter.status} · {shelter.occupancyPercent}%
                      </span>
                    </div>

                    {/* Capacity Bar */}
                    <div className="w-full h-1.5 bg-[#051424] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          shelter.occupancyPercent > 80 ? 'bg-[#ffb4ab]' : 'bg-[#44d8f1]'
                        }`}
                        style={{ width: `${Math.min(100, shelter.occupancyPercent)}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-[10px] font-mono text-[#bfc8cd]">
                      <span>
                        Occupancy: {shelter.capacityCurrent} / {shelter.capacityMax}
                      </span>
                      <span>Rations: {shelter.rationsDays}</span>
                    </div>

                    {/* Safe Occupancy & Status Controls */}
                    <div className="pt-1.5 border-t border-[#1c2b3c] flex flex-wrap items-center justify-between gap-1.5">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleAdjustShelter(shelter, shelter.capacityCurrent - 10)}
                          disabled={updatingShelterId === shelter.id || shelter.capacityCurrent <= 0}
                          className="px-2 py-0.5 rounded bg-[#051424] hover:bg-[#1c2b3c] text-white border border-[#273647] text-[10px] font-mono disabled:opacity-40 cursor-pointer"
                        >
                          -10
                        </button>
                        <button
                          onClick={() => handleAdjustShelter(shelter, shelter.capacityCurrent + 10)}
                          disabled={updatingShelterId === shelter.id || shelter.capacityCurrent >= shelter.capacityMax}
                          className="px-2 py-0.5 rounded bg-[#051424] hover:bg-[#1c2b3c] text-white border border-[#273647] text-[10px] font-mono disabled:opacity-40 cursor-pointer"
                        >
                          +10
                        </button>
                      </div>
                      <select
                        aria-label={`Status for ${shelter.name}`}
                        value={shelter.status}
                        disabled={updatingShelterId === shelter.id}
                        onChange={(e) =>
                          handleAdjustShelter(
                            shelter,
                            shelter.capacityCurrent,
                            e.target.value as ReliefShelter['status']
                          )
                        }
                        className="bg-[#051424] text-white border border-[#273647] rounded px-1.5 py-0.5 text-[10px] font-mono"
                      >
                        <option value="AVAILABLE">AVAILABLE</option>
                        <option value="STABLE">STABLE</option>
                        <option value="CRITICAL">CRITICAL</option>
                        <option value="FULL">FULL</option>
                        <option value="CLOSED">CLOSED</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Tactical Units & Resource Stockpile */}
          <div className="bg-[#0d1c2d] border border-[#1c2b3c] rounded-xl p-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#1c2b3c] pb-2.5 mb-3">
              <span className="font-mono text-xs font-bold uppercase text-white flex items-center gap-1.5">
                <Truck className="w-3.5 h-3.5 text-[#ffb870]" />
                Tactical Units Mobilized
              </span>
              <span className="text-[10px] font-mono text-[#ffb870] bg-[#7d4800]/40 px-2 py-0.5 rounded">
                {tacticalUnits.length} TEAMS IN DB
              </span>
            </div>

            <div className="mb-2.5 rounded border border-amber-500/30 bg-amber-950/20 px-2.5 py-1.5 text-[10px] font-mono text-amber-300">
              NOTE: Unit dispatch updates the central command database &amp; audit log. External VHF/SATCOM field hardware relay is simulated.
            </div>

            {unitsLoading ? (
              <div className="text-xs text-[#8a9297] py-3 font-mono">Loading tactical response units...</div>
            ) : unitsError ? (
              <div className="text-xs text-[#ffb4ab] py-2">{unitsError}</div>
            ) : tacticalUnits.length === 0 ? (
              <div className="text-xs text-[#8a9297] py-2">No tactical units available in database.</div>
            ) : (
              <div className="space-y-2.5">
                {tacticalUnits.map((unit) => {
                  const draft = unitDispatchDrafts[unit.id] || {
                    destination: unit.destination || activeTarget.corridor,
                    status: unit.status,
                    priority: 'URGENT' as const,
                  };
                  return (
                    <div
                      key={unit.id}
                      className="bg-[#122131] border border-[#1c2b3c] p-3 rounded-lg text-xs space-y-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-white">{unit.name}</span>
                        <span className="text-[9px] font-mono font-bold bg-[#00363e] text-[#44d8f1] px-1.5 py-0.5 rounded">
                          {unit.statusLabel || unit.status}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#bfc8cd]">{unit.description}</p>
                      <div className="flex items-center justify-between text-[10px] font-mono text-[#8a9297] pt-1 border-t border-[#1c2b3c]">
                        <span>Destination: <strong className="text-white">{unit.destination}</strong></span>
                        <span>Personnel: {unit.personnel}</span>
                      </div>

                      {/* Interactive Dispatch Controls */}
                      <div className="pt-1.5 border-t border-[#1c2b3c] space-y-1.5">
                        <input
                          type="text"
                          value={draft.destination}
                          onChange={(e) =>
                            setUnitDispatchDrafts((prev) => ({
                              ...prev,
                              [unit.id]: { ...draft, destination: e.target.value },
                            }))
                          }
                          placeholder="Target corridor / sector..."
                          className="w-full bg-[#051424] text-white border border-[#273647] rounded px-2 py-1 text-[11px]"
                        />
                        <div className="flex items-center gap-1.5">
                          <select
                            aria-label={`Status for ${unit.name}`}
                            value={draft.status}
                            onChange={(e) =>
                              setUnitDispatchDrafts((prev) => ({
                                ...prev,
                                [unit.id]: { ...draft, status: e.target.value as TacticalUnit['status'] },
                              }))
                            }
                            className="bg-[#051424] text-white border border-[#273647] rounded px-1.5 py-1 text-[10px] font-mono"
                          >
                            <option value="EN ROUTE">EN ROUTE</option>
                            <option value="ON SCENE">ON SCENE</option>
                            <option value="ACTIVE">ACTIVE</option>
                            <option value="DEBRIS CLEARING">DEBRIS CLEARING</option>
                            <option value="STANDBY">STANDBY</option>
                          </select>
                          <select
                            aria-label={`Priority for ${unit.name}`}
                            value={draft.priority}
                            onChange={(e) =>
                              setUnitDispatchDrafts((prev) => ({
                                ...prev,
                                [unit.id]: {
                                  ...draft,
                                  priority: e.target.value as 'CRITICAL' | 'URGENT' | 'ROUTINE',
                                },
                              }))
                            }
                            className="bg-[#051424] text-white border border-[#273647] rounded px-1.5 py-1 text-[10px] font-mono"
                          >
                            <option value="CRITICAL">CRITICAL</option>
                            <option value="URGENT">URGENT</option>
                            <option value="ROUTINE">ROUTINE</option>
                          </select>
                          <button
                            onClick={() => handleDispatchUnit(unit)}
                            disabled={dispatchingUnitId === unit.id}
                            className="ml-auto px-2.5 py-1 rounded bg-[#7d4800] hover:bg-[#995800] text-[#ffb870] font-mono font-bold text-[10px] cursor-pointer disabled:opacity-50"
                          >
                            {dispatchingUnitId === unit.id ? 'SAVING...' : 'DISPATCH / UPDATE'}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Official SDMA Dispatch Audit Log */}
      <div className="bg-[#0d1c2d] border border-[#1c2b3c] rounded-xl p-4 shadow-xl">
        <div className="flex items-center justify-between border-b border-[#1c2b3c] pb-3 mb-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-[#44d8f1]" />
            <h3 className="text-xs sm:text-sm font-bold text-white uppercase tracking-wider">
              State Disaster Management Authority (SDMA) Dispatch Audit Stream
            </h3>
          </div>
          <span className="text-[10px] font-mono text-[#8a9297]">
            CRYPTOGRAPHIC LEDGER • SEC 30 DMA 2005
          </span>
        </div>

        <div className="space-y-2.5">
          {auditList.map((log) => (
            <div
              key={log.id}
              className={`p-3 rounded-lg border text-xs transition-all ${
                log.highlight
                  ? 'bg-[#122131] border-[#ffb4ab]/50 shadow-md'
                  : 'bg-[#122131]/60 border-[#1c2b3c]'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-1 mb-1 font-mono text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-[#44d8f1]">{log.code}</span>
                  <span className="text-white font-semibold">{log.title}</span>
                </div>
                <span className="text-[#8a9297]">{log.timestamp}</span>
              </div>
              <p className="text-[#bfc8cd] text-xs leading-relaxed">{log.message}</p>
              <div className="mt-1.5 text-[10px] font-mono text-[#8a9297]">
                Authority: {log.authority}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
