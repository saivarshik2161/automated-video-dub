import React, { useEffect, useRef } from 'react';
import { Terminal, Copy, Check } from 'lucide-react';

interface LogEntry {
  timestamp: string;
  message: string;
  stage?: string;
}

interface LogConsoleProps {
  logs: LogEntry[];
}

export const LogConsole: React.FC<LogConsoleProps> = ({ logs }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = React.useState(false);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const handleCopyLogs = () => {
    const text = logs.map((l) => `[${l.timestamp}] ${l.message}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white/90 backdrop-blur-md rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden mb-8">
      {/* Top Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-100/90 border-b border-slate-200">
        <div className="flex items-center gap-2 text-xs font-mono font-bold text-black">
          <Terminal className="w-3.5 h-3.5 text-slate-800" />
          <span>Execution Log Console</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        </div>

        <button
          type="button"
          onClick={handleCopyLogs}
          className="inline-flex items-center gap-1 text-[11px] font-mono text-slate-800 hover:text-black font-semibold transition-colors cursor-pointer"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-700" />
              <span className="text-emerald-700 font-bold">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3 text-slate-700" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Terminal Content Body */}
      <div
        ref={scrollRef}
        className="p-4 font-mono text-xs text-black bg-slate-50/90 max-h-64 overflow-y-auto space-y-1.5 select-text border-t border-slate-200"
      >
        {logs.length === 0 ? (
          <div className="text-slate-700 italic font-medium py-2">
            No pipeline events received yet. Enter a YouTube URL and click "Dub it" to begin.
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="flex items-start gap-2 leading-relaxed">
              <span className="text-slate-700 font-bold flex-shrink-0 select-none">
                [{log.timestamp}]
              </span>
              <span className="text-black font-semibold break-all">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
