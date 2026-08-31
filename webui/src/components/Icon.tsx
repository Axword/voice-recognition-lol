import type { JSX } from 'preact';

/* Ikony lucide, obrysowe, wklejone jako ścieżki. Bez zależności w bundlu. */

const P = {
  mic: ['M12 19v3', 'M19 10v2a7 7 0 0 1-14 0v-2'],
  sliders: ['M10 5H3', 'M12 19H3', 'M14 3v4', 'M16 17v4', 'M21 12h-9', 'M21 19h-5', 'M21 5h-7', 'M8 10v4', 'M8 12H3'],
  cpu: [
    'M12 20v2', 'M12 2v2', 'M17 20v2', 'M17 2v2', 'M2 12h2', 'M2 17h2', 'M2 7h2',
    'M20 12h2', 'M20 17h2', 'M20 7h2', 'M7 20v2', 'M7 2v2',
  ],
  list: ['M11 5h10', 'M11 12h10', 'M11 19h10', 'M4 4h1v5', 'M4 9h2', 'M6.5 20H3.4c0-1 2.6-1.925 2.6-3.5a1.5 1.5 0 0 0-2.6-1.02'],
  scroll: [
    'M15 12h-5', 'M15 8h-5', 'M19 17V5a2 2 0 0 0-2-2H4',
    'M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3',
  ],
  info: ['M12 16v-4', 'M12 8h.01'],
  sun: ['M12 2v2', 'M12 20v2', 'm4.93 4.93 1.41 1.41', 'm17.66 17.66 1.41 1.41', 'M2 12h2', 'M20 12h2', 'm6.34 17.66-1.41 1.41', 'm19.07 4.93-1.41 1.41'],
  moon: ['M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401'],
  play: ['M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z'],
  download: ['M12 15V3', 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'm7 10 5 5 5-5'],
  x: ['M18 6 6 18', 'm6 6 12 12'],
  check: ['M20 6 9 17l-5-5'],
  search: ['m21 21-4.34-4.34'],
  refresh: ['M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8', 'M21 3v5h-5', 'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16', 'M8 16H3v5'],
  alert: ['m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3', 'M12 9v4', 'M12 17h.01'],
  unplug: ['m19 5 3-3', 'm2 22 3-3', 'M6.3 20.3a2.4 2.4 0 0 0 3.4 0L12 18l-6-6-2.3 2.3a2.4 2.4 0 0 0 0 3.4Z', 'M7.5 13.5 10 11', 'M10.5 16.5 13 14', 'm12 6 6 6 2.3-2.3a2.4 2.4 0 0 0 0-3.4l-2.6-2.6a2.4 2.4 0 0 0-3.4 0Z'],
  circleCheck: ['m9 12 2 2 4-4'],
  spinner: ['M21 12a9 9 0 1 1-6.219-8.56'],
  chevronDown: ['m6 9 6 6 6-6'],
  volume: [
    'M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z',
    'M16 9a5 5 0 0 1 0 6',
    'M19.364 18.364a9 9 0 0 0 0-12.728',
  ],
  keyboard: ['M10 8h.01', 'M12 12h.01', 'M14 8h.01', 'M16 12h.01', 'M18 8h.01', 'M6 8h.01', 'M7 16h10', 'M8 12h.01'],
  packageCheck: [
    'M12 22V12', 'm16 17 2 2 4-4',
    'M21 11.127V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.729l7 4a2 2 0 0 0 2 .001l1.32-.753',
    'M3.29 7 12 12l8.71-5', 'm7.5 4.27 8.997 5.148',
  ],
} as const;

/* Kształty, których nie da się zapisać jako path. */
const EXTRA: Partial<Record<IconName, JSX.Element[]>> = {
  mic: [<rect key="a" x="9" y="2" width="6" height="13" rx="3" />],
  cpu: [
    <rect key="a" x="4" y="4" width="16" height="16" rx="2" />,
    <rect key="b" x="8" y="8" width="8" height="8" rx="1" />,
  ],
  info: [<circle key="a" cx="12" cy="12" r="10" />],
  sun: [<circle key="a" cx="12" cy="12" r="4" />],
  search: [<circle key="a" cx="11" cy="11" r="8" />],
  circleCheck: [<circle key="a" cx="12" cy="12" r="10" />],
  stop: [<rect key="a" width="14" height="14" x="5" y="5" rx="2" />],
  keyboard: [<rect key="a" width="20" height="16" x="2" y="4" rx="2" />],
};

export type IconName = keyof typeof P | 'stop';

interface Props {
  name: IconName;
  size?: number;
  class?: string;
  strokeWidth?: number;
}

export function Icon({ name, size = 16, class: cls, strokeWidth = 1.75 }: Props) {
  const paths: readonly string[] = name === 'stop' ? [] : P[name];
  return (
    <svg
      class={cls}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width={strokeWidth}
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths.map((d) => (
        <path key={d} d={d} />
      ))}
      {EXTRA[name]}
    </svg>
  );
}
