import React from 'react';
import { JobOptions } from '../types';
import { Users, Music, Mic, Layers, Info } from 'lucide-react';

interface OptionsPanelProps {
  options: JobOptions;
  onChange: (options: JobOptions) => void;
  disabled?: boolean;
}

export const OptionsPanel: React.FC<OptionsPanelProps> = ({
  options,
  onChange,
  disabled = false,
}) => {
  return (
    <div className="bg-white rounded-2xl border border-slate-300 p-5 sm:p-6 shadow-md mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-5 border-b border-slate-200 gap-2">
        <div>
          <h3 className="text-base font-bold text-slate-950">Pipeline Options</h3>
          <p className="text-xs text-slate-800 font-medium">Configure speech recognition, voices, and audio remixing</p>
        </div>

        {/* Translation Model Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-300 text-xs text-slate-950 font-medium">
          <Layers className="w-3.5 h-3.5 text-indigo-700" />
          <span>Translation:</span>
          <span className="font-bold text-indigo-900">IndicTrans2</span>
          <span className="text-[11px] text-slate-700 font-semibold hidden sm:inline">(Indic → English)</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        {/* 1. Speaker Mode */}
        <div className="flex flex-col justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-200">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-4 h-4 text-slate-900" />
            <span className="text-sm font-bold text-black">Speaker Mode</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-200 rounded-lg">
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange({ ...options, multi_speaker: false })}
              className={`py-1.5 px-2 rounded-md text-xs font-bold transition-all ${
                !options.multi_speaker
                  ? 'bg-white text-indigo-950 shadow-sm'
                  : 'text-slate-800 hover:text-black'
              }`}
            >
              Single Speaker
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange({ ...options, multi_speaker: true })}
              className={`py-1.5 px-2 rounded-md text-xs font-bold transition-all ${
                options.multi_speaker
                  ? 'bg-white text-indigo-950 shadow-sm'
                  : 'text-slate-800 hover:text-black'
              }`}
            >
              Multi Speaker
            </button>
          </div>
        </div>

        {/* 2. Background Music */}
        <div className="flex flex-col justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-200">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Music className="w-4 h-4 text-slate-900" />
              <span className="text-sm font-bold text-black">Background Audio</span>
            </div>
            <input
              type="checkbox"
              id="bgMusic"
              disabled={disabled}
              checked={options.keep_background_music}
              onChange={(e) => onChange({ ...options, keep_background_music: e.target.checked })}
              className="w-4 h-4 text-indigo-600 rounded border-slate-400 focus:ring-indigo-600 cursor-pointer"
            />
          </div>
          <label htmlFor="bgMusic" className="text-xs text-slate-900 font-medium cursor-pointer">
            Preserve background ambient music track alongside English voice
          </label>
        </div>

        {/* 3. Voice Cloning (Disabled stretch goal) */}
        <div className="flex flex-col justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-200 opacity-80">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <Mic className="w-4 h-4 text-slate-700" />
              <span className="text-sm font-bold text-slate-900">Voice Cloning</span>
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-900">
              Advanced / High VRAM
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-800 font-medium mt-2">
            <Info className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
            <span>Optional stretch feature (Disabled to ensure core pipeline reliability)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
