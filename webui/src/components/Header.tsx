import { connection, patchSettings, settings, status, theme } from '../lib/state';
import { languageOptions } from '../lib/languages';
import { t } from '../i18n';
import { Icon } from './Icon';

export function Header() {
  const s = t.value;
  const conn = connection.value;
  const dark = theme.value === 'dark';
  const cfg = settings.value;

  const connLabel = conn === 'online' ? s.conn_online : conn === 'connecting' ? s.conn_connecting : s.conn_offline;
  const dotClass = conn === 'online' ? 'dot dot--on' : conn === 'offline' ? 'dot dot--danger' : 'dot dot--off';

  return (
    <header class="header">
      <div class="header__brand">
        <span class="header__title">{s.app_title}</span>
        {status.value?.version && <span class="header__version">{status.value.version}</span>}
      </div>

      <div class="header__right">
        <span class="conn" title={connLabel}>
          <span class={dotClass} />
          {connLabel}
        </span>

        <select
          class="select select--compact"
          aria-label={s.game_language}
          title={s.game_language}
          value={cfg?.language ?? 'pl_PL'}
          disabled={!cfg}
          onChange={(e) => patchSettings({ language: (e.currentTarget as HTMLSelectElement).value })}
        >
          {languageOptions(s.untested).map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <select
          class="select select--compact"
          aria-label={s.ui_language}
          title={s.ui_language}
          value={cfg?.ui_language ?? 'pl_PL'}
          disabled={!cfg}
          onChange={(e) =>
            patchSettings({ ui_language: (e.currentTarget as HTMLSelectElement).value as 'pl_PL' | 'en_US' })
          }
        >
          <option value="pl_PL">PL</option>
          <option value="en_US">EN</option>
        </select>

        <button
          type="button"
          class="btn btn--quiet btn--icon"
          aria-label={s.theme_toggle}
          title={dark ? s.theme_light : s.theme_dark}
          onClick={() => patchSettings({ theme: dark ? 'light' : 'dark' })}
          disabled={!settings.value}
        >
          <Icon name={dark ? 'sun' : 'moon'} size={16} />
        </button>
      </div>
    </header>
  );
}
