import React from 'react';
import { 
  DownloadCloud, 
  Mic2, 
  Languages, 
  Volume2, 
  Sliders, 
  Film 
} from 'lucide-react';

const STAGES = [
  {
    num: '01',
    title: 'Download',
    desc: 'Extracts the source video stream using yt-dlp in high-definition MP4 format.',
    icon: DownloadCloud,
    tag: 'yt-dlp',
  },
  {
    num: '02',
    title: 'Transcribe',
    desc: 'Whisper performs multilingual speech recognition and detects segment boundaries.',
    icon: Mic2,
    tag: 'Whisper',
  },
  {
    num: '03',
    title: 'Translate',
    desc: 'IndicTrans2 neural model converts transcript into natural, context-aware English.',
    icon: Languages,
    tag: 'IndicTrans2',
  },
  {
    num: '04',
    title: 'Synthesize',
    desc: 'Edge-TTS generates natural human-like English audio for each individual segment.',
    icon: Volume2,
    tag: 'Edge-TTS',
  },
  {
    num: '05',
    title: 'Align',
    desc: 'Aligns speech timestamps and applies tempo scaling (atempo) to preserve lip timing.',
    icon: Sliders,
    tag: 'FFmpeg Tempo',
  },
  {
    num: '06',
    title: 'Remix',
    desc: 'Stream-copies original video stream with the aligned English audio into final MP4.',
    icon: Film,
    tag: 'Stream Copy',
  },
];

export const HowItWorksSection: React.FC = () => {
  return (
    <section className="relative py-20 px-4 sm:px-6 max-w-6xl mx-auto z-10">
      <div className="text-center max-w-2xl mx-auto mb-16">
        <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-700 mb-2">
          Architecture
        </h2>
        <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-950">
          How the Dubbing Pipeline Works
        </h3>
        <p className="mt-3 text-slate-900 font-medium text-sm sm:text-base">
          Six synchronized stages transform raw video audio into timed English dubs without quality loss.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {STAGES.map((stg) => {
          const Icon = stg.icon;
          return (
            <div
              key={stg.num}
              className="group relative p-6 bg-white rounded-2xl border border-slate-300 shadow-md hover:shadow-lg hover:border-indigo-400 transition-all duration-300"
            >
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-mono font-bold text-slate-800 group-hover:text-indigo-700 transition-colors">
                  STAGE {stg.num}
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-200 text-slate-950 font-bold border border-slate-300 group-hover:bg-indigo-100 group-hover:text-indigo-900 transition-colors">
                  {stg.tag}
                </span>
              </div>

              <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-900 group-hover:bg-indigo-100 group-hover:text-indigo-700 group-hover:border-indigo-200 transition-all mb-4">
                <Icon className="w-5 h-5" />
              </div>

              <h4 className="text-lg font-bold text-black mb-2">
                {stg.title}
              </h4>
              <p className="text-sm text-slate-900 font-medium leading-relaxed">
                {stg.desc}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
};
