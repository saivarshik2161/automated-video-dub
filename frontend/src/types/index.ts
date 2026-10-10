export interface JobOptions {
  multi_speaker: boolean;
  keep_background_music: boolean;
  voice_cloning: boolean;
  whisper_model: string;
  tts_voice: string;
}

export interface SpeakerProfile {
  speaker_id: string;
  gender: string;
  voice_id: string;
  segment_count: number;
  locked: boolean;
}

export type PipelineStage = 
  | 'download' 
  | 'transcribe' 
  | 'diarize'
  | 'translate' 
  | 'synthesize' 
  | 'align' 
  | 'mix_audio'
  | 'validate'
  | 'remix';

export interface ProgressEventData {
  job_id: string;
  stage: PipelineStage;
  stage_percent: number;
  overall_percent: number;
  message: string;
  elapsed: number;
  details?: Record<string, any>;
}

export interface TranscriptItem {
  index: number;
  start: number;
  end: number;
  speaker: string;
  gender?: string;
  voice?: string;
  original: string;
  english: string;
}

export interface TranscriptResponse {
  job_id: string;
  source_language: string;
  target_language: string;
  total_segments: number;
  speakers?: SpeakerProfile[];
  segments: TranscriptItem[];
}

export interface JobResult {
  job_id: string;
  url: string;
  title: string;
  duration_seconds: number;
  duration_formatted: string;
  source_language: string;
  whisper_model: string;
  translation_model: string;
  tts_voice: string;
  speakers?: SpeakerProfile[];
  validation?: {
    is_valid: boolean;
    status: string;
    passed_count: number;
    issue_count: number;
    checks_passed: string[];
    issues: string[];
  };
  total_processing_time: number;
  total_processing_formatted: string;
  artifacts: {
    source_video: string;
    audio: string;
    transcription: string;
    translation: string;
    tts_dir: string;
    aligned_audio: string;
    master_audio?: string;
    validation_report?: string;
    final_dubbed: string;
    published_output?: string;
  };
  transcript_count: number;
  status: 'completed' | 'failed';
}

export interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  current_stage: string;
  stage_percent?: number;
  overall_percent: number;
  message: string;
  error?: string | null;
  result?: JobResult | null;
}
