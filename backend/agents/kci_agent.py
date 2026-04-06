"""
KCI (kci.go.kr) 논문 서지정보 수집 에이전트

수집 방식: 페이지네이션
  POST poArtiSearList.kci (startPg=1,2,3...) → 페이지별 목록 파싱
  상세 페이지 개별 요청 없음
"""

import re
from typing import Callable

import requests
from bs4 import BeautifulSoup
import pandas as pd

KCI_SEARCH_URL = "https://www.kci.go.kr/kciportal/po/search/poArtiSearList.kci"
KCI_BASE       = "https://www.kci.go.kr"
HEADERS        = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
PAGE_SIZE = 100  # KCI가 허용하는 최대 건수/페이지


def collect(
    keyword: str,
    num_papers: int | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """KCI 논문을 페이지네이션으로 전체 수집"""

    # 1페이지 요청으로 전체 건수 파악
    soup1, count1 = _fetch_page(keyword, 1)
    if soup1 is None:
        return pd.DataFrame()

    total = _parse_total(soup1) or count1
    if total == 0:
        print("[KCI] 검색 결과 없음")
        return pd.DataFrame()

    if num_papers is not None:
        total = min(total, num_papers)

    print(f"[KCI] 전체 {total}건 — {PAGE_SIZE}건씩 페이지 수집")

    rows: list[dict] = []

    # 1페이지 결과 먼저 파싱
    rows.extend(_parse_page(soup1))
    if progress_cb:
        progress_cb(len(rows), total)

    # 나머지 페이지 순차 요청
    page = 2
    while len(rows) < total:
        soup, _ = _fetch_page(keyword, page)
        if soup is None:
            break
        new_rows = _parse_page(soup)
        if not new_rows:
            break
        rows.extend(new_rows)
        if progress_cb:
            progress_cb(len(rows), total)
        page += 1

    df = pd.DataFrame(rows)
    print(f"[KCI] 수집 완료: {len(df)}건")
    return df


def _fetch_page(keyword: str, page: int):
    """페이지 요청 → (soup, 이 페이지 건수) 반환. 실패 시 (None, 0)"""
    payload = _build_payload(keyword, page, PAGE_SIZE)
    try:
        resp = requests.post(
            KCI_SEARCH_URL, data=payload, headers=HEADERS, timeout=30
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        count = len(soup.find_all("a", class_="subject"))
        return soup, count
    except Exception as e:
        print(f"[KCI] 페이지 {page} 요청 실패: {e}")
        return None, 0


def _parse_total(soup: BeautifulSoup) -> int:
    """HTML에서 전체 검색 건수 추출"""
    for tag, cls in [("span", "totalCnt"), ("strong", "total"), ("em", "total")]:
        el = soup.find(tag, class_=cls)
        if el:
            txt = re.sub(r"[^\d]", "", el.text)
            if txt:
                return int(txt)
    return 0


def _parse_page(soup: BeautifulSoup) -> list[dict]:
    """목록 페이지 HTML에서 논문 정보 파싱"""
    rows = []
    title_tags = soup.find_all("a", class_="subject")

    for tag in title_tags:
        try:
            title = tag.text.strip()
            href  = tag.get("href", "")
            link  = KCI_BASE + href if href.startswith("/") else href

            container = tag.find_parent("li") or tag.find_parent("div")
            writer, journal, year = "", "", ""

            if container:
                text = container.get_text(" ", strip=True)

                # 저자 (한글 이름)
                kor_names = re.findall(r"[가-힣]{2,4}(?=\s|,|;|$)", text)
                # 이름처럼 보이는 2~4글자 한글 (너무 일반적인 단어 제외)
                writer = ", ".join(kor_names[:5]) if kor_names else ""

                # 연도
                year_m = re.search(r"\b(19|20)\d{2}\b", text)
                if year_m:
                    year = year_m.group()

                # 저널명 태그 시도
                for cls in ["jounal", "journal", "magz", "source"]:
                    el = container.find(class_=cls)
                    if el:
                        journal = el.text.strip()
                        break

            rows.append({
                "Title":     title,
                "Writer":    writer,
                "Year":      year,
                "Journal":   journal,
                "Publisher": "",
                "Abstract":  "",
                "Link":      link,
                "Source":    "KCI",
            })
        except Exception as e:
            print(f"[KCI] 항목 파싱 오류: {e}")

    return rows


def _build_payload(keyword: str, start_pg: int, docs_count: int) -> dict:
    return {
        "poSearchBean.searType":      "thesis",
        "poSearchBean.conditionList": "KEYALL",
        "poSearchBean.keywordList":   keyword,
        "poSearchBean.sortName":      "SCORE",
        "poSearchBean.sortDir":       "desc",
        "poSearchBean.startPg":       start_pg,
        "poSearchBean.docsCount":     docs_count,
    }
