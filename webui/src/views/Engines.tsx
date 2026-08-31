import { useEffect, useState } from 'preact/hooks';
import { api } from '../lib/api';
import { downloads, enginesDirty, settings, status } from '../lib/state';
import { t } from '../i18n';
import { bytes, pct } from '../lib/format';
import { Icon } from '../components/Icon';
import { Button, Card, Empty, PageHead } from '../components/ui';
import type { Engine } from '../lib/types';

function describe(engine: Engine, uiLang: string): string {
  const d = engine.description;
  if (!d) return '';
  if (typeof d === 'string') return d;
  return d[uiLang] ?? d.en_US ?? Object.values(d)[0] ?? '';
}

export function Engines() {
  const s = t.value;
  const uiLang = settings.value?.ui_language ?? 'pl_PL';
  const activeId = status.value?.engine_id ?? settings.value?.engine_id;
  const dirty = enginesDirty.value;
  const [list, setList] = useState<Engine[] | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  async function load() {
    try {
      setList((await api.engines()).engines);
    } catch {
      setList([]);
    }
  }

  useEffect(() => {
    void load();
  }, [dirty]);

  const speedLabel: Record<string, string> = {
    fast: s.speed_fast,
    balanced: s.speed_balanced,
    slow: s.speed_slow,
  };
  const qualityLabel: Record<string, string> = {
    basic: s.quality_basic,
    good: s.quality_good,
    best: s.quality_best,
  };

  async function activate(id: string) {
    setPendingId(id);
    try {
      await api.activateEngine(id);
      if (settings.value) settings.value = { ...settings.value, engine_id: id };
      if (status.value) status.value = { ...status.value, engine_id: id };
      await load();
    } catch {
      /* pozostajemy przy poprzednim silniku */
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div class="page">
      <PageHead
        title={s.nav_engines}
        lead={s.engines_lead}
        actions={
          <Button variant="quiet" size="sm" onClick={() => void load()}>
            <Icon name="refresh" size={14} />
            {s.refresh}
          </Button>
        }
      />

      <p class="muted" style="margin:0;font-size:var(--step-s)">{s.engines_note}</p>

      {list === null ? (
        <Card flush>
          <Empty>{s.loading}</Empty>
        </Card>
      ) : list.length === 0 ? (
        <Card flush>
          <Empty>{s.error_generic}</Empty>
        </Card>
      ) : (
        <div class="engines">
          {list.map((e) => {
            const dl = downloads.value[e.id];
            const busy = Boolean(dl && !dl.done && !dl.cancelled && !dl.error);
            const installed = e.installed || e.bundled || Boolean(dl?.done);
            const active = e.id === activeId;
            const percent = dl ? pct(dl.percent ?? (dl.total ? (dl.received ?? 0) / dl.total : 0)) : 0;

            return (
              <article key={e.id} class={active ? 'engine engine--active' : 'engine'}>
                <div class="engine__top">
                  <div>
                    <h3 class="engine__name">{e.name}</h3>
                    <p class="engine__desc">{describe(e, uiLang)}</p>
                  </div>
                  <div class="engine__actions">
                    {busy ? (
                      <Button variant="danger" size="sm" onClick={() => void api.cancelEngine(e.id)}>
                        <Icon name="x" size={14} />
                        {s.cancel}
                      </Button>
                    ) : !installed ? (
                      <Button size="sm" onClick={() => void api.downloadEngine(e.id)}>
                        <Icon name="download" size={14} />
                        {s.download}
                      </Button>
                    ) : active ? (
                      <span class="badge badge--accent">
                        <Icon name="check" size={12} />
                        {s.engine_active}
                      </span>
                    ) : (
                      <Button
                        size="sm"
                        variant="accent"
                        disabled={pendingId === e.id}
                        onClick={() => void activate(e.id)}
                      >
                        {s.use}
                      </Button>
                    )}
                  </div>
                </div>

                <div class="engine__meta">
                  <span class="badge">{s.engine_langs}</span>
                  <span class="badge">
                    {s.engine_speed}: {speedLabel[e.speed] ?? e.speed}
                  </span>
                  <span class="badge">
                    {s.engine_quality}: {qualityLabel[e.quality] ?? e.quality}
                  </span>
                  {e.size_bytes > 0 && (
                    <span class="badge">
                      {s.engine_size}: {bytes(e.size_bytes)}
                    </span>
                  )}
                  {e.requires_cuda && <span class="badge">{s.engine_cuda}</span>}
                  <span class={installed ? 'badge badge--accent' : 'badge'}>
                    {e.bundled ? s.engine_bundled : installed ? s.engine_installed : s.engine_not_installed}
                  </span>
                  {dl?.error && <span class="badge badge--danger">{s.download_failed}</span>}
                  {dl?.cancelled && <span class="badge">{s.download_cancelled}</span>}
                </div>

                {busy && (
                  <div class="progress">
                    <span class="mono muted">{s.downloading}</span>
                    <span class="progress__track">
                      <span class="progress__fill" style={{ width: `${percent}%` }} />
                    </span>
                    <span class="progress__pct">{percent}%</span>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
