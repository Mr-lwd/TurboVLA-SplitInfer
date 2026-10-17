import { computed } from 'vue'
import { useData } from 'vitepress'
import chinese from './zh-CN.json'

/** Shared components read the active locale without duplicating their logic. */
export function useLocaleText() {
  const { lang } = useData()
  const isZh = computed(() => lang.value.startsWith('zh'))
  const t = (english: string) => isZh.value
    ? (chinese as Record<string, string>)[english] ?? english
    : english
  return { isZh, t }
}
