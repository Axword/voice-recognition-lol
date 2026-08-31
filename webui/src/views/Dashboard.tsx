import { useEffect, useState } from 'preact/hooks';
import { api } from '../lib/api';
import { heard, patchSettings, settings, status, view } from '../lib/state';
import type { Engine } from '../lib/types';
import { t } from '../i18n';
import { clock } from '../lib/format';
import { Icon } from '../components/Icon';
import { Button, Card, Empty, PageHead } from '../components/ui';

export function Dashboard() {
  const s = t.value;
  const st = status.value;
  const listening = st?.listening ?? false;
  const [busy, setBusy] = useState(false);
  const [installedEngines, setInstalledEngines] = useState<Engine[]>([]);

  useEffect(() => {
    api
      .engines()
      .then((r) => setInstalledEngines(r.engines.filter((e) => e.installed || e.bundled)))
      .catch(() => setInstalledEngines([]));
  }, []);

  const activeEngineId = st?.engine_id ?? settings.value?.engine_id ?? '';

  async function switchEngine(id: string) {
    try {
      await api.activateEngine(id);
      if (settings.value) settings.value = { ...settings.value, engine_id: id };
      if (status.value) {
        const chosen = installedEngines.find((e) => e.id === id);
        status.value = { ...status.value, engine_id: id, engine_name: chosen?.name ?? id };
      }
    } catch {
      /* silnik zostaje bez zmian */
    }
  }

  function toggleMode() {
    const next = st?.mode === 'letters' ? 'spells' : 'letters';
    void patchSettings({ recognition_mode: next });
    if (status.value) status.value = { ...status.value, mode: next };
  }

  async function toggle() {
    setBusy(true);
    try {
      const res = listening ? await api.stopListening() : await api.startListening();
      if (st) status.value = { ...st, listening: res.listening };
    } catch {
      /* stan i tak przyjdzie po WS */
    } finally {
      setBusy(false);
    }
  }

  const items = heard.value;

  return (
    <div class="page">
      <PageHead title={s.nav_dashboard} lead={s.dashboard_lead} />

      {st?.error && (
        <div class="banner banner--danger">
          <Icon name="alert" size={18} />
          <div class="banner__text">
            <div class="banner__title">{s.service_error_title}</div>
            <div class="banner__sub mono">{st.error}</div>
            <div class="banner__sub">{s.service_error_hint}</div>
          </div>
        </div>
      )}

      <div class="hero">
        <div class="hero__main">
          <span class="hero__state">{listening ? s.state_listening : s.state_stopped}</span>
          <p class="hero__hint">{listening ? s.hint_listening : s.hint_stopped}</p>
          <Button
            variant={listening ? 'danger' : 'accent'}
            class="hero__btn"
            onClick={toggle}
            disabled={busy || !st}
          >
            <Icon name={listening ? 'stop' : 'play'} size={18} />
            {listening ? s.stop_listening : s.start_listening}
          </Button>
        </div>

        <div class="hero__side">
          <div class="stat">
            <span class="stat__k">{s.stat_game}</span>
            <span class="stat__v">{st?.game_active ? s.in_game : s.no_game}</span>
          </div>
          <div class="stat">
            <span class="stat__k">{s.stat_champion}</span>
            <span class="stat__v">{st?.champion || s.none}</span>
          </div>
          <div class="stat">
            <span class="stat__k">{s.stat_engine}</span>
            {installedEngines.length > 1 ? (
              <select
                class="select select--compact"
                aria-label={s.stat_engine}
                value={activeEngineId}
                onChange={(e) => void switchEngine((e.currentTarget as HTMLSelectElement).value)}
              >
                {installedEngines.map((e) => (
                  <option key={e.id} value={e.id}>{e.name}</option>
                ))}
              </select>
            ) : (
              <span class="stat__v">{st?.engine_name || st?.engine_id || s.none}</span>
            )}
          </div>
          <button type="button" class="stat" onClick={toggleMode} title={s.recognition_mode} disabled={!st}>
            <span class="stat__k">{s.stat_mode}</span>
            <span class="stat__v">{st?.mode === 'letters' ? s.letters_mode : s.spells_mode}</span>
          </button>
          <button type="button" class="stat" onClick={() => (view.value = 'commands')} title={s.nav_commands}>
            <span class="stat__k">{s.stat_mappings}</span>
            <span class="stat__v">{st?.mappings_count ?? 0}</span>
          </button>
        </div>
      </div>

      <Card
        title={s.feed_title}
        flush
        actions={
          items.length > 0 ? (
            <Button variant="quiet" size="sm" onClick={() => (heard.value = [])}>
              {s.clear}
            </Button>
          ) : undefined
        }
      >
        {items.length === 0 ? (
          <Empty>{s.feed_empty}</Empty>
        ) : (
          <div class="feed">
            {items.map((h, i) => (
              <div class="feed__row" key={`${h.at}-${i}`}>
                <span class="feed__time">{clock(h.at)}</span>
                <span class="feed__phrase">{h.phrase}</span>
                {h.key ? (
                  <span class="key">{h.key}</span>
                ) : (
                  <span class="badge">{s.feed_no_match}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
