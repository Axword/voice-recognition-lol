import { useEffect, useMemo, useState } from 'preact/hooks';
import { api } from '../lib/api';
import { patchSettings, settings, status } from '../lib/state';
import { languageOptions } from '../lib/languages';
import { t } from '../i18n';
import { Icon } from '../components/Icon';
import { Button, Card, Empty, PageHead } from '../components/ui';
import type { MappingsResponse } from '../lib/types';

export function Commands() {
  const s = t.value;
  const [data, setData] = useState<MappingsResponse | null>(null);
  const [query, setQuery] = useState('');
  const mode = status.value?.mode;
  const language = settings.value?.language ?? 'pl_PL';

  async function load() {
    try {
      setData(await api.mappings());
    } catch {
      setData({ champion: null, mode: 'spells', mappings: [] });
    }
  }

  useEffect(() => {
    void load();
  }, [mode, language]);

  const rows = useMemo(() => {
    const all = data?.mappings ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (m) =>
        m.phrase.toLowerCase().includes(q) ||
        m.key.toLowerCase().includes(q) ||
        m.source.toLowerCase().includes(q),
    );
  }, [data, query]);

  return (
    <div class="page page--wide">
      <PageHead
        title={s.nav_commands}
        lead={s.commands_lead}
        actions={
          <Button variant="quiet" size="sm" onClick={() => void load()}>
            <Icon name="refresh" size={14} />
            {s.refresh}
          </Button>
        }
      />

      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <label class="search">
          <Icon name="search" size={15} />
          <input
            class="input"
            type="search"
            placeholder={s.search_placeholder}
            aria-label={s.search_placeholder}
            value={query}
            onInput={(e) => setQuery((e.currentTarget as HTMLInputElement).value)}
          />
        </label>
        <select
          class="select select--compact"
          aria-label={s.game_language}
          title={s.game_language}
          value={language}
          disabled={!settings.value}
          onChange={(e) => void patchSettings({ language: (e.currentTarget as HTMLSelectElement).value })}
        >
          {languageOptions(s.untested).map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <span class="badge">{data?.champion || s.no_champion}</span>
        <span class="badge">
          {rows.length} {s.mappings_count}
        </span>
      </div>

      <Card flush>
        {data === null ? (
          <Empty>{s.loading}</Empty>
        ) : rows.length === 0 ? (
          <Empty>{query ? s.commands_no_results : s.commands_empty}</Empty>
        ) : (
          <div class="table__scroll">
            <table class="table">
              <thead>
                <tr>
                  <th style="width:55%">{s.col_phrase}</th>
                  <th style="width:15%">{s.col_key}</th>
                  <th style="width:30%">{s.col_source}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((m, i) => (
                  <tr key={`${m.phrase}-${m.key}-${i}`}>
                    <td>{m.phrase}</td>
                    <td>
                      <span class="key">{m.key}</span>
                    </td>
                    <td class="mono muted">{m.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
