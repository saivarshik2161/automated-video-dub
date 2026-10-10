import React, { useRef, useState } from 'react';
import { JobResult, TranscriptItem } from '../types';
import { Download, Film, Volume2, CheckCircle2, Play, Search, Users, ShieldCheck, Lock } from 'lucide-react';
import { formatTimestampRange } from '../lib/utils';

interface ResultSectionProps {
  jobResult: JobResult;
  transcript: TranscriptItem[];
}

export const ResultSection: React.FC<ResultSectionProps> = ({
  jobResult,
  transcript,
}) => {
  const originalVideoRef = useRef<HTMLVideoElement>(null);
  const dubbedVideoRef = useRef<HTMLVideoElement>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null);

  const originalVideoUrl = `/api/jobs/${jobResult.job_id}/original`;
  const dubbedVideoUrl = `/api/jobs/${jobResult.job_id}/video`;
  const downloadUrl = `/api/jobs/${jobResult.job_id}/download`;

  const speakers = jobResult.speakers || [];

  const handleSeek = (startSeconds: number, index: number) => {
    setActiveSegmentIndex(index);
    if (dubbedVideoRef.current) {
      dubbedVideoRef.current.currentTime = startSeconds;
      dubbedVideoRef.current.play().catch(() => {});
    }
    if (originalVideoRef.current) {
      originalVideoRef.current.currentTime = startSeconds;
      originalVideoRef.current.play().catch(() => {});
    }
  };

  const filteredTranscript = transcript.filter((item) => {
    const q = searchTerm.toLowerCase();
    return (
      item.original.toLowerCase().includes(q) ||
      item.english.toLowerCase().includes(q) ||
      item.speaker.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-8">
      {/* Completion Header Banner */}
      <div className="p-6 bg-emerald-50/80 border border-emerald-200/80 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500 text-white flex items-center justify-center flex-shrink-0">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-emerald-950">Dubbing Complete</h3>
            <p className="text-xs text-emerald-700">
              Total processing time: <span className="font-mono font-semibold">{jobResult.total_processing_formatted}</span> • Source: {jobResult.source_language.toUpperCase()}
            </p>
          </div>
        </div>

        <a
          href={downloadUrl}
          download={`dubbed_${jobResult.job_id}.mp4`}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-sm font-medium shadow-sm transition-all cursor-pointer flex-shrink-0"
        >
          <Download className="w-4 h-4" />
          <span>Download Dubbed MP4</span>
        </a>
      </div>

      {/* Dual Video Players: Side-by-side on desktop, stacked on mobile */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Original Video Player */}
        <div className="bg-white rounded-2xl border border-slate-300 overflow-hidden shadow-md">
          <div className="px-4 py-3 bg-slate-100 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Film className="w-4 h-4 text-slate-800" />
              <span className="text-xs font-bold text-black">Original Video ({jobResult.source_language.toUpperCase()})</span>
            </div>
            <span className="text-[11px] font-mono text-slate-900 font-bold">{jobResult.duration_formatted}</span>
          </div>
          <div className="relative aspect-video bg-black flex items-center justify-center">
            <video
              key={`orig-${jobResult.job_id}`}
              ref={originalVideoRef}
              controls
              playsInline
              preload="auto"
              className="w-full h-full object-contain"
            >
              <source src={originalVideoUrl} type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          </div>
        </div>

        {/* Dubbed Video Player */}
        <div className="bg-white rounded-2xl border border-indigo-300 overflow-hidden shadow-md">
          <div className="px-4 py-3 bg-indigo-50 border-b border-indigo-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-indigo-700" />
              <span className="text-xs font-bold text-black">English Dubbed Video (AI Voice)</span>
            </div>
            <span className="text-[11px] font-mono text-indigo-900 font-bold bg-indigo-100 px-2 py-0.5 rounded">Edge-TTS</span>
          </div>
          <div className="relative aspect-video bg-black flex items-center justify-center">
            <video
              key={`dubbed-${jobResult.job_id}`}
              ref={dubbedVideoRef}
              controls
              playsInline
              preload="auto"
              className="w-full h-full object-contain"
            >
              <source src={dubbedVideoUrl} type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          </div>
        </div>
      </div>

      {/* Persistent Speaker Identification & Voice Mapping Table */}
      {speakers.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-300 overflow-hidden shadow-md">
          <div className="p-4 sm:p-5 border-b border-slate-200 bg-slate-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center">
                <Users className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-950">Speaker Identification & Voice Locking</h4>
                <p className="text-xs text-slate-700 font-medium">
                  {speakers.length} distinct speaker{speakers.length > 1 ? 's' : ''} detected with gender-matched locked voices across the entire video
                </p>
              </div>
            </div>
            {jobResult.validation && (
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100 border border-emerald-300 text-emerald-800 text-xs font-semibold">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Pre-Export QA: {jobResult.validation.status}</span>
              </div>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-100 text-slate-950 font-mono font-bold border-b border-slate-300">
                <tr>
                  <th className="py-2.5 px-4 w-32">Speaker ID</th>
                  <th className="py-2.5 px-4 w-28">Detected Gender</th>
                  <th className="py-2.5 px-4">Assigned English Voice</th>
                  <th className="py-2.5 px-4 w-32">Dialogue Count</th>
                  <th className="py-2.5 px-4 w-32">Voice Lock</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {speakers.map((sp) => (
                  <tr key={sp.speaker_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-bold text-slate-950 font-mono">{sp.speaker_id}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold ${
                        sp.gender === 'Female' ? 'bg-pink-100 text-pink-800 border border-pink-200' : 'bg-blue-100 text-blue-800 border border-blue-200'
                      }`}>
                        {sp.gender}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-indigo-900">{sp.voice_id}</td>
                    <td className="py-3 px-4 font-mono text-slate-700">{sp.segment_count} segments</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        <Lock className="w-3 h-3 text-emerald-600" />
                        Persistent Lock
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Transcript View Section */}
      <div className="bg-white rounded-2xl border border-slate-300 overflow-hidden shadow-md">
        <div className="p-4 sm:p-5 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h4 className="text-base font-bold text-slate-950">Synchronized Transcript</h4>
            <p className="text-xs text-slate-700 font-medium">
              Click any dialogue segment to seek the player to that timestamp
            </p>
          </div>

          {/* Transcript Filter Search */}
          <div className="relative max-w-xs w-full">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search transcript..."
              className="w-full pl-8 pr-3 py-1.5 text-xs text-black font-medium bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
            />
          </div>
        </div>

        {/* Transcript Rows */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100 text-slate-950 font-mono font-bold border-b border-slate-300">
              <tr>
                <th className="py-3 px-4 w-28 text-slate-950">Timestamp</th>
                <th className="py-3 px-4 w-36 text-slate-950">Speaker & Voice</th>
                <th className="py-3 px-4 w-1/2 text-slate-950">Original ({jobResult.source_language.toUpperCase()})</th>
                <th className="py-3 px-4 w-1/2 text-black">English Dub</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {filteredTranscript.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-slate-600 font-medium italic">
                    No transcript segments found matching your search.
                  </td>
                </tr>
              ) : (
                filteredTranscript.map((seg) => {
                  const isActive = activeSegmentIndex === seg.index;
                  return (
                    <tr
                      key={seg.index}
                      onClick={() => handleSeek(seg.start, seg.index)}
                      className={`hover:bg-indigo-50/80 cursor-pointer transition-colors ${
                        isActive ? 'bg-indigo-100/70 font-semibold' : ''
                      }`}
                    >
                      <td className="py-3.5 px-4 font-mono whitespace-nowrap">
                        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-indigo-100 text-[11px] font-bold text-indigo-900 border border-indigo-200">
                          <Play className="w-2.5 h-2.5 fill-indigo-700 text-indigo-700" />
                          <span>{formatTimestampRange(seg.start, seg.end)}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="font-bold text-slate-950 font-mono text-xs">{seg.speaker}</div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {seg.gender && (
                            <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              seg.gender === 'Female' ? 'bg-pink-100 text-pink-700 border border-pink-200' : 'bg-blue-100 text-blue-700 border border-blue-200'
                            }`}>
                              {seg.gender}
                            </span>
                          )}
                          {seg.voice && (
                            <span className="text-[10px] font-mono text-slate-500 truncate max-w-[110px]" title={seg.voice}>
                              {seg.voice.replace('Neural', '').replace('en-US-', '').replace('en-GB-', '')}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-900 font-medium leading-relaxed">
                        {seg.original}
                      </td>
                      <td className="py-3.5 px-4 text-black font-semibold text-[13px] leading-relaxed">
                        {seg.english}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
