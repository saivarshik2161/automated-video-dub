import React, { useState, useRef, useEffect } from 'react';
import { JobOptions, PipelineStage, TranscriptItem, JobResult } from './types';
import { ParticleBackground } from './components/ParticleBackground';
import { HeroSection } from './components/HeroSection';
import { HowItWorksSection } from './components/HowItWorksSection';
import { OptionsPanel } from './components/OptionsPanel';
import { LiveProgress } from './components/LiveProgress';
import { LogConsole } from './components/LogConsole';
import { ResultSection } from './components/ResultSection';
import { ArchitectureSection } from './components/ArchitectureSection';
import { Footer } from './components/Footer';

export const App: React.FC = () => {
  const [jobId, setJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pipeline Options
  const [options, setOptions] = useState<JobOptions>({
    multi_speaker: true,
    keep_background_music: true,
    voice_cloning: false,
    whisper_model: 'small',
    tts_voice: 'en-US-ChristopherNeural',
  });

  // Live Progress & SSE State
  const [currentStage, setCurrentStage] = useState<PipelineStage | string>('download');
  const [stagePercent, setStagePercent] = useState<number>(0);
  const [overallPercent, setOverallPercent] = useState<number>(0);
  const [currentMessage, setCurrentMessage] = useState<string>('');
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set());
  const [logs, setLogs] = useState<{ timestamp: string; message: string; stage?: string }[]>([]);

  // Results State
  const [jobResult, setJobResult] = useState<JobResult | null>(null);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);

  const appSectionRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const addLog = (message: string, stage?: string) => {
    const timeStr = new Date().toTimeString().split(' ')[0];
    setLogs((prev) => [...prev, { timestamp: timeStr, message, stage }]);
  };

  const fetchTranscript = async (id: string) => {
    try {
      const res = await fetch(`/api/jobs/${id}/transcript`);
      if (res.ok) {
        const data = await res.json();
        setTranscript(data.segments || []);
      }
    } catch (err) {
      console.error('Failed to load transcript:', err);
    }
  };

  const checkJobStatus = async (id: string) => {
    try {
      const res = await fetch(`/api/jobs/${id}`);
      if (!res.ok) return;
      const data = await res.json();

      // Sync backend logs if available
      if (Array.isArray(data.logs) && data.logs.length > 0) {
        setLogs(data.logs);
      }

      if (data.status === 'processing') {
        if (data.current_stage) setCurrentStage(data.current_stage);
        if (typeof data.overall_percent === 'number' && data.overall_percent > 0) {
          setOverallPercent(data.overall_percent);
        }
        if (typeof data.stage_percent === 'number') {
          setStagePercent(data.stage_percent);
        }
        if (data.message) setCurrentMessage(data.message);
      } else if (data.status === 'completed') {
        setOverallPercent(100);
        setStagePercent(100);
        setCurrentMessage('Dubbing completed successfully!');
        setCompletedStages(
          new Set(['download', 'transcribe', 'translate', 'synthesize', 'align', 'remix'])
        );
        if (data.result) setJobResult(data.result);
        stopPolling();
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
        }
        await fetchTranscript(id);
      } else if (data.status === 'failed') {
        setError(data.error || 'Pipeline execution failed');
        stopPolling();
      }
    } catch (err) {
      // Ignore transient network errors during poll
    }
  };

  const startJob = async (targetUrl: string) => {
    setIsSubmitting(true);
    setError(null);
    setJobResult(null);
    setTranscript([]);
    setCurrentStage('download');
    setStagePercent(0);
    setOverallPercent(5);
    setCurrentMessage('Stage 1/6: Connecting to YouTube and extracting stream...');
    setCompletedStages(new Set());
    setJobId('active_job'); // Render LiveProgress & LogConsole immediately!
    const nowStr = new Date().toTimeString().split(' ')[0];
    setLogs([
      { timestamp: nowStr, stage: 'download', message: `Submitting video: ${targetUrl}` },
      { timestamp: nowStr, stage: 'download', message: `[STAGE 1: DOWNLOAD] Connecting to YouTube and extracting video stream...` }
    ]);
    stopPolling();

    // Smooth scroll to application section immediately so user sees the progress right away
    setTimeout(() => {
      appSectionRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 50);

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: targetUrl, options }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to submit dubbing job');
      }

      const { job_id } = await res.json();
      setJobId(job_id);
      addLog(`Job active with ID: ${job_id}`);

      // Immediately poll status in case already cached/completed
      await checkJobStatus(job_id);

      // Connect to SSE stream
      connectSSE(job_id);

      // Start fallback polling interval every 1.5 seconds
      pollTimerRef.current = window.setInterval(() => {
        checkJobStatus(job_id);
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
      addLog(`Error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const connectSSE = (id: string) => {
    const es = new EventSource(`/api/jobs/${id}/events`);
    eventSourceRef.current = es;

    es.addEventListener('status', (e) => {
      const data = JSON.parse(e.data);
      if (data.status === 'processing') {
        addLog(`Pipeline started execution...`);
      }
    });

    es.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data);
      setCurrentStage(data.stage);
      setStagePercent(data.stage_percent);
      setOverallPercent(data.overall_percent);
      setCurrentMessage(data.message);
      setElapsedSeconds(data.elapsed);

      if (data.stage_percent >= 100) {
        setCompletedStages((prev) => new Set([...prev, data.stage]));
      }

      addLog(data.message, data.stage);
    });

    es.addEventListener('complete', async (e) => {
      const resultData = JSON.parse(e.data);
      setOverallPercent(100);
      setStagePercent(100);
      setCurrentMessage('Dubbing completed successfully!');
      setJobResult(resultData);
      setCompletedStages(
        new Set(['download', 'transcribe', 'translate', 'synthesize', 'align', 'remix'])
      );
      addLog('Dubbing complete! Video and transcript are ready.');
      stopPolling();
      es.close();

      // Fetch transcript segments
      await fetchTranscript(id);
    });

    es.addEventListener('error', (e: any) => {
      try {
        const errData = JSON.parse(e.data);
        if (errData && errData.error) {
          setError(errData.error || 'Pipeline execution failed');
          addLog(`Pipeline Error: ${errData.error}`);
        }
      } catch {
        // SSE disconnected or closed, fallback poller continues
      }
    });
  };

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      stopPolling();
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col font-sans selection:bg-indigo-500 selection:text-white relative">
      {/* Three.js Particle Background (Sticky canvas behind content) */}
      <ParticleBackground />

      {/* Main Content wrapper */}
      <main className="flex-1 relative z-10">
        {/* Hero Section */}
        <HeroSection
          onStartDubbing={startJob}
          isSubmitting={isSubmitting}
          error={error}
        />

        {/* How It Works Section */}
        <HowItWorksSection />

        {/* The Application Section */}
        <section
          ref={appSectionRef}
          id="app-section"
          className="py-16 px-4 sm:px-6 max-w-5xl mx-auto scroll-mt-10"
        >
          <div className="text-center max-w-xl mx-auto mb-10">
            <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-700 mb-2">
              Workbench
            </h2>
            <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-black">
              Interactive Dubbing Studio
            </h3>
            <p className="mt-2 text-slate-800 text-sm font-medium">
              Adjust configuration, track real-time synthesis events, and review results.
            </p>
          </div>

          {/* Live Progress Section (Shown once a job has been initiated) */}
          {jobId && (
            <>
              <LiveProgress
                currentStage={currentStage}
                stagePercent={stagePercent}
                overallPercent={overallPercent}
                currentMessage={currentMessage}
                elapsedSeconds={elapsedSeconds}
                completedStages={completedStages}
              />

              <LogConsole logs={logs} />
            </>
          )}

          {/* Completed State & Result Players */}
          {jobResult && (
            <ResultSection
              jobResult={jobResult}
              transcript={transcript}
            />
          )}

          {/* Options Panel */}
          <OptionsPanel
            options={options}
            onChange={setOptions}
            disabled={isSubmitting || (jobId !== null && overallPercent < 100 && !error)}
          />
        </section>

        {/* Architecture Section */}
        <ArchitectureSection />
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};

export default App;
