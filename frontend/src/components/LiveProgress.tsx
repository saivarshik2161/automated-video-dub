import React from 'react';
import { PipelineStage } from '../types';
import { Check, Loader2, Circle, Clock } from 'lucide-react';
import { formatTime } from '../lib/utils';

interface LiveProgressProps {
  currentStage: PipelineStage | string;
  stagePercent: number;
  overallPercent: number;
  currentMessage: string;
  elapsedSeconds: number;
  completedStages: Set<string>;
}

const STAGES: { key: PipelineStage; name: string }[] = [
  { key: 'download', name: 'Download' },
  { key: 'transcribe', name: 'Transcribe' },
  { key: 'translate', name: 'Translate' },
  { key: 'synthesize', name: 'Synthesize' },
  { key: 'align', name: 'Align' },
  { key: 'remix', name: 'Remix' },
];

export const LiveProgress: React.FC<LiveProgressProps> = ({
  currentStage,
  stagePercent,
  overallPercent,
  currentMessage,
  elapsedSeconds,
  completedStages,
}) => {
  return (
    <div className="bg-white/95 backdrop-blur-md rounded-2xl border border-slate-200/90 p-5 sm:p-7 shadow-sm mb-6">
      {/* Top Header with Overall Percentage */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-700">
            Real-time Pipeline
          </span>
          <h3 className="text-xl font-extrabold text-black mt-0.5">
            {overallPercent >= 100 ? 'Dubbing Completed' : 'Processing Video...'}
          </h3>
          <p className="text-sm text-slate-800 mt-1 font-mono font-medium truncate max-w-lg">
            {currentMessage || 'Waiting for events...'}
          </p>
        </div>

        <div className="flex items-center gap-4 sm:text-right">
          <div className="flex items-center gap-1.5 text-xs text-slate-900 font-semibold bg-slate-100 border border-slate-300 px-3 py-1.5 rounded-lg shadow-xs">
            <Clock className="w-3.5 h-3.5 text-slate-700" />
            <span className="font-mono">{formatTime(elapsedSeconds)}</span>
          </div>

          <div>
            <span className="text-2xl sm:text-3xl font-extrabold text-indigo-700 font-mono">
              {overallPercent}%
            </span>
          </div>
        </div>
      </div>

      {/* Main Overall Progress Bar */}
      <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden mb-8 border border-slate-200/50">
        <div
          className="h-full bg-indigo-600 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${Math.min(Math.max(overallPercent, 0), 100)}%` }}
        />
      </div>

      {/* 6 Stage Trackers */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
        {STAGES.map((s) => {
          const isDone = completedStages.has(s.key) || overallPercent >= 100;
          const isActive = currentStage === s.key && !isDone;

          return (
            <div
              key={s.key}
              className={`p-3 rounded-xl border transition-all ${
                isDone
                  ? 'bg-emerald-50/70 border-emerald-300 text-emerald-950 font-semibold'
                  : isActive
                  ? 'bg-indigo-50/80 border-indigo-400 text-indigo-950 shadow-sm font-semibold'
                  : 'bg-slate-50 border-slate-200 text-slate-800'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-slate-900">{s.name}</span>
                {isDone ? (
                  <div className="w-4 h-4 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                    <Check className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                ) : isActive ? (
                  <Loader2 className="w-4 h-4 text-indigo-700 animate-spin" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-slate-400" />
                )}
              </div>

              <div className="flex items-baseline justify-between text-[11px] font-mono">
                <span className={isActive ? 'text-indigo-800 font-extrabold' : isDone ? 'text-emerald-800 font-bold' : 'text-slate-700 font-medium'}>
                  {isDone ? '100%' : isActive ? `${stagePercent}%` : '0%'}
                </span>
                <span className="text-[10px] text-slate-600 font-semibold uppercase tracking-wider">
                  {isDone ? 'Done' : isActive ? 'Active' : 'Pending'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
