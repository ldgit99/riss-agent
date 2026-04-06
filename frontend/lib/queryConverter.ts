/**
 * 프론트엔드용 검색어 변환 유틸 (백엔드와 동일 로직 — 미리보기용)
 */

export type KeywordGroups = string[][]

export function parseUserInput(raw: string): KeywordGroups {
  const trimmed = raw.trim()
  if (!trimmed) return []

  const groups: KeywordGroups = []
  for (const groupStr of trimmed.split('/')) {
    const keywords = groupStr.split(',').map(k => k.trim()).filter(Boolean)
    if (keywords.length > 0) groups.push(keywords)
  }
  return groups.length > 0 ? groups : [[trimmed]]
}

export function toRissQuery(groups: KeywordGroups): string {
  if (groups.length === 0) return ''
  if (groups.length === 1 && groups[0].length === 1) return groups[0][0]

  return groups
    .map(g => g.length === 1 ? `((${g[0]}))` : `((${g.join(')|(')}))`  )
    .join(' ')
}

export function toKciQuery(groups: KeywordGroups): string {
  if (groups.length === 0) return ''
  if (groups.length === 1 && groups[0].length === 1) return groups[0][0]

  return groups.map(g => `(${g.join('|')})`).join(' AND ')
}
