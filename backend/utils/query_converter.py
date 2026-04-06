"""
검색어 자동 변환 유틸

입력 형식:
  - 단일: "인공지능"
  - OR:   "생성형AI, ChatGPT, 챗GPT"
  - AND:  "생성형AI,ChatGPT / 인공지능,AI / 교육,수업"

RISS 변환: ((생성형AI)|(ChatGPT)) ((인공지능)|(AI)) ((교육)|(수업))
KCI  변환: (생성형AI|ChatGPT) AND (인공지능|AI) AND (교육|수업)
"""


def parse_user_input(raw: str) -> list[list[str]]:
    """
    사용자 입력 문자열을 키워드 그룹 리스트로 파싱한다.

    '생성형AI,ChatGPT / 인공지능,AI / 교육,수업'
    → [['생성형AI', 'ChatGPT'], ['인공지능', 'AI'], ['교육', '수업']]
    """
    raw = raw.strip()
    if not raw:
        return []

    groups = []
    for group_str in raw.split('/'):
        keywords = [k.strip() for k in group_str.split(',') if k.strip()]
        if keywords:
            groups.append(keywords)

    return groups if groups else [[raw]]


def convert_to_riss_query(groups: list[list[str]]) -> str:
    """
    키워드 그룹 → RISS 불리언 검색 쿼리

    [['A', 'B'], ['C']] → "((A)|(B)) ((C))"
    단일 키워드 [['인공지능']] → "인공지능"
    """
    if not groups:
        return ''
    if len(groups) == 1 and len(groups[0]) == 1:
        return groups[0][0]

    parts = []
    for group in groups:
        if len(group) == 1:
            parts.append(f'(({group[0]}))')
        else:
            inner = ')|('. join(group)   # 'A)|(B)|(C' → ((A)|(B)|(C))
            parts.append(f'(({inner}))')
    return ' '.join(parts)


def convert_to_kci_query(groups: list[list[str]]) -> str:
    """
    키워드 그룹 → KCI 불리언 검색 쿼리

    [['A', 'B'], ['C']] → "(A|B) AND (C)"
    단일 키워드 [['인공지능']] → "인공지능"
    """
    if not groups:
        return ''
    if len(groups) == 1 and len(groups[0]) == 1:
        return groups[0][0]

    parts = ['(' + '|'.join(group) + ')' for group in groups]
    return ' AND '.join(parts)


def build_queries(raw: str) -> dict[str, str]:
    """
    원시 입력 → {'groups': ..., 'riss': ..., 'kci': ...} 반환
    """
    groups = parse_user_input(raw)
    return {
        'groups': groups,
        'riss':   convert_to_riss_query(groups),
        'kci':    convert_to_kci_query(groups),
    }
