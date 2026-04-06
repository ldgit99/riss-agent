"""
KCI (kci.go.kr) 논문 서지정보 수집 에이전트

수집 방식: 1단계 (목록 페이지에서 직접 파싱)
  POST poArtiSearList.kci → 논문 목록 + 서지정보 일괄 추출
  상세 페이지 개별 요청 없음 → 빠르고 안정적
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


def collect(
    keyword: str,
    num_papers: int | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """
    KCI 논문 목록을 한 번의 요청으로 수집 후 DataFrame 반환.
    상세 페이지 개별 요청 없이 목록 페이지에서 직접 파싱.
    """
    fetch_count = num_papers if num_papers is not None else 9999
    print(f"[KCI] 목록 요청 (docsCount={fetch_count})")

    payload = _build_payload(keyword, 1, fetch_count)
    try:
        resp = requests.post(
            KCI_SEARCH_URL, data=payload, headers=HEADERS, timeout=60
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[KCI] 목록 요청 실패: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    # 각 논문 항목: <div class="cont"> 또는 <li> 단위
    items = soup.select("div.subjectArea") or soup.select("li.result-item")

    # fallback: a.subject 기반 파싱
    if not items:
        return _parse_by_links(soup, progress_cb)

    rows = []
    total = len(items)
    print(f"[KCI] {total}건 발견")

    for i, item in enumerate(items):
        row = _parse_item(item)
        if row:
            rows.append(row)
        if progress_cb:
            progress_cb(i + 1, total)

    df = pd.DataFrame(rows)
    print(f"[KCI] 수집 완료: {len(df)}건")
    return df


def _parse_by_links(soup: BeautifulSoup, progress_cb=None) -> pd.DataFrame:
    """a.subject 기반 목록 파싱 (fallback)"""
    title_tags = soup.find_all("a", class_="subject")
    total = len(title_tags)
    if total == 0:
        print("[KCI] 검색 결과 없음")
        return pd.DataFrame()

    print(f"[KCI] {total}건 제목 발견 (link-based 파싱)")
    rows = []

    for i, tag in enumerate(title_tags):
        title = tag.text.strip()
        href  = tag.get("href", "")
        link  = KCI_BASE + href if href.startswith("/") else href

        # 상위 컨테이너에서 메타정보 추출
        container = tag.find_parent("li") or tag.find_parent("div")
        writer, journal, year, publisher = "", "", "", ""

        if container:
            # 저자
            author_tag = container.find(class_=re.compile(r"author|writer", re.I))
            if author_tag:
                raw = author_tag.text.strip()
                kor = re.findall(r"[가-힣]{2,5}", raw)
                writer = ", ".join(kor) if kor else raw[:50]

            # 저널명
            journal_tag = container.find(class_=re.compile(r"journal|jounal|magz", re.I))
            if journal_tag:
                journal = journal_tag.text.strip()

            # 연도
            year_match = re.search(r"\b(19|20)\d{2}\b", container.text)
            if year_match:
                year = year_match.group()

        rows.append({
            "Title":     title,
            "Writer":    writer,
            "Publisher": publisher,
            "Year":      year,
            "Journal":   journal,
            "Abstract":  "",
            "Link":      link,
            "Source":    "KCI",
        })

        if progress_cb:
            progress_cb(i + 1, total)

    df = pd.DataFrame(rows)
    print(f"[KCI] 수집 완료: {len(df)}건")
    return df


def _parse_item(item) -> dict | None:
    try:
        title_tag = item.find("a", class_="subject") or item.find("a")
        if not title_tag:
            return None

        title = title_tag.text.strip()
        href  = title_tag.get("href", "")
        link  = KCI_BASE + href if href.startswith("/") else href

        writer, journal, year, publisher = "", "", "", ""

        author_tag = item.find(class_=re.compile(r"author|writer", re.I))
        if author_tag:
            raw = author_tag.text.strip()
            kor = re.findall(r"[가-힣]{2,5}", raw)
            writer = ", ".join(kor) if kor else raw[:50]

        journal_tag = item.find(class_=re.compile(r"journal|jounal|magz", re.I))
        if journal_tag:
            journal = journal_tag.text.strip()

        year_match = re.search(r"\b(19|20)\d{2}\b", item.text)
        if year_match:
            year = year_match.group()

        return {
            "Title":     title,
            "Writer":    writer,
            "Publisher": publisher,
            "Year":      year,
            "Journal":   journal,
            "Abstract":  "",
            "Link":      link,
            "Source":    "KCI",
        }
    except Exception as e:
        print(f"[KCI] 항목 파싱 실패: {e}")
        return None


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
