import { useEffect, useRef, useState } from 'preact/hooks';
import { api, downloadLogs } from '../lib/api';
import { logLines } from '../lib/state';
import { t } from '../i18n';
import { bytes, clock, dateTime } from '../lib/format';
import { Icon } from '../components/Icon';
import { Button, Card, Empty, PageHead, Switch } from '../components/ui';
import type { LogLine, LogsResponse } from '../lib/types';

function normalize(entry: LogLine | string): LogLine {
  if (typeof entry === 'string') return { message: entry, level: 'info' };
  return entry;
}

export function Logs() {
  const s = t.value;
  const [files, setFiles] = useState<LogsResponse['files']>([]);
  const [busy, setBusy] = useState(false);
  const [autoscroll, setAutoscroll] = useState(true);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .logs()
      .then((r) => {
        setFiles(r.files ?? []);
        if (logLines.value.length === 0 && r.tail?.length) {
          logLines.value = r.tail.map(normalize);
        }
      })
      .catch(() => setFiles([]));
  }, []);

  const lines = logLines.value;

  useEffect(() => {
    if (autoscroll && boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [lines.length, autoscroll]);

  async function grab() {
    setBusy(true);
    try {
      await downloadLogs();
    } catch {
      /* przycisk wraca do stanu spoczynku */
    } finally {
      setBusy(false);
    }
  }

  return (
    <div class="page page--wide">
      <PageHead
        title={s.nav_logs}
        lead={s.logs_lead}
        actions={
          <Button variant="accent" onClick={() => void grab()} disabled={busy}>
            <Icon name={busy ? 'spinner' : 'download'} size={15} class={busy ? 'spin' : undefined} />
            {s.logs_download}
          </Button>
        }
      />

      <Card
        title={s.logs_live}
        flush
        actions={
          <span style="display:flex;align-items:center;gap:8px">
            <span class="muted" style="font-size:var(--step-xs)">
              {s.autoscroll}
            </span>
            <Switch label={s.autoscroll} checked={autoscroll} onChange={setAutoscroll} />
          </span>
        }
      >
        {lines.length === 0 ? (
          <Empty>{s.logs_empty}</Empty>
        ) : (
          <div class="log" ref={boxRef}>
            {lines.map((l, i) => {
              const lvl = (l.level ?? 'info').toLowerCase();
              return (
                <div class="log__line" key={i}>
                  <span class="muted">{clock(l.time)}</span>
                  <span
                    class={
                      lvl === 'error' || lvl === 'critical'
                        ? 'log__lvl log__lvl--error'
                        : lvl === 'warning' || lvl === 'warn'
                          ? 'log__lvl log__lvl--warning'
                          : 'log__lvl'
                    }
                  >
                    {lvl}
                  </span>
                  <span>{l.message}</span>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card title={s.logs_files} flush>
        {files.length === 0 ? (
          <Empty>{s.logs_empty}</Empty>
        ) : (
          <div class="files">
            {files.map((f) => (
              <div class="file-row" key={f.name}>
                <Icon name="scroll" size={15} class="muted" />
                <span class="file-row__name">{f.name}</span>
                <span class="file-row__meta">
                  {bytes(f.size)} {' · '} {dateTime(f.modified)}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
