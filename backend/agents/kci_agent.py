"""
KCI (kci.go.kr) 논문 서지정보 수집 에이전트

수집 방식: 2단계
  1단계 - POST poArtiSearList.kci → 논문 제목+링크 목록 (docsCount=9999)
  2단계 - 각 논문 상세 페이지 GET → 서지정보 추출 (ThreadPoolExecutor 병렬)
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
DETAIL_WORKERS = 4        # 상세 페이지 병렬 요청 수
DETAIL_TIMEOUT = (5, 15)  # (연결 타임아웃, 읽기 타임아웃)


def collect(
    keyword: str,
    num_papers: int | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """
    KCI 논문 수집 후 DataFrame 반환.

    Args:
        keyword:     KCI 불리언 쿼리
        num_papers:  수집 수 (None이면 전체 — docsCount=9999로 한 번에 요청)
        progress_cb: (collected, total) 진행상황 콜백
    """
    fetch_count = num_papers if num_papers is not None else 9999
    print(f"[KCI] 목록 요청 (docsCount={fetch_count})")

    payload = _build_payload(keyword, 1, fetch_count)
    try:
        resp = requests.post(
            KCI_SEARCH_URL, data=payload, headers=HEADERS, timeout=30
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[KCI] 목록 요청 실패: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    title_tags = soup.find_all("a", class_="subject")
    total = len(title_tags)
    if total == 0:
        print("[KCI] 검색 결과 없음")
        return pd.DataFrame()
    print(f"[KCI] {total}건 제목 발견 — 상세 페이지 병렬 수집 시작")

    rows: list[dict] = []
    completed = 0

    with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as executor:
        future_map = {executor.submit(_fetch_detail, tag): tag for tag in title_tags}
        for future in as_completed(future_map):
            completed += 1
            result = future.result()
            if result:
                rows.append(result)
            if progress_cb:
                progress_cb(completed, total)

    df = pd.DataFrame(rows)
    print(f"[KCI] 수집 완료: {len(df)}건")
    return df


def _fetch_detail(tag) -> dict | None:
    try:
        title = tag.text.strip()
        href  = tag.get("href", "")
        link  = KCI_BASE + href if href.startswith("/") else href

        resp = requests.get(link, headers=HEADERS, timeout=DETAIL_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")

        journal_tag  = soup.find("p", class_="jounal")
        year_tag     = soup.find("p", class_="vol")
        pub_tag      = soup.find("p", class_="pub")
        writer_tag   = soup.find("div", class_="author")
        abs_tag      = soup.find("div", class_="innerBox open")

        writers = ""
        if writer_tag:
            raw = writer_tag.text.strip()
            kor = re.findall(r"[가-힣]{2,5}", raw)
            eng = re.findall(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)+", raw)
            names = kor if kor else eng
            writers = ", ".join(names)

        publisher = ""
        if pub_tag:
            parts = pub_tag.text.strip().split(":")
            publisher = parts[1].strip() if len(parts) > 1 else pub_tag.text.strip()

        year = ""
        if year_tag:
            year = year_tag.text.strip().split(",")[0].strip()

        return {
            "Title":     title,
            "Writer":    writers,
            "Publisher": publisher,
            "Year":      year,
            "Journal":   journal_tag.text.strip() if journal_tag else "",
            "Abstract":  abs_tag.text.strip() if abs_tag else "",
            "Link":      link,
            "Source":    "KCI",
        }
    except Exception as e:
        print(f"[KCI] detail 파싱 실패 ({tag.text[:30]}): {e}")
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
