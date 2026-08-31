import { useState } from 'preact/hooks';
import { api } from '../lib/api';
import { status } from '../lib/state';
import { t } from '../i18n';
import { Icon } from '../components/Icon';
import { Button, Card, PageHead, Row } from '../components/ui';
import type { UpdateInfo } from '../lib/types';

export function About() {
  const s = t.value;
  const st = status.value;
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [checking, setChecking] = useState(false);
  const [installing, setInstalling] = useState(false);

  async function check() {
    setChecking(true);
    try {
      setInfo(await api.checkUpdate());
    } catch {
      setInfo(null);
    } finally {
      setChecking(false);
    }
  }

  async function install() {
    setInstalling(true);
    try {
      await api.installUpdate();
    } catch {
      setInstalling(false);
    }
  }

  const available = info?.available ?? st?.update_available ?? false;

  return (
    <div class="page">
      <PageHead title={s.nav_about} lead={s.about_lead} />

      {available && (
        <div class="banner">
          <Icon name="packageCheck" size={18} />
          <div class="banner__text">
            <div class="banner__title">{s.update_available}</div>
            {info?.latest && <div class="banner__sub mono">{info.latest}</div>}
          </div>
          <div class="banner__actions">
            {info?.url && (
              <a class="btn btn--quiet btn--sm" href={info.url} target="_blank" rel="noreferrer">
                {s.release_page}
              </a>
            )}
            <Button variant="accent" size="sm" onClick={() => void install()} disabled={installing}>
              <Icon name={installing ? 'spinner' : 'download'} size={14} class={installing ? 'spin' : undefined} />
              {s.install_update}
            </Button>
          </div>
        </div>
      )}

      <Card flush>
        <Row label={s.app_title} hint={st?.engine_name ? `${s.stat_engine}: ${st.engine_name}` : undefined}>
          <span class="mono">{st?.version ?? info?.current ?? ''}</span>
        </Row>
        <Row
          label={s.check_now}
          hint={info && !info.available ? s.up_to_date : undefined}
        >
          <Button onClick={() => void check()} disabled={checking}>
            <Icon name={checking ? 'spinner' : 'refresh'} size={15} class={checking ? 'spin' : undefined} />
            {checking ? s.checking : s.check_now}
          </Button>
        </Row>
        <Row label={s.quit_app} hint={s.quit_hint}>
          <Button variant="danger" onClick={() => void api.quit()}>
            <Icon name="x" size={15} />
            {s.quit_app}
          </Button>
        </Row>
      </Card>

      {info?.notes && (
        <Card title={s.update_notes}>
          <p style="white-space:pre-wrap" class="muted">
            {info.notes}
          </p>
        </Card>
      )}
    </div>
  );
}
