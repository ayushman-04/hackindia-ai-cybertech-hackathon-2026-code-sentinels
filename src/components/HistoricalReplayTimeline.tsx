import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Pause, Play, RotateCcw } from 'lucide-react';

export interface HistoricalReplayRange {
  from: number;
  to: number;
}

export interface HistoricalReplayTimelineProps {
  minYear?: number;
  maxYear?: number;
  yearCounts?: { year: number; count: number }[];
  value?: HistoricalReplayRange | null;
  onChange?: (value: HistoricalReplayRange | null) => void;
}

const FALLBACK_MIN_YEAR = 2009;
const FALLBACK_MAX_YEAR = 2022;
const DRAG_DEBOUNCE_MS = 90;
const PLAYBACK_INTERVAL_MS = 1200;

export const HistoricalReplayTimeline: React.FC<HistoricalReplayTimelineProps> = ({
  minYear = FALLBACK_MIN_YEAR,
  maxYear = FALLBACK_MAX_YEAR,
  yearCounts = [],
  value = null,
  onChange = (_val: HistoricalReplayRange | null = null) => undefined,
}) => {
  const safeMinYear = Math.min(minYear, maxYear);
  const safeMaxYear = Math.max(minYear, maxYear);
  const activeRange = value ?? { from: safeMinYear, to: safeMaxYear };
  const [draftRange, setDraftRange] = useState<HistoricalReplayRange>(activeRange);
  const [isPlaying, setIsPlaying] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const draftRef = useRef(draftRange);

  const countsByYear = useMemo(
    () => new Map(yearCounts.map((entry) => [entry.year, entry.count])),
    [yearCounts]
  );
  const maxCount = Math.max(1, ...yearCounts.map((entry) => entry.count));
  const yearTicks = Array.from(
    { length: safeMaxYear - safeMinYear + 1 },
    (_, index) => safeMinYear + index
  );

  useEffect(() => {
    const nextRange = value ?? { from: safeMinYear, to: safeMaxYear };
    setDraftRange(nextRange);
    draftRef.current = nextRange;
  }, [safeMaxYear, safeMinYear, value]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!isPlaying) return;

    const timer = window.setInterval(() => {
      const current = draftRef.current;
      const nextYear = current.from >= safeMaxYear ? safeMinYear : current.from + 1;
      const nextRange = { from: nextYear, to: nextYear };
      draftRef.current = nextRange;
      setDraftRange(nextRange);
      onChange(nextRange);
    }, PLAYBACK_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [isPlaying, onChange, safeMaxYear, safeMinYear]);

  const emitDebounced = (nextRange: HistoricalReplayRange) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      onChange(nextRange);
      debounceRef.current = null;
    }, DRAG_DEBOUNCE_MS);
  };

  const commitDraft = () => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    onChange(draftRef.current);
  };

  const updateDraft = (range: HistoricalReplayRange) => {
    const nextRange = {
      from: Math.max(safeMinYear, Math.min(range.from, safeMaxYear)),
      to: Math.max(safeMinYear, Math.min(range.to, safeMaxYear)),
    };
    if (nextRange.from > nextRange.to) {
      nextRange.from = nextRange.to;
    }
    draftRef.current = nextRange;
    setDraftRange(nextRange);
    emitDebounced(nextRange);
  };

  const handleReset = () => {
    setIsPlaying(false);
    const resetRange = { from: safeMinYear, to: safeMaxYear };
    draftRef.current = resetRange;
    setDraftRange(resetRange);
    onChange(null);
  };

  return (
    <div className="mt-4 rounded-xl border border-cyan-400/20 bg-[#071522]/80 p-3 text-slate-200 shadow-inner">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-cyan-300">
            Historical Time Replay
          </div>
          <div className="mt-1 text-[11px] text-slate-400">
            {value ? `${draftRange.from} - ${draftRange.to}` : 'All years'}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setIsPlaying((playing) => !playing)}
            className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 p-1.5 text-cyan-200 transition-colors hover:bg-cyan-500/25"
            title={isPlaying ? 'Pause historical replay' : 'Play historical replay'}
            aria-label={isPlaying ? 'Pause historical replay' : 'Play historical replay'}
          >
            {isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="rounded-lg border border-slate-600 bg-slate-800/80 p-1.5 text-slate-300 transition-colors hover:bg-slate-700"
            title="Reset historical replay to all years"
            aria-label="Reset historical replay to all years"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="relative mt-4 px-1">
        <div className="flex h-10 items-end gap-0.5">
          {yearTicks.map((year) => (
            <div key={year} className="flex min-w-0 flex-1 items-end justify-center">
              <div
                className="w-full rounded-t-sm bg-cyan-400/60 transition-all"
                style={{ height: `${Math.max(3, ((countsByYear.get(year) ?? 0) / maxCount) * 30)}px` }}
                title={`${year}: ${countsByYear.get(year) ?? 0} events`}
              />
            </div>
          ))}
        </div>
        <div className="pointer-events-none absolute inset-x-1 bottom-0 h-1 rounded-full bg-cyan-950" />
        <div className="mt-1 flex justify-between text-[9px] font-mono text-slate-500">
          <span>{safeMinYear}</span>
          <span>{safeMaxYear}</span>
        </div>

        <div className="relative mt-2 h-6">
          <input
            type="range"
            min={safeMinYear}
            max={safeMaxYear}
            value={draftRange.from}
            onChange={(event) => updateDraft({ from: Number(event.target.value), to: draftRange.to })}
            onPointerUp={commitDraft}
            onTouchEnd={commitDraft}
            className="historical-replay-range absolute inset-x-0 top-0 z-20 h-2 w-full cursor-pointer appearance-none bg-transparent accent-cyan-400"
            aria-label="Historical replay start year"
          />
          <input
            type="range"
            min={safeMinYear}
            max={safeMaxYear}
            value={draftRange.to}
            onChange={(event) => updateDraft({ from: draftRange.from, to: Number(event.target.value) })}
            onPointerUp={commitDraft}
            onTouchEnd={commitDraft}
            className="historical-replay-range absolute inset-x-0 top-0 z-10 h-2 w-full cursor-pointer appearance-none bg-transparent accent-cyan-400"
            aria-label="Historical replay end year"
          />
        </div>
      </div>
    </div>
  );
};
