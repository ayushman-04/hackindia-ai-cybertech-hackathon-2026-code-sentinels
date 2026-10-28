import React, { useState, useEffect } from 'react';
import { HazardZone, OperationalModule } from '../types';
import { LIVE_VIEW_IMAGES } from '../data/mockData';
import {
  MapPin,
  Search,
  AlertTriangle,
  Zap,
  CloudRain,
  Droplets,
  TrendingUp,
  Map,
  BellRing,
  ShieldAlert,
  PhoneCall,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Shield,
  Activity,
  ArrowUpRight,
  Radio,
  Loader2,
} from 'lucide-react';
import { useI18n } from '../i18n/index.tsx';
import { LandslideApi, LiveWeather } from '../services/api';

function parseCoordinates(coordStr?: string): { latitude?: number; longitude?: number } {
  if (!coordStr) return {};
  const cleaned = coordStr.replace(/[°NSEW]/gi, '').trim();
  const parts = cleaned.split(',');
  if (parts.length >= 2) {
    const lat = parseFloat(parts[0].trim());
    const lon = parseFloat(parts[1].trim());
    if (!isNaN(lat) && !isNaN(lon)) return { latitude: lat, longitude: lon };
  }
  return {};
}

interface TerraDashboardProps {
  selectedZone: HazardZone;
  onSelectZone: (zone: HazardZone) => void;
  zones: HazardZone[];
  onNavigate: (module: OperationalModule) => void;
  theme: 'dark' | 'light';
}

export const TerraDashboard: React.FC<TerraDashboardProps> = ({
  selectedZone,
  onSelectZone,
  zones,
  onNavigate,
  theme,
}) => {
  const { t } = useI18n();
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [searchLocation, setSearchLocation] = useState(selectedZone.name);
  const [currentTime, setCurrentTime] = useState('');

  useEffect(() => {
    setSearchLocation(selectedZone.name);
  }, [selectedZone]);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleDateString('en-IN', {
          weekday: 'short',
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleNextImage = () => {
    setCurrentImageIndex((prev) => (prev + 1) % LIVE_VIEW_IMAGES.length);
  };

  const handlePrevImage = () => {
    setCurrentImageIndex((prev) => (prev - 1 + LIVE_VIEW_IMAGES.length) % LIVE_VIEW_IMAGES.length);
  };

  const [weather, setWeather] = useState<LiveWeather | null>(null);
  const [weatherLoading, setWeatherLoading] = useState<boolean>(true);
  const [weatherError, setWeatherError] = useState<string | null>(null);
  const [warningWeather, setWarningWeather] = useState<Record<string, LiveWeather>>({});
  const [warningWeatherLoading, setWarningWeatherLoading] = useState<boolean>(false);

  // Fetch live meteorological telemetry for selected zone
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setWeatherLoading(true);
    setWeatherError(null);

    const coords = parseCoordinates(selectedZone.coords);

    LandslideApi.getLiveWeather(
      {
        state: selectedZone.state,
        latitude: coords.latitude,
        longitude: coords.longitude,
        regionName: selectedZone.name,
      },
      controller.signal
    )
      .then((data) => {
        if (!active) return;
        if (!data || !data.is_live_feed) {
          setWeather(null);
          setWeatherError('Telemetry unavailable');
        } else {
          setWeather(data);
          setWeatherError(null);
        }
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        if (active) {
          setWeather(null);
          setWeatherError('Weather feed unavailable');
        }
      })
      .finally(() => {
        if (active) {
          setWeatherLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [selectedZone.id, selectedZone.state, selectedZone.coords, selectedZone.name]);

  // High & Medium warning zones
  const warningZones = zones.filter(
    (z) => z.riskStatus === 'CRITICAL RED' || z.riskStatus === 'ADVISORY ORANGE'
  );

  // Fetch live weather for warning zones
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setWarningWeatherLoading(true);

    const fetchWarningWeather = async () => {
      const results: Record<string, LiveWeather> = {};
      await Promise.all(
        warningZones.map(async (zone) => {
          try {
            const coords = parseCoordinates(zone.coords);
            const data = await LandslideApi.getLiveWeather(
              {
                state: zone.state,
                latitude: coords.latitude,
                longitude: coords.longitude,
                regionName: zone.name,
              },
              controller.signal
            );
            if (data && data.is_live_feed) {
              results[zone.id] = data;
            }
          } catch {
            // Zone telemetry unavailable
          }
        })
      );
      if (active) {
        setWarningWeather(results);
        setWarningWeatherLoading(false);
      }
    };

    fetchWarningWeather();

    return () => {
      active = false;
      controller.abort();
    };
  }, [zones]);

  return (
    <div className="space-y-6 pb-16 font-sans">
      {/* Top Search & Live Time Bar (Screen 2 Mockup) */}
      <div
        className={`p-4 rounded-2xl border flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm ${
          theme === 'light'
            ? 'bg-white border-slate-200 text-slate-900'
            : 'bg-[#0d1c2d] border-[#1c2b3c] text-white'
        }`}
      >
        {/* Location Dropdown / Search */}
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <MapPin className="w-4 h-4 text-emerald-500" />
            </div>
            <select
              value={selectedZone.id}
              onChange={(e) => {
                const z = zones.find((item) => item.id === e.target.value);
                if (z) onSelectZone(z);
              }}
              className={`w-full pl-9 pr-8 py-2 rounded-xl text-xs sm:text-sm font-semibold border appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-400 transition-all ${
                theme === 'light'
                  ? 'bg-slate-50 border-slate-300 text-slate-900'
                  : 'bg-[#122131] border-[#273647] text-white'
              }`}
            >
              {zones.map((z) => (
                <option key={z.id} value={z.id}>
                  {z.name} ({z.subDivision})
                </option>
              ))}
            </select>
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-slate-400">
              <span className="text-xs">▼</span>
            </div>
          </div>

          <button
            onClick={() => onNavigate('risk-details')}
            className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl text-xs sm:text-sm tracking-wide shadow cursor-pointer transition-all flex-shrink-0"
          >
            {t('dashboard.check')}
          </button>
        </div>

        {/* Live Date / Time & Status Indicator */}
        <div className="flex items-center gap-3 self-end md:self-auto text-xs font-mono">
          <span className="text-slate-500 dark:text-slate-400">
            {currentTime || 'Mon, 2 Sep 2024 03:45 PM'}
          </span>
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/30 font-bold text-[11px]">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            {t('dashboard.liveData')}
          </span>
        </div>
      </div>

      {/* Main Grid: Current Risk Level + Live Optical View (Screen 2 Mockup) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Current Risk Level Card (7 cols) */}
        <div
          className={`lg:col-span-7 p-6 rounded-2xl border flex flex-col justify-between shadow-md ${
            theme === 'light'
              ? 'bg-white border-slate-200 text-slate-900'
              : 'bg-[#0d1c2d] border-[#1c2b3c] text-white'
          }`}
        >
          <div>
            <span className="text-xs font-mono font-bold uppercase text-slate-400 tracking-wider">
              {t('dashboard.currentRiskLevel')}
            </span>

            {/* Risk Badge Header */}
            <div className="mt-3 flex items-center gap-3">
              <div
                className={`w-12 h-12 rounded-2xl flex items-center justify-center ${
                  selectedZone.riskStatus === 'CRITICAL RED'
                    ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                    : 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                }`}
              >
                <AlertTriangle className="w-7 h-7 animate-pulse" />
              </div>
              <div>
                <h2 className="text-2xl sm:text-3xl font-black text-red-500 tracking-tight">
                  {selectedZone.riskStatus === 'CRITICAL RED' ? t('dashboard.highRisk') : t('dashboard.moderateRisk')}
                </h2>
                <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 font-medium">
                  {t('dashboard.riskWindow')}
                </p>
              </div>
            </div>

            {/* Key Metrics Strip (Screen 2 Mockup) */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
              {/* Metric 1: Risk Score */}
              <div
                className={`p-3 rounded-xl border ${
                  theme === 'light'
                    ? 'bg-slate-50 border-slate-200'
                    : 'bg-[#122131] border-[#1c2b3c]'
                }`}
              >
                <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400">
                  <Zap className="w-3.5 h-3.5 text-red-400" />
                  {t('dashboard.riskScore')}
                </span>
                <span className="text-lg sm:text-xl font-bold font-mono text-red-500 block mt-1">
                  {selectedZone.rfConfidence || '78%'}
                </span>
              </div>

              {/* Metric 2: Live Rainfall */}
              <div
                className={`p-3 rounded-xl border ${
                  theme === 'light'
                    ? 'bg-slate-50 border-slate-200'
                    : 'bg-[#122131] border-[#1c2b3c]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400">
                    <CloudRain className="w-3.5 h-3.5 text-cyan-400" />
                    72H ANTECEDENT RAIN
                  </span>
                  {weatherLoading && (
                    <Loader2 className="w-3 h-3 animate-spin text-cyan-400" />
                  )}
                </div>
                {weatherLoading ? (
                  <span className="text-sm font-bold font-mono text-slate-400 block mt-1">
                    Loading...
                  </span>
                ) : weatherError || !weather || !weather.is_live_feed ? (
                  <div className="mt-1">
                    <span className="text-sm font-bold font-mono text-amber-500 block">
                      Unavailable
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono block">
                      {weatherError || 'Feed offline'}
                    </span>
                  </div>
                ) : (
                  <div className="mt-1">
                    <span className="text-lg sm:text-xl font-bold font-mono text-cyan-400 block">
                      {weather.antecedent_72h_rainfall_mm.toFixed(1)} mm
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono block">
                      Rate: {weather.current_rainfall_mm_hr.toFixed(1)} mm/h
                    </span>
                  </div>
                )}
              </div>

              {/* Metric 3: Soil Moisture */}
              <div
                className={`p-3 rounded-xl border ${
                  theme === 'light'
                    ? 'bg-slate-50 border-slate-200'
                    : 'bg-[#122131] border-[#1c2b3c]'
                }`}
              >
                <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400">
                  <Droplets className="w-3.5 h-3.5 text-amber-400" />
                  {t('dashboard.soilMoisture')}
                </span>
                <span className="text-lg sm:text-xl font-bold font-mono text-amber-400 block mt-1">
                  {selectedZone.soilPoreSaturation}
                </span>
              </div>

              {/* Metric 4: Slope Angle */}
              <div
                className={`p-3 rounded-xl border ${
                  theme === 'light'
                    ? 'bg-slate-50 border-slate-200'
                    : 'bg-[#122131] border-[#1c2b3c]'
                }`}
              >
                <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400">
                  <TrendingUp className="w-3.5 h-3.5 text-red-400" />
                  {t('dashboard.slopeAngle')}
                </span>
                <span className="text-lg sm:text-xl font-bold font-mono text-white block mt-1">
                  {selectedZone.slopeGradient}
                </span>
              </div>
            </div>
          </div>

          {/* Safety Advisory Banner */}
          <div className="mt-6 p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 flex items-start gap-2.5 text-xs">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span className="font-medium">
              Heavy rainfall and vulnerable terrain detected along {selectedZone.highwaySegment}.
              Avoid non-essential travel to high-risk areas.
            </span>
          </div>
        </div>

        {/* Right: Live View Carousel Card (5 cols) */}
        <div
          className={`lg:col-span-5 p-6 rounded-2xl border flex flex-col justify-between shadow-md ${
            theme === 'light'
              ? 'bg-white border-slate-200 text-slate-900'
              : 'bg-[#0d1c2d] border-[#1c2b3c] text-white'
          }`}
        >
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold uppercase text-slate-400 tracking-wider">
                {t('dashboard.liveView')}
              </span>
              <span className="text-[10px] font-mono text-cyan-400 flex items-center gap-1">
                <Radio className="w-3 h-3 animate-pulse" />
                UAV QUAD-402
              </span>
            </div>

            {/* Image Preview Box with Carousel */}
            <div className="mt-3 relative rounded-xl overflow-hidden border border-slate-700/50 group h-52 sm:h-56 bg-black">
              <img
                src={LIVE_VIEW_IMAGES[currentImageIndex].url}
                alt={LIVE_VIEW_IMAGES[currentImageIndex].caption}
                className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
              />

              {/* High Risk Area Badge Overlay */}
              <div className="absolute top-2.5 right-2.5 bg-red-600/90 text-white font-mono font-bold text-[10px] px-2 py-0.5 rounded-md shadow uppercase tracking-wide">
                {LIVE_VIEW_IMAGES[currentImageIndex].label}
              </div>

              {/* Bottom Caption Overlay */}
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-3 text-white">
                <p className="text-xs font-semibold truncate">
                  {LIVE_VIEW_IMAGES[currentImageIndex].caption}
                </p>
                <span className="text-[10px] font-mono text-slate-300">
                  {LIVE_VIEW_IMAGES[currentImageIndex].time}
                </span>
              </div>
            </div>
          </div>

          {/* Carousel Slider Controls < 1/3 > */}
          <div className="mt-3 flex items-center justify-between text-xs font-mono text-slate-400">
            <button
              onClick={handlePrevImage}
              className="p-1 rounded hover:bg-slate-700/40 text-slate-300 cursor-pointer"
              title="Previous drone scan"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <span>
              {currentImageIndex + 1} / {LIVE_VIEW_IMAGES.length}
            </span>

            <button
              onClick={handleNextImage}
              className="p-1 rounded hover:bg-slate-700/40 text-slate-300 cursor-pointer"
              title="Next drone scan"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 4 Quick Action Cards (Screen 2 Mockup) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Action 1: View Risk Map */}
        <div
          onClick={() => onNavigate('risk-map')}
          className={`p-4 rounded-xl border flex items-center gap-3.5 transition-all cursor-pointer group hover:shadow-md ${
            theme === 'light'
              ? 'bg-white hover:bg-slate-50 border-slate-200 text-slate-900'
              : 'bg-[#0d1c2d] hover:bg-[#122131] border-[#1c2b3c] text-white'
          }`}
        >
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
            <Map className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-bold truncate">{t('dashboard.viewRiskMap')}</h4>
            <p className="text-[11px] text-slate-400 truncate">{t('dashboard.exploreRiskZones')}</p>
          </div>
          <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-500 transition-colors" />
        </div>

        {/* Action 2: Check Alerts */}
        <div
          onClick={() => onNavigate('alerts')}
          className={`p-4 rounded-xl border flex items-center gap-3.5 transition-all cursor-pointer group hover:shadow-md ${
            theme === 'light'
              ? 'bg-white hover:bg-slate-50 border-slate-200 text-slate-900'
              : 'bg-[#0d1c2d] hover:bg-[#122131] border-[#1c2b3c] text-white'
          }`}
        >
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
            <BellRing className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-bold truncate">{t('dashboard.checkAlerts')}</h4>
            <p className="text-[11px] text-slate-400 truncate">{t('dashboard.latestWarnings')}</p>
          </div>
          <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-amber-500 transition-colors" />
        </div>

        {/* Action 3: Emergency SOS */}
        <div
          onClick={() => onNavigate('emergency-sos')}
          className={`p-4 rounded-xl border flex items-center gap-3.5 transition-all cursor-pointer group hover:shadow-md ${
            theme === 'light'
              ? 'bg-white hover:bg-slate-50 border-slate-200 text-slate-900'
              : 'bg-[#0d1c2d] hover:bg-[#122131] border-[#1c2b3c] text-white'
          }`}
        >
          <div className="w-10 h-10 rounded-xl bg-red-500/10 text-red-500 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-bold truncate">{t('dashboard.emergencySos')}</h4>
            <p className="text-[11px] text-slate-400 truncate">{t('dashboard.getHelpNow')}</p>
          </div>
          <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-red-500 transition-colors" />
        </div>

        {/* Action 4: Nearby Helplines */}
        <div
          onClick={() => onNavigate('emergency-sos')}
          className={`p-4 rounded-xl border flex items-center gap-3.5 transition-all cursor-pointer group hover:shadow-md ${
            theme === 'light'
              ? 'bg-white hover:bg-slate-50 border-slate-200 text-slate-900'
              : 'bg-[#0d1c2d] hover:bg-[#122131] border-[#1c2b3c] text-white'
          }`}
        >
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-500 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
            <PhoneCall className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-bold truncate">{t('dashboard.nearbyHelplines')}</h4>
            <p className="text-[11px] text-slate-400 truncate">{t('dashboard.importantContacts')}</p>
          </div>
          <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-cyan-500 transition-colors" />
        </div>
      </div>

      {/* High and Medium Warning Zones Live Telemetry Summary (User Request) */}
      <div
        className={`p-6 rounded-2xl border shadow-sm ${
          theme === 'light'
            ? 'bg-white border-slate-200 text-slate-900'
            : 'bg-[#0d1c2d] border-[#1c2b3c] text-white'
        }`}
      >
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span>{t('dashboard.warningZones')}</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {t('dashboard.warningZonesDescription')}
            </p>
          </div>
          <span className="text-xs font-mono font-bold px-2.5 py-1 rounded bg-red-500/10 text-red-500 border border-red-500/30">
            {warningZones.length} {t('dashboard.corridorsActive')}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
          {warningZones.map((zone) => (
            <div
              key={zone.id}
              onClick={() => {
                onSelectZone(zone);
                onNavigate('risk-details');
              }}
              className={`p-4 rounded-xl border transition-all cursor-pointer hover:scale-[1.02] shadow-sm ${
                zone.riskStatus === 'CRITICAL RED'
                  ? 'border-red-500/40 bg-red-500/5 hover:border-red-500'
                  : 'border-amber-500/40 bg-amber-500/5 hover:border-amber-500'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm truncate">{zone.name}</span>
                <span
                  className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                    zone.riskStatus === 'CRITICAL RED'
                      ? 'bg-red-500 text-white'
                      : 'bg-amber-500 text-slate-950'
                  }`}
                >
                  {zone.riskStatus === 'CRITICAL RED' ? 'HIGH' : 'MODERATE'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{zone.corridor}</p>

              {/* Data metrics */}
              <div className="grid grid-cols-2 gap-2 mt-3 text-xs font-mono">
                <div>
                  <span className="text-slate-400 block text-[10px]">72H RAINFALL</span>
                  {warningWeatherLoading && !warningWeather[zone.id] ? (
                    <span className="text-slate-400 font-mono text-[11px]">Loading...</span>
                  ) : warningWeather[zone.id]?.is_live_feed ? (
                    <div>
                      <span className="font-bold text-cyan-500">
                        {warningWeather[zone.id].antecedent_72h_rainfall_mm.toFixed(1)} mm
                      </span>
                      <span className="text-[9px] text-slate-400 block font-normal">
                        Rate: {warningWeather[zone.id].current_rainfall_mm_hr.toFixed(1)} mm/h
                      </span>
                    </div>
                  ) : (
                    <span className="text-amber-500 font-mono text-[11px]">Unavailable</span>
                  )}
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">SOIL MOISTURE</span>
                  <span className="font-bold text-amber-500">{zone.soilPoreSaturation}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">SLOPE GRADIENT</span>
                  <span className="font-bold text-slate-200 dark:text-white">{zone.slopeGradient}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">{t('dashboard.leadTimeEvac')}</span>
                  <span className="font-bold text-emerald-500">{zone.lstmEvac}</span>
                </div>
              </div>

              <div className="mt-3 pt-2.5 border-t border-slate-700/30 flex items-center justify-between text-[11px]">
                <span className="text-slate-400 font-mono">{zone.populationRunout}</span>
                <span className="text-emerald-500 font-bold flex items-center gap-0.5">
                  {t('dashboard.inspect')} <ChevronRight className="w-3 h-3" />
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
