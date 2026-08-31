import { connection, retryNow, view } from './lib/state';
import { t } from './i18n';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { Button } from './components/ui';
import { Icon } from './components/Icon';
import { Dashboard } from './views/Dashboard';
import { SettingsView } from './views/SettingsView';
import { Engines } from './views/Engines';
import { Commands } from './views/Commands';
import { Logs } from './views/Logs';
import { About } from './views/About';

function CurrentView() {
  switch (view.value) {
    case 'settings':
      return <SettingsView />;
    case 'engines':
      return <Engines />;
    case 'commands':
      return <Commands />;
    case 'logs':
      return <Logs />;
    case 'about':
      return <About />;
    case 'dashboard':
    default:
      return <Dashboard />;
  }
}

function OfflineBanner() {
  const s = t.value;
  if (connection.value !== 'offline') return null;
  return (
    <div class="banner banner--danger banner--page">
      <Icon name="unplug" size={18} />
      <div class="banner__text">
        <div class="banner__title">{s.offline_title}</div>
        <div class="banner__sub">{s.offline_sub}</div>
      </div>
      <div class="banner__actions">
        <Button size="sm" onClick={retryNow}>
          <Icon name="refresh" size={14} />
          {s.retry}
        </Button>
      </div>
    </div>
  );
}

export function App() {
  return (
    <div class="shell">
      <Header />
      <div class="body">
        <Sidebar />
        <main class="main">
          <OfflineBanner />
          <CurrentView />
        </main>
      </div>
    </div>
  );
}
