import { useEffect, useState } from 'preact/hooks';
import { api } from '../lib/api';
import { patchSettings, saveState, settings } from '../lib/state';
import { t } from '../i18n';
import { pct } from '../lib/format';
import { Icon } from '../components/Icon';
import { Button, Card, Empty, PageHead, Row, Segmented, Select, Switch } from '../components/ui';
import type { AudioDevice, RecognitionMode, Sensitivity, Theme, UiLanguage } from '../lib/types';
import { languageOptions } from '../lib/languages';

function SavedIndicator() {
  const s = t.value;
  const state = saveState.value;
  const on = state !== 'idle';
  const label = state === 'error' ? s.save_failed : state === 'saving' ? s.saving : s.saved;
  return (
    <span class={on ? 'saved saved--on' : 'saved'} aria-live="polite">
      {state !== 'idle' && (
        <Icon
          name={state === 'error' ? 'alert' : state === 'saving' ? 'spinner' : 'check'}
          size={13}
          class={state === 'saving' ? 'spin' : undefined}
        />
      )}
      {on ? label : ''}
    </span>
  );
}

function KeyInput({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <input
      class="input input--key"
      aria-label={label}
      maxLength={12}
      value={value}
      onInput={(e) => onChange((e.currentTarget as HTMLInputElement).value.trim().toLowerCase())}
    />
  );
}

function MicTest() {
  const s = t.value;
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ level: number; transcript: string } | null>(null);

  async function run() {
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.testAudio());
    } catch {
      setResult({ level: 0, transcript: '' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div class="row">
        <div>
          <div class="row__label">{s.test_mic}</div>
          <p class="row__hint">{s.test_mic_hint}</p>
        </div>
        <div class="row__control">
          <Button onClick={run} disabled={busy}>
            <Icon name={busy ? 'spinner' : 'volume'} size={15} class={busy ? 'spin' : undefined} />
            {busy ? s.test_mic_running : s.test_mic}
          </Button>
        </div>
      </div>

      {result && (
        <div class="mic-result">
          <div style="display:flex;align-items:center;gap:12px">
            <span class="muted" style="font-size:var(--step-s);min-width:56px">
              {s.mic_level}
            </span>
            <span class="meter">
              <span class="meter__fill" style={{ width: `${pct(result.level)}%` }} />
            </span>
            <span class="mono muted">{pct(result.level)}%</span>
          </div>
          <div style="display:flex;align-items:baseline;gap:12px">
            <span class="muted" style="font-size:var(--step-s);min-width:56px">
              {s.mic_transcript}
            </span>
            <span class="mono">{result.transcript || s.mic_transcript_empty}</span>
          </div>
        </div>
      )}
    </>
  );
}

export function SettingsView() {
  const s = t.value;
  const cfg = settings.value;
  const [devices, setDevices] = useState<AudioDevice[]>([]);

  useEffect(() => {
    api
      .audioDevices()
      .then((r) => setDevices(r.devices))
      .catch(() => setDevices([]));
  }, []);

  if (!cfg) {
    return (
      <div class="page">
        <PageHead title={s.nav_settings} lead={s.settings_lead} />
        <Card flush>
          <Empty>{s.loading}</Empty>
        </Card>
      </div>
    );
  }

  const sensHint =
    cfg.spell_sensitivity === 'low'
      ? s.sens_desc_low
      : cfg.spell_sensitivity === 'high'
        ? s.sens_desc_high
        : s.sens_desc_medium;

  const deviceOptions = [
    { value: '', label: s.audio_device_default },
    ...devices.map((d) => ({ value: d.id, label: d.default ? `${d.name} (${s.audio_device_default})` : d.name })),
  ];

  return (
    <div class="page">
      <PageHead title={s.nav_settings} lead={s.settings_lead} actions={<SavedIndicator />} />

      <Card title={s.group_recognition} flush>
        <Row label={s.recognition_mode} hint={s.recognition_mode_hint}>
          <Segmented<RecognitionMode>
            label={s.recognition_mode}
            value={cfg.recognition_mode}
            options={[
              { value: 'letters', label: s.letters_mode },
              { value: 'spells', label: s.spells_mode },
            ]}
            onChange={(v) => patchSettings({ recognition_mode: v })}
          />
        </Row>
        <Row label={s.sensitivity} hint={sensHint}>
          <Segmented<Sensitivity>
            label={s.sensitivity}
            value={cfg.spell_sensitivity}
            options={[
              { value: 'low', label: s.low_strict },
              { value: 'medium', label: s.medium },
              { value: 'high', label: s.high_loose },
            ]}
            onChange={(v) => patchSettings({ spell_sensitivity: v })}
          />
        </Row>
        <Row label={s.language} hint={s.language_hint}>
          <Select
            label={s.language}
            value={cfg.language}
            options={languageOptions(s.untested)}
            onChange={(v) => patchSettings({ language: v })}
          />
        </Row>
        <Row label={s.merge_commands} hint={s.merge_commands_hint}>
          <Switch
            label={s.merge_commands}
            checked={cfg.merge_command_languages}
            onChange={(v) => patchSettings({ merge_command_languages: v })}
          />
        </Row>
        <Row label={s.ui_language}>
          <Select<UiLanguage>
            label={s.ui_language}
            value={cfg.ui_language}
            options={[
              { value: 'pl_PL', label: 'Polski' },
              { value: 'en_US', label: 'English' },
            ]}
            onChange={(v) => patchSettings({ ui_language: v })}
          />
        </Row>
      </Card>

      <Card title={s.group_keys} flush>
        <Row label={s.flash_key} hint={s.flash_key_hint}>
          <KeyInput
            label={s.flash_key}
            value={cfg.flash_key}
            onChange={(v) => patchSettings({ flash_key: v })}
          />
        </Row>
        <Row label={s.summoner2_key} hint={s.summoner2_key_hint}>
          <KeyInput
            label={s.summoner2_key}
            value={cfg.summoner2_key}
            onChange={(v) => patchSettings({ summoner2_key: v })}
          />
        </Row>
      </Card>

      <Card title={s.group_audio} flush>
        <Row label={s.audio_device} hint={s.audio_device_hint}>
          <Select
            label={s.audio_device}
            value={cfg.audio_device ?? ''}
            options={deviceOptions}
            onChange={(v) => patchSettings({ audio_device: v === '' ? null : v })}
          />
        </Row>
        <MicTest />
      </Card>

      <Card title={s.group_app} flush>
        <Row label={s.start_with_windows} hint={s.start_with_windows_hint}>
          <Switch
            label={s.start_with_windows}
            checked={cfg.start_with_windows}
            onChange={(v) => patchSettings({ start_with_windows: v })}
          />
        </Row>
        <Row label={s.start_listening_on_launch} hint={s.start_listening_on_launch_hint}>
          <Switch
            label={s.start_listening_on_launch}
            checked={cfg.start_listening_on_launch}
            onChange={(v) => patchSettings({ start_listening_on_launch: v })}
          />
        </Row>
        <Row label={s.check_updates} hint={s.check_updates_hint}>
          <Switch
            label={s.check_updates}
            checked={cfg.check_updates}
            onChange={(v) => patchSettings({ check_updates: v })}
          />
        </Row>
        <Row label={s.theme}>
          <Segmented<Theme>
            label={s.theme}
            value={cfg.theme}
            options={[
              { value: 'dark', label: s.theme_dark },
              { value: 'light', label: s.theme_light },
              { value: 'system', label: s.theme_system },
            ]}
            onChange={(v) => patchSettings({ theme: v })}
          />
        </Row>
      </Card>
    </div>
  );
}
