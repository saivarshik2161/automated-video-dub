import React from 'react';
import { Mic, Languages, FastForward, Database } from 'lucide-react';

const ARCH_CARDS = [
  {
    title: 'Whisper',
    badge: 'Multilingual ASR',
    icon: Mic,
    desc: 'Provides robust multilingual speech recognition with automatic language identification. Preserves precise segment boundaries and word-level timestamps essential for subsequent alignment.',
  },
  {
    title: 'IndicTrans2',
    badge: 'Neural Translation',
    icon: Languages,
    desc: 'State-of-the-art open-source translation model developed by AI4Bharat. Translates 22 Indian languages into natural English, preserving semantic nuances and sentence structure across segment boundaries.',
  },
  {
    title: 'Timing Alignment',
    badge: 'Tempo Scaling',
    icon: FastForward,
    desc: 'Calculates the duration delta between original speech and generated Edge-TTS audio. Applies FFmpeg atempo time-stretching within natural thresholds (1.0x - 1.38x) to prevent lip-sync drift.',
  },
  {
    title: 'Caching & Resume',
    badge: 'State Persistence',
    icon: Database,
    desc: 'Every pipeline stage outputs validated artifacts (source.mp4, audio.wav, transcription.json, translation.json, tts/). If a stage is interrupted or re-run, execution resumes from the latest valid stage instantly.',
  },
];

export const ArchitectureSection: React.FC = () => {
  return (
    <section className="py-20 px-4 sm:px-6 max-w-6xl mx-auto z-10 relative">
      <div className="text-center max-w-2xl mx-auto mb-14">
        <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-700 mb-2">
          Technical Highlights
        </h2>
        <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-black">
          Core Engineering Decisions
        </h3>
        <p className="mt-3 text-slate-800 text-sm sm:text-base font-medium">
          Every layer of the dubbing pipeline is optimized for accuracy, lip synchronization, and computational efficiency.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {ARCH_CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.title}
              className="p-6 sm:p-7 bg-white/95 backdrop-blur-md rounded-2xl border border-slate-200 shadow-sm hover:border-indigo-300 hover:shadow-md transition-all duration-300"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-700">
                  <Icon className="w-5 h-5" />
                </div>
                <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-full bg-slate-100 border border-slate-300 text-slate-900">
                  {card.badge}
                </span>
              </div>

              <h4 className="text-lg font-bold text-black mb-2">
                {card.title}
              </h4>
              <p className="text-sm text-slate-800 leading-relaxed font-normal">
                {card.desc}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
};
