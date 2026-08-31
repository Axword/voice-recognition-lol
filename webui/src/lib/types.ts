// Ksztalty odpowiedzi API. Zrodlo prawdy: docs/CONTRACTS.md.

export type RecognitionMode = 'letters' | 'spells';
export type Sensitivity = 'low' | 'medium' | 'high';
export type Theme = 'dark' | 'light' | 'system';
export type UiLanguage = 'pl_PL' | 'en_US';

export interface Settings {
  recognition_mode: RecognitionMode;
  spell_sensitivity: Sensitivity;
  language: string;
  merge_command_languages: boolean;
  ui_language: UiLanguage;
  flash_key: string;
  summoner2_key: string;
  engine_id: string;
  audio_device: string | null;
  start_with_windows: boolean;
  start_listening_on_launch: boolean;
  theme: Theme;
  skipped_version: string | null;
  check_updates: boolean;
}

export interface Status {
  listening: boolean;
  game_active: boolean;
  champion: string | null;
  mode: string;
  engine_id: string;
  engine_name: string | null;
  version: string;
  mappings_count: number;
  last_command: string | null;
  last_heard: string | null;
  update_available: boolean;
  error?: string | null;
}

export interface AudioDevice {
  id: string;
  name: string;
  default: boolean;
}

export interface Engine {
  id: string;
  name: string;
  backend: string;
  speed: string;
  quality: string;
  size_bytes: number;
  installed: boolean;
  active: boolean;
  requires_cuda: boolean;
  bundled?: boolean;
  description?: string | Record<string, string>;
}

export interface Mapping {
  phrase: string;
  key: string;
  source: string;
}

export interface MappingsResponse {
  champion: string | null;
  mode: string;
  mappings: Mapping[];
}

export interface LogLine {
  time?: number;
  level?: string;
  message: string;
}

export interface LogsResponse {
  files: { name: string; size: number; modified: number }[];
  tail: (LogLine | string)[];
}

export interface UpdateInfo {
  current: string | null;
  latest: string | null;
  available: boolean;
  url?: string | null;
  notes?: string | null;
}

export interface HeardItem {
  at: number;
  phrase: string;
  key: string | null;
}

export interface DownloadState {
  percent?: number;
  received?: number;
  total?: number;
  done?: boolean;
  cancelled?: boolean;
  error?: string;
}
