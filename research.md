# 논문 서지정보 수집 멀티 에이전트 시스템 연구

## 1. 개요

RISS(riss.kr)와 KCI(kci.go.kr) 두 학술 데이터베이스에서 논문 서지정보를 자동 수집하는 멀티 에이전트 시스템 설계 및 구현 방안 연구.

사용자가 검색어를 입력하면 각 사이트의 검색 규칙에 맞게 쿼리를 변환하고, 두 에이전트가 병렬로 수집한 결과를 CSV 파일로 저장한다.

**배포 스택**: GitHub 저장소 관리 + Vercel 프론트엔드 배포 + Python 백엔드 API 조합으로 운영한다.

---

## 2. 데이터 소스 분석

### 2.1 RISS (riss.kr)

**기본 URL 구조**

```
GET https://www.riss.kr/search/Search.do
  ?query={검색어}
  &iStartCount={시작위치}        ← 페이지네이션 (0, 100, 200, ...)
  &colName=re_a_kor              ← 학술논문
  &colName=bib_t                 ← 학위논문
  &pageScale=100                 ← 페이지당 100개
  &strSort=RANK
  &order=%2FDESC
```

**검색어 문법 (불리언 검색)**

```
((키워드A1)|(키워드A2)) ((키워드B1)|(키워드B2))
```

예시:
```
((생성형AI)|(생성)|(ChatGPT)|(챗GPT)) ((인공지능)|(AI)) ((교육)|(수업))
```

- `|` : OR 연산자
- 그룹 사이 공백 : AND 연산자
- 괄호로 그룹화

**전체 논문 수 파싱**

```python
total_papers_tag = soup.find('span', class_='num')
total_papers = int(total_papers_tag.text.replace(',', ''))
```

**개별 논문 파싱 (컨테이너: `div.cont.ml60`)**

| 필드 | 파싱 방법 |
|------|-----------|
| Title | `p.title` 텍스트 |
| Writer | `span.writer` 텍스트 |
| Publisher | `p.etc > span[1]` |
| Year | `p.etc > span[2]` |
| Journal / Degree | `p.etc > span[3]` |
| Abstract | `p.preAbstract` (없으면 `'초록이 없습니다.'`) |
| Link | `'https://www.riss.kr' + p.title > a['href']` |

**학술논문 vs 학위논문 차이점**

| 구분 | colName | Journal 칼럼 | 추가 칼럼 |
|------|---------|-------------|----------|
| 학술논문 | `re_a_kor` | 학술지명 | - |
| 학위논문 | `bib_t` | 학위구분(석/박사) | University |

**페이지네이션**

- `iStartCount=0` → 1~100번째
- `iStartCount=100` → 101~200번째
- `time.sleep(1)` 간격 필수

---

### 2.2 KCI (kci.go.kr)

**기본 요청**

```
POST https://www.kci.go.kr/kciportal/po/search/poArtiSearList.kci
Content-Type: application/x-www-form-urlencoded
```

**POST 파라미터**

```python
payload = {
    'poSearchBean.searType': 'thesis',
    'poSearchBean.conditionList': 'KEYALL',   # 전체 필드 검색
    'poSearchBean.keywordList': search_keyword,
    'poSearchBean.sortName': 'SCORE',
    'poSearchBean.sortDir': 'desc',
    'poSearchBean.startPg': 1,
    'poSearchBean.docsCount': num_papers       # 가져올 논문 수
}
```

**검색어 문법**

```
(키워드A1|키워드A2) AND (키워드B1|키워드B2)
```

예시:
```
(생성형AI|생성|ChatGPT|챗GPT) AND (인공지능|AI) AND (교육|수업)
```

- `|` : OR
- `AND` : AND (대문자)
- RISS와 달리 괄호 내부에 공백 없음, 그룹 간 `AND` 키워드 필요

**수집 방식: 2단계 크롤링**

1단계: 목록 페이지에서 제목+링크 수집
```python
titles = soup.find_all('a', class_='subject')
```

2단계: 각 논문 상세 페이지 방문하여 서지정보 수집
```python
# 상세 페이지 URL
link = 'https://www.kci.go.kr' + tag.get('href')

# 필드 파싱
journal  = detail_soup.find('p', class_='jounal').text.strip()
year     = detail_soup.find('p', class_='vol').text.strip().split(',')[0]
publisher = detail_soup.find('p', class_='pub').text.strip().split(':')[1].strip()
writer   = detail_soup.find('div', class_='author')  # 한글 이름 regex 추출
abstracts = detail_soup.find('div', class_='innerBox open').text.strip()
```

- `time.sleep(0.1)` 간격 필수 (논문 수만큼 요청 발생)
- 논문 수가 많을 때 시간 비례 증가 (예: 409개 → ~7분)

---

## 3. 검색어 자동 변환 모듈

사용자가 자연어 형태로 키워드 그룹을 입력하면 각 사이트 규칙으로 자동 변환한다.

### 3.1 입력 형식 정의

```
그룹1: 생성형AI, 생성, ChatGPT, 챗GPT
그룹2: 인공지능, AI
그룹3: 교육, 수업
```

### 3.2 변환 로직

```python
def convert_to_riss_query(groups: list[list[str]]) -> str:
    """
    groups = [['생성형AI', '생성', 'ChatGPT'], ['인공지능', 'AI'], ['교육', '수업']]
    → "((생성형AI)|(생성)|(ChatGPT)) ((인공지능)|(AI)) ((교육)|(수업))"
    """
    parts = []
    for group in groups:
        inner = ')|('.join(group)
        parts.append(f'(({inner}))')
    return ' '.join(parts)


def convert_to_kci_query(groups: list[list[str]]) -> str:
    """
    groups = [['생성형AI', '생성', 'ChatGPT'], ['인공지능', 'AI'], ['교육', '수업']]
    → "(생성형AI|생성|ChatGPT) AND (인공지능|AI) AND (교육|수업)"
    """
    parts = []
    for group in groups:
        inner = '|'.join(group)
        parts.append(f'({inner})')
    return ' AND '.join(parts)
```

### 3.3 단일 키워드 입력 지원

단일 단어 입력 시 그룹 없이 직접 전달:
```python
# 입력: "인공지능"
riss_query  = "인공지능"
kci_query   = "인공지능"
```

---

## 4. 멀티 에이전트 아키텍처

### 4.1 에이전트 구성

```
┌─────────────────────────────────────────────────────┐
│                    Dashboard (UI)                    │
│           검색어 입력 + 진행상황 표시 + 결과 확인           │
└───────────────────────┬─────────────────────────────┘
                        │ keyword_groups
                        ▼
┌─────────────────────────────────────────────────────┐
│              Coordinator Agent (조율 에이전트)          │
│  - 검색어를 각 사이트 형식으로 변환                         │
│  - RISS/KCI 에이전트 병렬 실행                           │
│  - 결과 취합 및 CSV 저장                                │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────┐
│   RISS Agent          │  │      KCI Agent            │
│                      │  │                           │
│ ┌──────────────────┐ │  │ - POST 목록 수집           │
│ │  학술논문 수집     │ │  │ - 각 논문 상세페이지 방문    │
│ │  (colName=re_a)  │ │  │ - 서지정보 추출            │
│ └──────────────────┘ │  │ - kci_학술논문.csv 저장    │
│ ┌──────────────────┐ │  └──────────────────────────┘
│ │  학위논문 수집     │ │
│ │  (colName=bib_t) │ │
│ └──────────────────┘ │
│                      │
│ - 학술논문.csv 저장    │
│ - 학위논문.csv 저장    │
└──────────────────────┘
```

### 4.2 에이전트별 역할

| 에이전트 | 역할 | 출력 파일 |
|---------|------|----------|
| Coordinator | 쿼리 변환, 병렬 실행, 결과 취합 | `{keyword}_all.csv` |
| RISS Agent | RISS 학술/학위 수집 | `{keyword}_학술논문(riss).csv`, `{keyword}_학위논문.csv` |
| KCI Agent | KCI 학술 수집 | `{keyword}_학술논문(kci).csv` |

### 4.3 병렬 처리 방식

**Option A: `concurrent.futures.ThreadPoolExecutor`** (권장)
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_all_agents(keyword_groups):
    riss_kw = convert_to_riss_query(keyword_groups)
    kci_kw  = convert_to_kci_query(keyword_groups)
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(riss_agent_hs, riss_kw): 'riss_hs',
            executor.submit(riss_agent_hw, riss_kw): 'riss_hw',
            executor.submit(kci_agent, kci_kw):      'kci',
        }
        results = {}
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()
    return results
```

**Option B: Claude Agent SDK** (멀티 에이전트 오케스트레이션)
```python
# anthropic 패키지의 에이전트 SDK 활용
# 각 에이전트를 별도 tool로 정의하고 coordinator가 호출
```

---

## 5. 구현 계획

### 5.1 디렉토리 구조

GitHub 저장소 루트 기준 프론트엔드(Next.js)와 백엔드(Python FastAPI)를 모노레포로 구성한다.

```
riss-agent/                       ← GitHub 저장소 루트
├── frontend/                     ← Vercel 배포 대상 (Next.js)
│   ├── app/
│   │   ├── page.tsx              # 메인 대시보드 페이지
│   │   └── api/
│   │       └── download/route.ts # CSV 다운로드 엔드포인트
│   ├── components/
│   │   ├── SearchForm.tsx        # 검색어 입력 폼
│   │   ├── QueryPreview.tsx      # 쿼리 자동변환 미리보기
│   │   ├── ProgressPanel.tsx     # 수집 진행상황 표시
│   │   └── ResultTabs.tsx        # 결과 탭(학술/학위/KCI/통합)
│   ├── .env.local                # NEXT_PUBLIC_API_URL (gitignore)
│   ├── next.config.js
│   └── package.json
│
├── backend/                      ← Python FastAPI 서버
│   ├── main.py                   # FastAPI 앱 진입점
│   ├── agents/
│   │   ├── coordinator.py
│   │   ├── riss_agent.py
│   │   └── kci_agent.py
│   ├── utils/
│   │   ├── query_converter.py
│   │   └── deduplicator.py
│   ├── output/                   # CSV 임시 저장
│   └── requirements.txt
│
├── .gitignore
├── vercel.json                   ← Vercel 빌드·라우팅 설정
└── research.md
```

### 5.2 대시보드 (Next.js — Vercel 배포)

프론트엔드는 Next.js App Router로 구성하고, 백엔드 FastAPI와 분리한다. Vercel에서 `frontend/` 디렉토리를 루트로 지정해 배포한다.

**UI 컴포넌트 구성**

```
page.tsx (메인 대시보드)
├── SearchForm          ← 검색어 입력 + '/' 그룹 구분 안내
├── QueryPreview        ← RISS / KCI 쿼리 실시간 자동변환 표시
├── [수집 시작 버튼]      ← POST /api/search 호출
├── ProgressPanel       ← Server-Sent Events로 진행상황 스트리밍
└── ResultTabs
    ├── RISS 학술논문 탭
    ├── RISS 학위논문 탭
    ├── KCI 학술논문 탭
    └── 전체 통합 탭    ← CSV 다운로드 버튼 포함
```

**백엔드 연동 (FastAPI SSE)**

수집 시간이 길기 때문에(KCI 수백 건 → 수분) 단순 HTTP 응답 대신 SSE(Server-Sent Events)로 진행상황을 스트리밍한다.

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.post("/api/search")
async def search(body: SearchRequest):
    """SSE 스트림으로 진행상황 전송"""
    async def event_stream():
        async for event in coordinator.run_stream(body.keyword_groups):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/api/download/{job_id}")
def download(job_id: str, file_type: str):
    """수집 완료 후 CSV 파일 반환"""
    path = get_result_path(job_id, file_type)
    return FileResponse(path, filename=f"{file_type}.csv")
```

**프론트엔드 SSE 수신**

```typescript
// frontend/app/page.tsx (핵심 로직)
const startSearch = async (keyword: string) => {
  const groups = parseKeyword(keyword);
  const res = await fetch(`${API_URL}/api/search`, {
    method: 'POST',
    body: JSON.stringify({ keyword_groups: groups }),
  });
  const reader = res.body!.getReader();
  // 스트림에서 progress 이벤트 수신 → UI 업데이트
};
```

**대시보드 UI 흐름**

```
[검색어 입력] → [쿼리 미리보기 자동갱신] → [수집 시작]
     ↓
[SSE 실시간 진행상황: "RISS 학술 50/120건 수집 중..."]
     ↓
[탭별 결과 테이블] → [CSV 다운로드]
```

### 5.3 검색어 입력 규칙 안내

대시보드에서 사용자에게 표시할 입력 가이드:

```
입력 형식:
  - 단일 키워드: 인공지능
  - OR 그룹 (','로 구분): 생성형AI, ChatGPT, 챗GPT
  - AND 조합 ('/'로 그룹 구분):
      생성형AI,ChatGPT / 인공지능,AI / 교육,수업

자동 변환 결과:
  RISS: ((생성형AI)|(ChatGPT)) ((인공지능)|(AI)) ((교육)|(수업))
  KCI:  (생성형AI|ChatGPT) AND (인공지능|AI) AND (교육|수업)
```

---

## 6. 핵심 에이전트 코드 설계

### 6.1 RISS 에이전트 (`agents/riss_agent.py`)

```python
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import quote

RISS_SEARCH_URL = "https://www.riss.kr/search/Search.do"

def get_total_count(keyword: str, col_name: str) -> int:
    """전체 논문 수 조회"""
    params = _build_params(keyword, col_name, start=0)
    resp = requests.get(RISS_SEARCH_URL, params=params, timeout=10)
    soup = BeautifulSoup(resp.content, 'html.parser')
    tag = soup.find('span', class_='num')
    return int(tag.text.replace(',', '')) if tag else 0


def collect(keyword: str, col_name: str, paper_type: str) -> pd.DataFrame:
    """
    col_name: 're_a_kor' (학술) | 'bib_t' (학위)
    paper_type: '학술' | '학위'
    """
    total = get_total_count(keyword, col_name)
    rows = []
    
    for start in range(0, total, 100):
        params = _build_params(keyword, col_name, start)
        resp = requests.get(RISS_SEARCH_URL, params=params, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        for cont in soup.find_all('div', class_='cont ml60'):
            row = _parse_item(cont, paper_type)
            if row:
                rows.append(row)
        
        time.sleep(1)
        if len(rows) >= total:
            break
    
    return pd.DataFrame(rows)


def _parse_item(cont, paper_type: str) -> dict | None:
    try:
        spans = cont.find('p', class_='etc').find_all('span')
        abstract_tag = cont.find('p', class_='preAbstract')
        
        row = {
            'Title':    cont.find('p', class_='title').text.strip(),
            'Writer':   cont.find('span', class_='writer').text.strip(),
            'Year':     spans[2].text.strip(),
            'Abstract': abstract_tag.text.strip() if abstract_tag else '',
            'Link':     'https://www.riss.kr' + cont.find('p', class_='title').find('a')['href'].strip(),
            'Source':   'RISS',
        }
        if paper_type == '학술':
            row['Publisher'] = spans[1].text.strip()
            row['Journal']   = spans[3].text.strip()
        else:
            row['University'] = spans[1].text.strip()
            row['Degree']     = spans[3].text.strip()
        return row
    except Exception:
        return None


def _build_params(keyword, col_name, start):
    return {
        'isDetailSearch': 'N', 'searchGubun': 'true', 'viewYn': 'OP',
        'query': keyword, 'iStartCount': start, 'iGroupView': 5,
        'icate': 'all', 'colName': col_name, 'strSort': 'RANK',
        'pageScale': 100, 'order': '/DESC', 'onHanja': 'false',
    }
```

### 6.2 KCI 에이전트 (`agents/kci_agent.py`)

```python
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

KCI_SEARCH_URL = 'https://www.kci.go.kr/kciportal/po/search/poArtiSearList.kci'
KCI_BASE       = 'https://www.kci.go.kr'
HEADERS        = {'User-Agent': 'Mozilla/5.0'}


def get_total_count(keyword: str, count: int = 1) -> int:
    """검색 결과 수 확인 (1개만 가져와서 파악)"""
    payload = _build_payload(keyword, 1, 1)
    resp = requests.post(KCI_SEARCH_URL, data=payload, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.content, 'html.parser')
    # KCI는 결과 수를 별도 태그에서 추출 필요 — 실제 구현 시 확인
    count_tag = soup.find('span', class_='totalCnt')
    return int(count_tag.text.replace(',', '')) if count_tag else 0


def collect(keyword: str, num_papers: int | None = None) -> pd.DataFrame:
    """KCI 논문 수집"""
    if num_papers is None:
        num_papers = get_total_count(keyword)
    
    payload = _build_payload(keyword, 1, num_papers)
    resp = requests.post(KCI_SEARCH_URL, data=payload, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    title_tags = soup.find_all('a', class_='subject')
    rows = []
    
    for tag in title_tags:
        row = _fetch_detail(tag)
        if row:
            rows.append(row)
        time.sleep(0.1)
    
    return pd.DataFrame(rows)


def _fetch_detail(tag) -> dict | None:
    try:
        title = tag.text.strip()
        link  = KCI_BASE + tag.get('href')
        
        resp = requests.get(link, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        journal_tag  = soup.find('p', class_='jounal')
        year_tag     = soup.find('p', class_='vol')
        pub_tag      = soup.find('p', class_='pub')
        writer_tag   = soup.find('div', class_='author')
        abs_tag      = soup.find('div', class_='innerBox open')
        
        writers = ''
        if writer_tag:
            writers = ', '.join(re.findall(r'[가-힣]+', writer_tag.text.strip()))
        
        return {
            'Title':     title,
            'Writer':    writers,
            'Publisher': pub_tag.text.strip().split(':')[1].strip() if pub_tag else '',
            'Year':      year_tag.text.strip().split(',')[0] if year_tag else '',
            'Journal':   journal_tag.text.strip() if journal_tag else '',
            'Abstract':  abs_tag.text.strip() if abs_tag else '',
            'Link':      link,
            'Source':    'KCI',
        }
    except Exception:
        return None


def _build_payload(keyword, start_pg, docs_count):
    return {
        'poSearchBean.searType':     'thesis',
        'poSearchBean.conditionList': 'KEYALL',
        'poSearchBean.keywordList':   keyword,
        'poSearchBean.sortName':      'SCORE',
        'poSearchBean.sortDir':       'desc',
        'poSearchBean.startPg':       start_pg,
        'poSearchBean.docsCount':     docs_count,
    }
```

### 6.3 조율 에이전트 (`agents/coordinator.py`)

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import os

from agents.riss_agent import collect as riss_collect
from agents.kci_agent  import collect as kci_collect
from utils.query_converter import convert_to_riss_query, convert_to_kci_query


def run(keyword_groups: list[list[str]], output_dir: str = 'output') -> dict:
    """
    Returns:
        {
          'riss_hs': DataFrame,
          'riss_hw': DataFrame,
          'kci':     DataFrame,
          'all':     DataFrame,
          'files':   { 'riss_hs': path, 'riss_hw': path, 'kci': path, 'all': path }
        }
    """
    riss_kw = convert_to_riss_query(keyword_groups)
    kci_kw  = convert_to_kci_query(keyword_groups)
    label   = _make_label(keyword_groups)
    
    folder = os.path.join(output_dir, label)
    os.makedirs(folder, exist_ok=True)
    
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_hs = ex.submit(riss_collect, riss_kw, 're_a_kor', '학술')
        f_hw = ex.submit(riss_collect, riss_kw, 'bib_t',    '학위')
        f_kci = ex.submit(kci_collect, kci_kw)
    
    df_hs  = f_hs.result()
    df_hw  = f_hw.result()
    df_kci = f_kci.result()
    
    # 통합 및 중복 제거
    df_all = pd.concat([df_kci, df_hs, df_hw], ignore_index=True)
    df_all = df_all.drop_duplicates(subset=['Title', 'Journal'], keep='first')
    
    # 저장
    files = {
        'riss_hs': _save(df_hs,  folder, f'{label}_학술논문(riss).csv'),
        'riss_hw': _save(df_hw,  folder, f'{label}_학위논문.csv'),
        'kci':     _save(df_kci, folder, f'{label}_학술논문(kci).csv'),
        'all':     _save(df_all, folder, f'{label}_all.csv'),
    }
    
    return {'riss_hs': df_hs, 'riss_hw': df_hw, 'kci': df_kci, 'all': df_all, 'files': files}


def _save(df, folder, filename):
    path = os.path.join(folder, filename)
    df.to_csv(path, index=False, encoding='utf-8-sig')
    return path


def _make_label(groups):
    return '_'.join(groups[0][:2]) if groups else 'result'
```

### 6.4 검색어 변환 유틸 (`utils/query_converter.py`)

```python
def parse_user_input(raw: str) -> list[list[str]]:
    """
    '생성형AI,ChatGPT / 인공지능,AI / 교육,수업'
    → [['생성형AI', 'ChatGPT'], ['인공지능', 'AI'], ['교육', '수업']]
    """
    groups = []
    for group_str in raw.split('/'):
        keywords = [k.strip() for k in group_str.split(',') if k.strip()]
        if keywords:
            groups.append(keywords)
    return groups if groups else [[raw.strip()]]


def convert_to_riss_query(groups: list[list[str]]) -> str:
    if not groups:
        return ''
    if len(groups) == 1 and len(groups[0]) == 1:
        return groups[0][0]
    parts = ['((' + ')|('. join(g) + '))' for g in groups]
    return ' '.join(parts)


def convert_to_kci_query(groups: list[list[str]]) -> str:
    if not groups:
        return ''
    if len(groups) == 1 and len(groups[0]) == 1:
        return groups[0][0]
    parts = ['(' + '|'.join(g) + ')' for g in groups]
    return ' AND '.join(parts)
```

---

## 7. CSV 출력 스키마

### 학술논문 (RISS + KCI 공통)

| 칼럼 | 설명 | 비고 |
|------|------|------|
| Title | 논문 제목 | |
| Writer | 저자 | |
| Publisher | 발행처 (학회명) | |
| Year | 발행연도 | |
| Journal | 학술지명 | |
| Abstract | 초록 | |
| Link | 원문 링크 | |
| Source | 출처 (`RISS` / `KCI`) | |

### 학위논문 (RISS)

| 칼럼 | 설명 |
|------|------|
| Title | 논문 제목 |
| Writer | 저자 |
| University | 대학교 |
| Year | 발행연도 |
| Degree | 학위구분 (석사/박사) |
| Abstract | 초록 |
| Link | 원문 링크 |
| Source | `RISS` |

### 통합 파일 (`_all.csv`)

위 두 스키마를 `concat` 후 중복 제거. 없는 칼럼은 `NaN`.

---

## 8. 구현 시 주의사항

### 8.1 Rate Limiting

| 사이트 | 권장 딜레이 | 이유 |
|-------|-----------|------|
| RISS | `time.sleep(1)` per page | 페이지당 1초 |
| KCI  | `time.sleep(0.1)` per paper | 논문마다 상세 요청 |

KCI는 논문 수가 많을 때 시간이 오래 걸린다 (100개 → ~10초, 400개 → ~40초).

### 8.2 HTML 파싱 안정성

- RISS: `cont.find('p', class_='etc').find_all('span')` 인덱스가 논문에 따라 다를 수 있어 try/except 필수
- KCI: 상세 페이지 구조가 논문마다 다를 수 있음 (영문 논문, 공동 저자 등)
- 저자명 파싱 시 영문 이름 포함 고려 (`re.findall(r'[\w\s]+', ...)`)

### 8.3 인코딩

- 검색어 URL 인코딩: `urllib.parse.quote(keyword)`
- CSV 저장: `encoding='utf-8-sig'` (Excel에서 한글 깨짐 방지)

### 8.4 KCI 총 논문 수 파악

기존 코드는 수동으로 `paper_num`을 입력한다. 자동화를 위해:
- KCI 검색 결과 페이지의 총 건수 태그를 파싱하거나
- `docsCount=9999`로 요청 후 실제 수집된 `len(titles)`를 사용

---

## 9. GitHub + Vercel 배포 전략

### 9.1 GitHub 저장소 구성

**브랜치 전략**

```
main        ← 프로덕션 (Vercel 자동 배포 연결)
dev         ← 개발 통합 브랜치
feature/*   ← 기능별 작업 브랜치 (예: feature/kci-agent)
```

**`.gitignore` 필수 항목**

```gitignore
# 환경변수
.env
.env.local
frontend/.env.local

# 수집 결과 (용량 큰 CSV)
backend/output/

# Python
__pycache__/
*.pyc
.venv/

# Node
frontend/node_modules/
frontend/.next/
```

**GitHub Secrets (CI/CD용)**

| Secret 이름 | 용도 |
|------------|------|
| `VERCEL_TOKEN` | Vercel CLI 배포 인증 |
| `BACKEND_URL` | 프론트엔드가 호출할 백엔드 API 주소 |

---

### 9.2 Vercel 배포 구성

**핵심 제약: Vercel Serverless Function 실행 시간 제한**

| 플랜 | 최대 실행시간 |
|------|------------|
| Hobby (무료) | 10초 |
| Pro | 60초 |
| Enterprise | 900초 |

KCI 수집은 논문 수에 따라 수분 소요 → **Python 백엔드는 Vercel에서 직접 실행 불가**. 백엔드는 별도 서버(Railway, Render, 또는 로컬)에 배포하고, Vercel은 **프론트엔드 전용**으로 사용한다.

**배포 분리 구조**

```
GitHub repo
  ├── frontend/   →  Vercel (프론트엔드 자동 배포)
  └── backend/    →  Railway / Render / 직접 서버 (Python FastAPI)
```

**`vercel.json` (프론트엔드 루트 지정)**

```json
{
  "buildCommand": "cd frontend && npm run build",
  "outputDirectory": "frontend/.next",
  "installCommand": "cd frontend && npm install",
  "framework": "nextjs",
  "env": {
    "NEXT_PUBLIC_API_URL": "@backend_url"
  }
}
```

**Vercel 환경변수 설정**

Vercel 대시보드 → Settings → Environment Variables:

| 변수명 | 값 | 환경 |
|-------|-----|------|
| `NEXT_PUBLIC_API_URL` | `https://your-backend.railway.app` | Production / Preview |

---

### 9.3 GitHub Actions CI/CD

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Vercel
        run: npx vercel --prod --token=${{ secrets.VERCEL_TOKEN }}
        working-directory: frontend

  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/
```

---

### 9.4 로컬 개발 환경

```bash
# 백엔드 실행
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 프론트엔드 실행
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
# → http://localhost:3000
```

---

## 10. 의존성

**백엔드 (`backend/requirements.txt`)**

```
requests>=2.31.0
beautifulsoup4>=4.12.0
pandas>=2.0.0
fastapi>=0.110.0
uvicorn>=0.29.0
python-multipart>=0.0.9
lxml>=4.9.0          # 빠른 HTML 파싱 (선택)
```

**프론트엔드 (`frontend/package.json` 핵심 의존성)**

```json
{
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  }
}
```

---

## 11. 구현 로드맵

| 단계 | 작업 | 파일 | 비고 |
|------|------|------|------|
| 1 | GitHub 저장소 생성 + 브랜치 전략 설정 | `.gitignore`, `README.md` | 모노레포 구조 |
| 2 | 검색어 변환 유틸 구현 + 테스트 | `backend/utils/query_converter.py` | |
| 3 | RISS 에이전트 구현 (학술 + 학위) | `backend/agents/riss_agent.py` | |
| 4 | KCI 에이전트 구현 | `backend/agents/kci_agent.py` | |
| 5 | 조율 에이전트 + SSE 스트리밍 | `backend/agents/coordinator.py` | |
| 6 | FastAPI 서버 구성 | `backend/main.py` | CORS 설정 포함 |
| 7 | Next.js 프론트엔드 구현 | `frontend/app/` | Vercel 연동 준비 |
| 8 | 로컬 통합 테스트 (소량 키워드로 검증) | - | |
| 9 | Vercel 프로젝트 생성 + 환경변수 설정 | Vercel 대시보드 | `NEXT_PUBLIC_API_URL` |
| 10 | GitHub Actions CI/CD 연결 | `.github/workflows/deploy.yml` | main push → 자동 배포 |

---

## 12. 향후 확장 방향

- **Claude Agent SDK 통합**: 각 에이전트를 `tool`로 정의하고 Claude LLM이 오케스트레이션
- **SCHOLAR / DBpia 에이전트 추가**: 동일 인터페이스로 확장 가능
- **중복 제거 고도화**: 제목 유사도(fuzzy matching) 기반 중복 검출
- **스케줄링**: 정기 수집 후 새 논문만 추가 저장
- **논문 분류 자동화**: 수집 후 LLM으로 관련도 점수 부여
