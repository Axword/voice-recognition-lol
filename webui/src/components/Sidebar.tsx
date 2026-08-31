import { status, view, type ViewId } from '../lib/state';
import { t } from '../i18n';
import { Icon, type IconName } from './Icon';

const ITEMS: { id: ViewId; icon: IconName; key: 'nav_dashboard' | 'nav_settings' | 'nav_engines' | 'nav_commands' | 'nav_logs' | 'nav_about' }[] = [
  { id: 'dashboard', icon: 'mic', key: 'nav_dashboard' },
  { id: 'settings', icon: 'sliders', key: 'nav_settings' },
  { id: 'engines', icon: 'cpu', key: 'nav_engines' },
  { id: 'commands', icon: 'list', key: 'nav_commands' },
  { id: 'logs', icon: 'scroll', key: 'nav_logs' },
  { id: 'about', icon: 'info', key: 'nav_about' },
];

export function Sidebar() {
  const s = t.value;
  const current = view.value;
  const listening = status.value?.listening ?? false;

  return (
    <nav class="sidebar" aria-label={s.app_title}>
      {ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          class="nav-item"
          aria-current={current === item.id ? 'page' : undefined}
          onClick={() => (view.value = item.id)}
        >
          <Icon name={item.icon} size={16} />
          <span>{s[item.key]}</span>
          {item.id === 'dashboard' && listening && <span class="nav-item__dot" />}
          {item.id === 'about' && status.value?.update_available && <span class="nav-item__dot" />}
        </button>
      ))}

      <a
        class="sidebar__foot"
        href="https://www.youtube.com/@Axword"
        target="_blank"
        rel="noreferrer"
        title="youtube.com/@Axword"
      >
        <span>{s.created_by}</span>
        <span class="sidebar__author">Axword</span>
      </a>
    </nav>
  );
}
