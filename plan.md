# 논문 서지정보 수집 멀티 에이전트 — 구현 계획

> **기반 문서**: `research.md`  
> **목표**: RISS + KCI 논문 서지정보를 수집하는 멀티 에이전트 시스템을  
> Next.js(Vercel) 프론트엔드 + FastAPI 백엔드 구조로 완성한다.

---

## 전체 흐름

```
Phase 0  환경 준비 (GitHub, 폴더 구조)
Phase 1  백엔드 — 유틸 & 에이전트
Phase 2  백엔드 — FastAPI 서버
Phase 3  프론트엔드 — Next.js 대시보드
Phase 4  로컬 통합 테스트
Phase 5  배포 (Vercel + Railway)
Phase 6  GitHub Actions CI/CD
```

---

## Phase 0. 환경 준비

### 0-1. GitHub 저장소 생성

1. GitHub에서 `riss-agent` 저장소 생성 (Public 또는 Private)
2. 로컬에 클론

```bash
git clone https://github.com/{username}/riss-agent.git
cd riss-agent
git checkout -b dev
```

### 0-2. 모노레포 폴더 스캐폴딩

```bash
mkdir -p backend/agents backend/utils backend/output
mkdir -p frontend/app/api/download
mkdir -p frontend/components
mkdir -p .github/workflows
```

최종 디렉토리:

```
riss-agent/
├── backend/
│   ├── agents/
│   ├── utils/
│   ├── output/          ← .gitignore 등록
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   └── api/download/route.ts
│   ├── components/
│   │   ├── SearchForm.tsx
│   │   ├── QueryPreview.tsx
│   │   ├── ProgressPanel.tsx
│   │   └── ResultTabs.tsx
│   ├── next.config.js
│   └── package.json
├── .github/workflows/deploy.yml
├── .gitignore
├── vercel.json
├── research.md
└── plan.md
```

### 0-3. .gitignore 작성

```gitignore
# 환경변수
.env
.env.local
frontend/.env.local

# 수집 결과 CSV (용량 큰 파일)
backend/output/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# Node
frontend/node_modules/
frontend/.next/
frontend/out/

# OS
.DS_Store
Thumbs.db
```

### 0-4. Python 가상환경 초기화

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**`backend/requirements.txt`**

```
requests>=2.31.0
beautifulsoup4>=4.12.0
pandas>=2.0.0
fastapi>=0.110.0
uvicorn>=0.29.0
python-multipart>=0.0.9
lxml>=4.9.0
pytest>=8.0.0
```

### 0-5. Next.js 프로젝트 초기화

```bash
cd frontend
npx create-next-app@latest . --typescript --app --tailwind --no-src-dir --import-alias "@/*"
```

---

## Phase 1. 백엔드 — 유틸 & 에이전트

### 1-1. 검색어 변환 유틸

**파일**: `backend/utils/query_converter.py`

구현 내용:
- `parse_user_input(raw: str) -> list[list[str]]`
  - `'생성형AI,ChatGPT / 인공지능,AI'` → `[['생성형AI','ChatGPT'], ['인공지능','AI']]`
  - `/`로 AND 그룹 분리, `,`로 OR 키워드 분리
  - 단일 단어 입력 시 `[[word]]` 반환
- `convert_to_riss_query(groups) -> str`
  - `[['A','B'],['C']]` → `"((A)|(B)) ((C))"`
- `convert_to_kci_query(groups) -> str`
  - `[['A','B'],['C']]` → `"(A|B) AND (C)"`

**검증 기준**: 단위 테스트 `backend/tests/test_query_converter.py`

```python
def test_riss_multi_group():
    groups = [['생성형AI', 'ChatGPT'], ['교육', '수업']]
    assert convert_to_riss_query(groups) == '((생성형AI)|(ChatGPT)) ((교육)|(수업))'

def test_kci_multi_group():
    groups = [['생성형AI', 'ChatGPT'], ['교육', '수업']]
    assert convert_to_kci_query(groups) == '(생성형AI|ChatGPT) AND (교육|수업)'

def test_single_keyword():
    groups = [['인공지능']]
    assert convert_to_riss_query(groups) == '인공지능'
    assert convert_to_kci_query(groups) == '인공지능'
```

---

### 1-2. RISS 에이전트

**파일**: `backend/agents/riss_agent.py`

구현 내용:

| 함수 | 역할 |
|------|------|
| `get_total_count(keyword, col_name)` | `span.num` 파싱으로 총 논문 수 반환 |
| `collect(keyword, col_name, paper_type)` | 페이지 순회 → DataFrame 반환 |
| `_parse_item(cont, paper_type)` | `div.cont.ml60` 파싱 → dict |
| `_build_params(keyword, col_name, start)` | GET 파라미터 dict 생성 |

핵심 설계 포인트:
- `col_name='re_a_kor'` → 학술논문 (Journal 칼럼)
- `col_name='bib_t'` → 학위논문 (University, Degree 칼럼)
- 페이지당 `time.sleep(1)`
- 모든 파싱에 `try/except` 적용, 실패 시 해당 항목 스킵
- `Source='RISS'` 칼럼 추가

**반환 DataFrame 스키마 (학술)**

| Title | Writer | Publisher | Year | Journal | Abstract | Link | Source |
|-------|--------|-----------|------|---------|----------|------|--------|

**반환 DataFrame 스키마 (학위)**

| Title | Writer | University | Year | Degree | Abstract | Link | Source |
|-------|--------|------------|------|--------|----------|------|--------|

**검증 기준**: 키워드 `"인공지능"` 학술논문 10건 수집 후 칼럼·타입 확인

---

### 1-3. KCI 에이전트

**파일**: `backend/agents/kci_agent.py`

구현 내용:

| 함수 | 역할 |
|------|------|
| `get_total_count(keyword)` | 검색 결과 총 건수 파싱 |
| `collect(keyword, num_papers)` | POST 목록 수집 → 상세 방문 → DataFrame |
| `_fetch_detail(tag)` | 논문 상세 페이지 파싱 → dict |
| `_build_payload(keyword, start_pg, count)` | POST payload dict 생성 |

핵심 설계 포인트:
- 1단계: `POST poArtiSearList.kci` → `a.subject` 목록
- 2단계: 각 논문 `GET` 상세 페이지 → 서지정보 추출
- `time.sleep(0.1)` per paper
- `num_papers=None`이면 `get_total_count()` 결과 사용
- `Source='KCI'` 칼럼 추가
- 영문 저자명 처리 (`re.findall(r'[가-힣A-Za-z\s]+', ...)`)

**반환 DataFrame 스키마**

| Title | Writer | Publisher | Year | Journal | Abstract | Link | Source |
|-------|--------|-----------|------|---------|----------|------|--------|

**검증 기준**: 키워드 `"인공지능"` 20건 제한 수집 후 칼럼 확인

---

### 1-4. 조율 에이전트

**파일**: `backend/agents/coordinator.py`

구현 내용:

| 함수 | 역할 |
|------|------|
| `run(keyword_groups, output_dir, job_id)` | 병렬 수집 → 취합 → CSV 저장 → 결과 dict 반환 |
| `run_stream(keyword_groups, job_id)` | 위와 동일 + SSE 이벤트 yield |
| `_save(df, folder, filename)` | CSV utf-8-sig 저장 |
| `_make_label(groups)` | 폴더·파일명용 레이블 생성 |

**병렬 실행**

```python
with ThreadPoolExecutor(max_workers=3) as ex:
    f_hs  = ex.submit(riss_collect, riss_kw, 're_a_kor', '학술')
    f_hw  = ex.submit(riss_collect, riss_kw, 'bib_t',    '학위')
    f_kci = ex.submit(kci_collect,  kci_kw)
```

**SSE 이벤트 타입**

```json
{ "type": "progress", "agent": "riss_hs", "count": 50, "total": 120 }
{ "type": "progress", "agent": "kci",     "count": 30, "total": 409 }
{ "type": "done",     "job_id": "abc123",  "counts": { "riss_hs": 120, "riss_hw": 45, "kci": 409, "all": 550 } }
{ "type": "error",    "agent": "kci",     "message": "..." }
```

**중복 제거 로직**

```python
df_all = pd.concat([df_kci, df_hs, df_hw], ignore_index=True)
df_all = df_all.drop_duplicates(subset=['Title', 'Journal'], keep='first')
```

KCI 우선 유지 (먼저 concat). `Journal` 없는 학위논문은 중복 제거 대상 아님.

**출력 파일 (output/{label}/{job_id}/)**

```
{label}_학술논문(riss).csv
{label}_학위논문.csv
{label}_학술논문(kci).csv
{label}_all.csv
```

---

## Phase 2. 백엔드 — FastAPI 서버

**파일**: `backend/main.py`

### 2-1. 엔드포인트 설계

| Method | Path | 역할 |
|--------|------|------|
| `POST` | `/api/search` | 수집 시작, SSE 스트림 반환 |
| `GET` | `/api/download/{job_id}` | CSV 파일 다운로드 |
| `GET` | `/api/preview` | 쿼리 미리보기 (변환 결과만 반환) |
| `GET` | `/health` | 헬스체크 |

### 2-2. 요청/응답 스키마

```python
# POST /api/search 요청 body
class SearchRequest(BaseModel):
    keyword_raw: str          # "생성형AI,ChatGPT / 교육,수업"
    # keyword_groups는 서버에서 parse_user_input()으로 변환

# GET /api/preview 쿼리 파라미터
# ?keyword_raw=생성형AI%2CChatGPT+%2F+교육
# 응답: { "riss": "...", "kci": "..." }
```

### 2-3. CORS 설정

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",     # Vercel 프리뷰 URL
        "https://your-domain.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2-4. 로컬 실행

```bash
cd backend
uvicorn main:app --reload --port 8000
# → http://localhost:8000/docs (Swagger UI)
```

**검증 기준**: Swagger UI에서 `/api/preview` 호출 → RISS/KCI 쿼리 변환 결과 정상 반환

---

## Phase 3. 프론트엔드 — Next.js 대시보드

### 3-1. 환경변수

**`frontend/.env.local`** (gitignore 대상)

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3-2. 컴포넌트 구현 순서

#### ① `SearchForm.tsx`

- 텍스트 입력창 (키워드 입력)
- 입력 형식 안내 툴팁:
  ```
  단일: 인공지능
  OR:   생성형AI, ChatGPT, 챗GPT
  AND:  생성형AI,ChatGPT / 인공지능,AI / 교육,수업
  ```
- 수집 시작 버튼 (로딩 중 비활성화)
- props: `onSubmit(keyword: string)`, `isLoading: boolean`

#### ② `QueryPreview.tsx`

- 입력 변경 시마다 `/api/preview` 호출 (debounce 300ms)
- RISS 쿼리 / KCI 쿼리 나란히 표시
- props: `keyword: string`

#### ③ `ProgressPanel.tsx`

- SSE 이벤트 수신 → 에이전트별 진행 바 표시
  ```
  RISS 학술논문  ████████░░  80/120건
  RISS 학위논문  ██████████  45/45건  ✓
  KCI  학술논문  ████░░░░░░  160/409건
  ```
- `type: "done"` 수신 시 완료 상태로 전환
- props: `events: SSEEvent[]`

#### ④ `ResultTabs.tsx`

- 탭: `RISS 학술` | `RISS 학위` | `KCI` | `전체 통합`
- 각 탭에 결과 테이블 + 건수 뱃지
- 탭별 CSV 다운로드 버튼 → `/api/download/{job_id}?file_type=riss_hs` 호출
- props: `jobId: string`, `counts: Record<string, number>`

#### ⑤ `app/page.tsx` (조립)

```
상태: keyword, isLoading, events[], jobId, counts
────────────────────────────────
<SearchForm />
<QueryPreview keyword={keyword} />
{isLoading && <ProgressPanel events={events} />}
{jobId && <ResultTabs jobId={jobId} counts={counts} />}
```

SSE 연결 로직:

```typescript
const startSearch = async (keyword: string) => {
  setIsLoading(true);
  setEvents([]);
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword_raw: keyword }),
  });
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const event = JSON.parse(line.slice(6));
      setEvents(prev => [...prev, event]);
      if (event.type === 'done') {
        setJobId(event.job_id);
        setCounts(event.counts);
        setIsLoading(false);
      }
    }
  }
};
```

### 3-3. `app/api/download/route.ts`

```typescript
// Next.js Route Handler — 백엔드 다운로드 프록시
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const jobId    = searchParams.get('jobId');
  const fileType = searchParams.get('fileType');
  const upstream = `${process.env.API_URL}/api/download/${jobId}?file_type=${fileType}`;
  const res = await fetch(upstream);
  return new Response(res.body, {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${fileType}.csv"`,
    },
  });
}
```

### 3-4. 로컬 실행

```bash
cd frontend
npm run dev
# → http://localhost:3000
```

**검증 기준**: 브라우저에서 키워드 입력 → 쿼리 미리보기 표시 → 수집 시작 → 진행 바 갱신 → 탭 결과 표시 → CSV 다운로드

---

## Phase 4. 로컬 통합 테스트

### 4-1. 단위 테스트

```bash
cd backend
pytest tests/ -v
```

테스트 대상:
- `test_query_converter.py`: 쿼리 변환 케이스 5개 이상
- `test_riss_agent.py`: 소량(10건) 수집 후 칼럼 검증
- `test_kci_agent.py`: 소량(10건) 수집 후 칼럼 검증

### 4-2. E2E 시나리오

| # | 검색어 입력 | 기대 결과 |
|---|------------|----------|
| 1 | `인공지능` | RISS/KCI 결과 모두 수집됨 |
| 2 | `생성형AI,ChatGPT / 교육,수업` | RISS 쿼리 `((생성형AI)\|(ChatGPT)) ((교육)\|(수업))` 변환 확인 |
| 3 | 결과 없는 키워드 | 빈 DataFrame, 에러 없이 완료 |
| 4 | CSV 다운로드 | `utf-8-sig` 인코딩, Excel 한글 정상 표시 |

### 4-3. 성능 확인

- KCI 100건 수집: 10초 이내 완료 확인
- RISS 학술 300건 (3페이지): 5초 이내 완료 확인
- SSE 이벤트 프론트엔드에 실시간 반영 확인

---

## Phase 5. 배포

### 5-1. 백엔드 — Railway 배포

> Railway는 Python FastAPI 배포가 간단하고, 실행시간 제한이 없어 KCI 스크래핑에 적합하다.

1. [railway.app](https://railway.app) 접속 → New Project → Deploy from GitHub
2. `backend/` 폴더를 Root Directory로 지정
3. 환경변수 설정 (필요 시)
4. 배포 후 URL 확인: `https://riss-agent-backend.up.railway.app`

**`backend/Procfile`** (Railway용)

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 5-2. 프론트엔드 — Vercel 배포

1. [vercel.com](https://vercel.com) 접속 → New Project → Import `riss-agent` 저장소
2. **Root Directory**: `frontend`
3. **Framework Preset**: Next.js (자동 감지)
4. **Environment Variables** 추가:
   - `NEXT_PUBLIC_API_URL` = `https://riss-agent-backend.up.railway.app`
   - `API_URL` = `https://riss-agent-backend.up.railway.app` (서버사이드용)
5. Deploy

**`vercel.json`** (저장소 루트)

```json
{
  "buildCommand": "cd frontend && npm run build",
  "outputDirectory": "frontend/.next",
  "installCommand": "cd frontend && npm install",
  "framework": "nextjs"
}
```

### 5-3. CORS 재확인

Railway 배포 후 백엔드 `main.py`의 `allow_origins`에 Vercel 도메인 추가:

```python
allow_origins=[
    "http://localhost:3000",
    "https://riss-agent.vercel.app",
    "https://*.vercel.app",
]
```

### 5-4. 배포 검증

- `https://riss-agent.vercel.app` 접속
- 키워드 입력 → 수집 시작 → 결과 CSV 다운로드 정상 동작 확인

---

## Phase 6. GitHub Actions CI/CD

**파일**: `.github/workflows/deploy.yml`

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main, dev]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run tests
        run: pytest backend/tests/ -v

  deploy-frontend:
    needs: test-backend
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Vercel
        run: |
          cd frontend
          npx vercel --prod --token=${{ secrets.VERCEL_TOKEN }} \
            --env NEXT_PUBLIC_API_URL=${{ secrets.BACKEND_URL }}
```

**GitHub Secrets 등록** (저장소 Settings → Secrets):

| Secret | 값 |
|--------|-----|
| `VERCEL_TOKEN` | Vercel 계정 토큰 |
| `BACKEND_URL` | Railway 백엔드 URL |

**브랜치 보호 규칙** (Settings → Branches → main):
- `test-backend` 통과 필수
- PR 없이 직접 push 금지

---

## 체크리스트

### Phase 0
- [ ] GitHub 저장소 생성 + dev 브랜치
- [ ] 모노레포 폴더 구조 생성
- [ ] `.gitignore` 작성
- [ ] Python 가상환경 + requirements.txt
- [ ] Next.js 프로젝트 초기화

### Phase 1
- [ ] `query_converter.py` 구현 + 단위 테스트 통과
- [ ] `riss_agent.py` 구현 + 소량 수집 검증
- [ ] `kci_agent.py` 구현 + 소량 수집 검증
- [ ] `coordinator.py` 구현 + SSE 이벤트 형식 확인

### Phase 2
- [ ] `main.py` FastAPI 서버 구현
- [ ] Swagger UI에서 전 엔드포인트 동작 확인
- [ ] CORS 설정 완료

### Phase 3
- [ ] `SearchForm.tsx` + 입력 안내
- [ ] `QueryPreview.tsx` + debounce 적용
- [ ] `ProgressPanel.tsx` + SSE 연결
- [ ] `ResultTabs.tsx` + 다운로드 버튼
- [ ] `page.tsx` 조립 완료

### Phase 4
- [ ] pytest 전체 통과
- [ ] E2E 4개 시나리오 통과
- [ ] CSV 파일 Excel 한글 정상 표시

### Phase 5
- [ ] Railway 백엔드 배포 완료
- [ ] Vercel 프론트엔드 배포 완료
- [ ] 프로덕션 E2E 검증 완료

### Phase 6
- [ ] GitHub Actions 파이프라인 동작 확인
- [ ] main PR merge 시 자동 배포 확인

---

## 핵심 의존성 요약

| 영역 | 기술 | 용도 |
|------|------|------|
| 백엔드 언어 | Python 3.11 | 에이전트 + API |
| 웹 프레임워크 | FastAPI + uvicorn | REST API + SSE |
| HTML 파싱 | BeautifulSoup4 + lxml | RISS/KCI 스크래핑 |
| 데이터 처리 | pandas | DataFrame → CSV |
| 프론트엔드 | Next.js 14 (App Router) + TypeScript | 대시보드 |
| 스타일 | Tailwind CSS | UI 스타일링 |
| 배포 — 프론트 | Vercel | Next.js 자동 빌드·배포 |
| 배포 — 백엔드 | Railway | FastAPI 장시간 실행 허용 |
| 소스 관리 | GitHub | 브랜치·PR·CI/CD |
| CI/CD | GitHub Actions | 테스트 + Vercel 배포 자동화 |
