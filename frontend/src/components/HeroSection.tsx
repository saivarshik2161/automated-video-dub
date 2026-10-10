import React, { useState } from 'react';
import { Sparkles, ArrowRight, Play, AlertCircle, Loader2 } from 'lucide-react';

interface HeroSectionProps {
  onStartDubbing: (url: string) => Promise<void>;
  isSubmitting: boolean;
  error: string | null;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onStartDubbing,
  isSubmitting,
  error,
}) => {
  const [url, setUrl] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanUrl = url.trim();

    if (!cleanUrl) {
      setLocalError('Please enter a YouTube video URL.');
      return;
    }

    if (!cleanUrl.includes('youtube.com') && !cleanUrl.includes('youtu.be')) {
      setLocalError('Please enter a valid YouTube link (e.g., https://www.youtube.com/watch?v=...).');
      return;
    }

    setLocalError(null);
    await onStartDubbing(cleanUrl);
  };

  const handleSampleClick = (sampleUrl: string) => {
    setUrl(sampleUrl);
    setLocalError(null);
  };

  return (
    <section className="relative pt-28 pb-20 md:pt-36 md:pb-28 px-4 sm:px-6 max-w-5xl mx-auto text-center z-10">
      {/* Top Badge */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-100 border border-indigo-300 text-indigo-950 text-xs sm:text-sm font-semibold mb-8 backdrop-blur-sm shadow-sm transition-all hover:border-indigo-400">
        <Sparkles className="w-3.5 h-3.5 text-indigo-700 animate-pulse" />
        <span>End-to-End Multilingual Speech to English Dubbing</span>
      </div>

      {/* Main Heading */}
      <h1 className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-slate-950 leading-[1.1] mb-6">
        AutoDub AI, <br className="hidden sm:inline" />
        <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-700 to-indigo-900">
          Smart Multilingual Dubbing.
        </span>
      </h1>

      {/* Subtitle */}
      <p className="text-lg sm:text-xl text-slate-900 max-w-2xl mx-auto font-medium leading-relaxed mb-10">
        Turn videos in other languages into naturally timed English-dubbed videos.
        Whisper speech recognition, IndicTrans2 neural translation, and Edge-TTS synthesis.
      </p>

      {/* URL Input Form */}
      <div className="max-w-2xl mx-auto">
        <form
          onSubmit={handleSubmit}
          className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 p-2 bg-white rounded-2xl border-2 border-slate-300 shadow-xl shadow-slate-200/50 hover:border-slate-400 transition-all"
        >
          <div className="flex-1 relative flex items-center pl-3">
            <span className="text-slate-900 text-sm font-bold mr-2 hidden sm:inline">URL:</span>
            <input
              type="text"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (localError) setLocalError(null);
              }}
              placeholder="Paste YouTube URL (e.g. https://www.youtube.com/watch?v=...)"
              className="w-full py-2.5 sm:py-3 pr-4 text-black font-semibold placeholder:text-slate-500 bg-transparent text-sm sm:text-base focus:outline-none"
              disabled={isSubmitting}
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-bold text-sm sm:text-base shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-70 disabled:cursor-not-allowed cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <span>Dub it</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Validation or API Error Banner */}
        {(localError || error) && (
          <div className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-50 text-red-800 text-xs sm:text-sm font-semibold border border-red-200 text-left">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{localError || error}</span>
          </div>
        )}

        {/* Quick Sample Link */}
        <div className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-800 font-medium">
          <span>Try sample Hindi clip:</span>
          <button
            type="button"
            onClick={() => handleSampleClick('https://www.youtube.com/watch?v=iVo3LfZti5w')}
            className="inline-flex items-center gap-1 font-bold text-indigo-700 hover:text-indigo-900 hover:underline cursor-pointer"
          >
            <Play className="w-3 h-3 fill-indigo-700 text-indigo-700" />
            <span>1-min Motivational Speech</span>
          </button>
        </div>
      </div>
    </section>
  );
};
