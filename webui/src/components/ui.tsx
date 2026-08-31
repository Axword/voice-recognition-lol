import type { ComponentChildren, JSX } from 'preact';
import { Icon } from './Icon';

type ButtonProps = JSX.IntrinsicElements['button'] & {
  variant?: 'default' | 'accent' | 'quiet' | 'danger';
  size?: 'md' | 'sm';
};

export function Button({ variant = 'default', size = 'md', class: cls, ...rest }: ButtonProps) {
  const classes = [
    'btn',
    variant !== 'default' ? `btn--${variant}` : '',
    size === 'sm' ? 'btn--sm' : '',
    cls ?? '',
  ]
    .filter(Boolean)
    .join(' ');
  return <button type="button" class={classes} {...rest} />;
}

export function Card({
  title,
  actions,
  flush,
  children,
}: {
  title?: string;
  actions?: ComponentChildren;
  flush?: boolean;
  children: ComponentChildren;
}) {
  return (
    <section class="card">
      {title && (
        <header class="card__head">
          <h2 class="card__title">{title}</h2>
          {actions && <div style="margin-left:auto;display:flex;gap:8px">{actions}</div>}
        </header>
      )}
      <div class={flush ? 'card__body card__body--flush' : 'card__body'}>{children}</div>
    </section>
  );
}

export function Row({
  label,
  hint,
  children,
  stack,
}: {
  label: string;
  hint?: string;
  children: ComponentChildren;
  stack?: boolean;
}) {
  return (
    <div class={stack ? 'row row--stack' : 'row'}>
      <div>
        <div class="row__label">{label}</div>
        {hint && <p class="row__hint">{hint}</p>}
      </div>
      <div class="row__control">{children}</div>
    </div>
  );
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      class="switch"
      aria-checked={checked ? 'true' : 'false'}
      aria-label={label}
      onClick={() => onChange(!checked)}
    />
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div class="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          class="segmented__opt"
          aria-pressed={o.value === value ? 'true' : 'false'}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Select<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div class="select-wrap">
      <select
        class="select"
        aria-label={label}
        value={value}
        onChange={(e) => onChange((e.currentTarget as HTMLSelectElement).value as T)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <Icon name="chevronDown" size={14} />
    </div>
  );
}

export function Empty({ children }: { children: ComponentChildren }) {
  return <p class="empty">{children}</p>;
}

export function PageHead({
  title,
  lead,
  actions,
}: {
  title: string;
  lead?: string;
  actions?: ComponentChildren;
}) {
  return (
    <header class="page__head">
      <div>
        <h1>{title}</h1>
        {lead && <p class="page__lead">{lead}</p>}
      </div>
      {actions && <div class="page__head-actions">{actions}</div>}
    </header>
  );
}
