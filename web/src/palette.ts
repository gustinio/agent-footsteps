import type { ResultStatus, ToolCategory } from '@/site'

// Full class names are written out so Tailwind can see them.
export const CATEGORY_FILL: Record<ToolCategory, string> = {
  shell: 'fill-sky-500',
  read: 'fill-emerald-500',
  search: 'fill-teal-500',
  edit: 'fill-amber-500',
  plan: 'fill-violet-500',
  web: 'fill-pink-500',
  finish: 'fill-slate-900 dark:fill-slate-100',
  other: 'fill-orange-500',
  none: 'fill-slate-300 dark:fill-slate-600',
}

export const STATUS_LABEL: Record<ResultStatus, string> = {
  ok: 'result ok',
  error: 'result error',
  empty: 'no result',
}
