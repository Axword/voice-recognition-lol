// Globalny stan panelu na sygnalach Preact plus polaczenie WebSocket.

import { computed, effect, signal } from '@preact/signals';
import { api, wsUrl } from './api';
import type { DownloadState, HeardItem, LogLine, Settings, Status } from './types';

export type ViewId = 'dashboard' | 'settings' | 'engines' | 'commands' | 'logs' | 'about';
export type Connection = 'connecting' | 'online' | 'offline';
export type SaveState = 'idle' | 'saving' | 'saved' | 'error';

const HEARD_LIMIT = 50;
const LOG_LIMIT = 500;

export const view = signal<ViewId>('dashboard');
export const connection = signal<Connection>('connecting');
export const status = signal<Status | null>(null);
export const settings = signal<Settings | null>(null);
export const heard = signal<HeardItem[]>([]);
export const logLines = signal<LogLine[]>([]);
export const downloads = signal<Record<string, DownloadState>>({});
export const enginesDirty = signal(0);
export const saveState = signal<SaveState>('idle');

// --- motyw -------------------------------------------------------------

const systemDark =
  typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;
const systemPrefersDark = signal(systemDark?.matches ?? true);
systemDark?.addEventListener('change', (e) => (systemPrefersDark.value = e.matches));

export const theme = computed<'dark' | 'light'>(() => {
  const chosen = settings.value?.theme ?? 'dark';
  if (chosen === 'system') return systemPrefersDark.value ? 'dark' : 'light';
  return chosen;
});

effect(() => {
  document.documentElement.dataset.theme = theme.value;
});

// --- ustawienia -------------------------------------------------------------

let saveTimer: ReturnType<typeof setTimeout> | undefined;

export async function patchSettings(patch: Partial<Settings>): Promise<void> {
  const before = settings.value;
  if (before) settings.value = { ...before, ...patch };
  saveState.value = 'saving';
  clearTimeout(saveTimer);
  try {
    settings.value = await api.putSettings(patch);
    saveState.value = 'saved';
    saveTimer = setTimeout(() => (saveState.value = 'idle'), 1600);
  } catch {
    if (before) settings.value = before;
    saveState.value = 'error';
    saveTimer = setTimeout(() => (saveState.value = 'idle'), 4000);
  }
}

export async function refreshAll(): Promise<void> {
  try {
    const [st, cfg] = await Promise.all([api.status(), api.settings()]);
    status.value = st;
    settings.value = cfg;
    if (connection.value === 'offline') connection.value = 'connecting';
  } catch {
    connection.value = 'offline';
  }
}

// --- ramki WebSocket ---------------------------------------------------------

function onFrame(frame: Record<string, unknown>): void {
  switch (frame.type) {
    case 'status': {
      const { type: _type, time: _time, ...rest } = frame;
      status.value = rest as unknown as Status;
      break;
    }
    case 'heard': {
      const at = typeof frame.time === 'number' ? frame.time * 1000 : Date.now();
      // matched to pojedynczy klawisz albo lista klawiszy przy lancuchu komend.
      const matched = frame.matched;
      const keys = Array.isArray(matched)
        ? matched.filter((entry): entry is string => typeof entry === 'string' && entry.length > 0)
        : typeof matched === 'string' && matched
          ? [matched]
          : [];
      const item: HeardItem = { at, phrase: String(frame.text ?? ''), keys };
      heard.value = [item, ...heard.value].slice(0, HEARD_LIMIT);
      break;
    }
    case 'download': {
      const id = String(frame.engine_id ?? '');
      if (!id) break;
      const prev = downloads.value[id] ?? {};
      const next: DownloadState = { ...prev };
      if (typeof frame.percent === 'number') next.percent = frame.percent / 100;
      if (typeof frame.downloaded === 'number') next.received = frame.downloaded;
      if (typeof frame.total === 'number') next.total = frame.total;
      if (frame.done === true) next.done = true;
      if (frame.cancelled === true) next.cancelled = true;
      if (typeof frame.error === 'string') next.error = frame.error;
      downloads.value = { ...downloads.value, [id]: next };
      if (next.done || next.cancelled || next.error) enginesDirty.value += 1;
      break;
    }
    case 'log': {
      const line: LogLine = {
        time: typeof frame.time === 'number' ? frame.time : undefined,
        level: typeof frame.level === 'string' ? frame.level : 'info',
        message: String(frame.message ?? ''),
      };
      const next = [...logLines.value, line];
      logLines.value = next.length > LOG_LIMIT ? next.slice(next.length - LOG_LIMIT) : next;
      break;
    }
    case 'update': {
      const st = status.value;
      if (st && typeof frame.available === 'boolean') {
        status.value = { ...st, update_available: frame.available };
      }
      break;
    }
    default:
      break;
  }
}

// --- polaczenie --------------------------------------------------------------

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
let backoffMs = 1000;

function scheduleReconnect(): void {
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    backoffMs = Math.min(backoffMs * 2, 15000);
    connect();
  }, backoffMs);
}

export function connect(): void {
  clearTimeout(reconnectTimer);
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  if (connection.value !== 'online') connection.value = 'connecting';

  let ws: WebSocket;
  try {
    ws = new WebSocket(wsUrl());
  } catch {
    connection.value = 'offline';
    scheduleReconnect();
    return;
  }
  socket = ws;

  ws.onopen = () => {
    backoffMs = 1000;
    connection.value = 'online';
    void refreshAll();
  };
  ws.onmessage = (event) => {
    try {
      const frame = JSON.parse(String(event.data)) as Record<string, unknown>;
      if (frame && typeof frame === 'object') onFrame(frame);
    } catch {
      /* nie-JSON ignorujemy */
    }
  };
  ws.onclose = () => {
    if (socket === ws) socket = null;
    connection.value = 'offline';
    scheduleReconnect();
  };
  ws.onerror = () => {
    ws.close();
  };
}

export function retryNow(): void {
  clearTimeout(reconnectTimer);
  backoffMs = 1000;
  if (socket) {
    try {
      socket.close();
    } catch {
      /* i tak otwieramy nowe */
    }
    socket = null;
  }
  connect();
  void refreshAll();
}
