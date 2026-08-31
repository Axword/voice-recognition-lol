// Klient REST panelu. Sesje (token, port) wstrzykuje serwer przez
// window.__LOLVOICE__, patrz server/api.py i docs/CONTRACTS.md.

import type {
  Engine,
  LogsResponse,
  MappingsResponse,
  AudioDevice,
  Settings,
  Status,
  UpdateInfo,
} from './types';

interface Session {
  token: string;
  port: number;
  version: string;
  apiBase: string;
}

declare global {
  interface Window {
    __LOLVOICE__?: Partial<Session>;
  }
}

const session: Session = {
  token: '',
  port: 21337,
  version: '',
  apiBase: '/api/v1',
};

/** Wczytuje sesje wstrzyknieta do HTML. Wolane raz, przy starcie panelu. */
export function bootToken(): void {
  const boot = window.__LOLVOICE__;
  if (!boot) return;
  if (typeof boot.token === 'string') session.token = boot.token;
  if (typeof boot.port === 'number') session.port = boot.port;
  if (typeof boot.version === 'string') session.version = boot.version;
  if (typeof boot.apiBase === 'string') session.apiBase = boot.apiBase;
}

export function sessionToken(): string {
  return session.token;
}

export function wsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const suffix = session.token ? `?token=${encodeURIComponent(session.token)}` : '';
  return `${proto}://${location.host}/ws/status${suffix}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${session.apiBase}${path}`, {
    ...init,
    headers: {
      'X-Auth-Token': session.token,
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) });

export const api = {
  status: () => get<Status>('/status'),
  startListening: () => post<{ listening: boolean }>('/listening/start'),
  stopListening: () => post<{ listening: boolean }>('/listening/stop'),

  settings: () => get<Settings>('/settings'),
  putSettings: (patch: Partial<Settings>) => put<Settings>('/settings', patch),

  engines: () => get<{ engines: Engine[] }>('/engines'),
  downloadEngine: (id: string) => post<{ started: boolean }>(`/engines/${encodeURIComponent(id)}/download`),
  cancelEngine: (id: string) => post<{ cancelled: boolean }>(`/engines/${encodeURIComponent(id)}/cancel`),
  activateEngine: (id: string) => post<{ engine_id: string }>(`/engines/${encodeURIComponent(id)}/activate`),

  audioDevices: () => get<{ devices: AudioDevice[] }>('/audio/devices'),
  testAudio: (seconds = 3) => post<{ level: number; transcript: string }>('/audio/test', { seconds }),

  mappings: () => get<MappingsResponse>('/champions/current/mappings'),

  logs: (limit = 200) => get<LogsResponse>(`/logs?limit=${limit}`),

  checkUpdate: (force = true) => get<UpdateInfo>(`/update/check?force=${force}`),
  installUpdate: () => post<{ started: boolean; reason?: string }>('/update/install'),

  quit: () => post<{ ok: boolean }>('/app/quit'),
};

/** Pobiera ZIP z logami i zapisuje go przez przegladarke. */
export async function downloadLogs(): Promise<void> {
  const response = await fetch(`${session.apiBase}/logs/download`, {
    headers: { 'X-Auth-Token': session.token },
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);

  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = /filename="([^"]+)"/.exec(disposition);
  const name = match?.[1] ?? 'lolvoice-logs.zip';

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
