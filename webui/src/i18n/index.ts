import { computed } from '@preact/signals';
import { pl, type Strings } from './pl';
import { en } from './en';
import { settings } from '../lib/state';

const bundles: Record<string, Strings> = { pl_PL: pl, en_US: en };

export const t = computed<Strings>(() => bundles[settings.value?.ui_language ?? 'pl_PL'] ?? pl);

export const locale = computed(() => (settings.value?.ui_language === 'en_US' ? 'en-GB' : 'pl-PL'));

export type { Strings };
