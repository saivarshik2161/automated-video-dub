import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="py-12 border-t border-slate-200 text-center text-xs text-slate-800 relative z-10 bg-white/70 backdrop-blur-sm">
      <div className="max-w-5xl mx-auto px-4 space-y-2">
        <p className="font-bold text-black text-sm">
          AutoDub AI — Smart Multilingual Video Dubbing
        </p>
        <p className="font-mono text-slate-700 font-semibold">
          Multilingual speech &rarr; English dubbing
        </p>
        <p className="text-[11px] text-slate-600 font-medium pt-2">
          Powered by Whisper • IndicTrans2 • Edge-TTS • FFmpeg
        </p>
      </div>
    </footer>
  );
};
