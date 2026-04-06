"""
RISS (riss.kr) 논문 서지정보 수집 에이전트

수집 대상:
  - 학술논문: colName=re_a_kor
  - 학위논문: colName=bib_t
"""

import time
from urllib.parse import urlencode
from typing import Callable

import requests
from bs4 import BeautifulSoup
import pandas as pd

RISS_SEARCH_URL = "https://www.riss.kr/search/Search.do"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
PAGE_SIZE = 100
SLEEP_PER_PAGE = 0.3


def get_total_count(keyword: str, col_name: str) -> int:
    """해당 colName으로 검색된 전체 논문 수 반환"""
    params = _build_params(keyword, col_name, start=0)
    try:
        resp = requests.get(
            RISS_SEARCH_URL, params=params, headers=HEADERS, timeout=15
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        tag = soup.find("span", class_="num")
        if tag:
            return int(tag.text.replace(",", "").strip())
    except Exception as e:
        print(f"[RISS] get_total_count error ({col_name}): {e}")
    return 0


def collect(
    keyword: str,
    col_name: str,
    paper_type: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """
    RISS 논문 수집 후 DataFrame 반환.

    Args:
        keyword:     RISS 불리언 쿼리
        col_name:    're_a_kor' (학술) | 'bib_t' (학위)
        paper_type:  '학술' | '학위'
        progress_cb: (collected, total) 진행상황 콜백
    """
    total = get_total_count(keyword, col_name)
    print(f"[RISS {paper_type}] 전체 {total}건")

    rows: list[dict] = []

    for start in range(0, max(total, 1), PAGE_SIZE):
        params = _build_params(keyword, col_name, start)
        try:
            resp = requests.get(
                RISS_SEARCH_URL, params=params, headers=HEADERS, timeout=15
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "lxml")

            for cont in soup.find_all("div", class_="cont ml60"):
                item = _parse_item(cont, paper_type)
                if item:
                    rows.append(item)

        except Exception as e:
            print(f"[RISS {paper_type}] page error (start={start}): {e}")

        if progress_cb:
            progress_cb(len(rows), total)

        time.sleep(SLEEP_PER_PAGE)

        if len(rows) >= total:
            break

    df = pd.DataFrame(rows)
    print(f"[RISS {paper_type}] 수집 완료: {len(df)}건")
    return df


def _parse_item(cont, paper_type: str) -> dict | None:
    try:
        title_tag = cont.find("p", class_="title")
        writer_tag = cont.find("span", class_="writer")
        etc_spans = cont.find("p", class_="etc").find_all("span")
        abstract_tag = cont.find("p", class_="preAbstract")

        href = title_tag.find("a")["href"].strip()
        row = {
            "Title":    title_tag.text.strip(),
            "Writer":   writer_tag.text.strip() if writer_tag else "",
            "Year":     etc_spans[2].text.strip() if len(etc_spans) > 2 else "",
            "Abstract": abstract_tag.text.strip() if abstract_tag else "",
            "Link":     "https://www.riss.kr" + href,
            "Source":   "RISS",
        }

        if paper_type == "학술":
            row["Publisher"] = etc_spans[1].text.strip() if len(etc_spans) > 1 else ""
            row["Journal"]   = etc_spans[3].text.strip() if len(etc_spans) > 3 else ""
        else:
            row["University"] = etc_spans[1].text.strip() if len(etc_spans) > 1 else ""
            row["Degree"]     = etc_spans[3].text.strip() if len(etc_spans) > 3 else ""

        return row
    except Exception:
        return None


def _build_params(keyword: str, col_name: str, start: int) -> dict:
    return {
        "isDetailSearch": "N",
        "searchGubun":    "true",
        "viewYn":         "OP",
        "query":          keyword,
        "queryText":      "",
        "iStartCount":    start,
        "iGroupView":     5,
        "icate":          "all",
        "colName":        col_name,
        "exQuery":        "",
        "exQueryText":    "",
        "order":          "/DESC",
        "onHanja":        "false",
        "strSort":        "RANK",
        "pageScale":      PAGE_SIZE,
        "orderBy":        "",
        "fsearchMethod":  "search",
        "isFDetailSearch":"N",
        "sflag":          1,
        "searchQuery":    keyword,
        "pageNumber":     1,
    }
