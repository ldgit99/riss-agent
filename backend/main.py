"""
FastAPI 백엔드 서버

엔드포인트:
  GET  /health                     헬스체크
  GET  /api/preview                쿼리 미리보기 (변환 결과)
  POST /api/search                 수집 시작 (SSE 스트림)
  GET  /api/download/{job_id}      CSV 다운로드
"""

import glob
import os
import traceback

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from agents.coordinator import run_stream, _csv_cache
from utils.query_converter import build_queries

# ─── 앱 초기화 ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="논문 서지정보 수집기 API",
    description="RISS + KCI 논문 서지정보를 수집하는 멀티 에이전트 API",
    version="1.0.0",
)

OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "output")

# ─── CORS ───────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 요청 스키마 ─────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    keyword_raw: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"keyword_raw": "생성형AI,ChatGPT / 인공지능,AI / 교육,수업"}
            ]
        }
    }


# ─── 엔드포인트 ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["시스템"])
def health():
    return {"status": "ok"}


@app.get("/api/preview", tags=["검색"])
def preview(keyword_raw: str = Query(..., description="사용자 입력 검색어")):
    """
    검색어를 RISS / KCI 쿼리로 변환한 결과만 반환.
    프론트엔드 실시간 미리보기에서 사용.
    """
    if not keyword_raw.strip():
        raise HTTPException(status_code=400, detail="keyword_raw가 비어있습니다.")
    result = build_queries(keyword_raw)
    return {
        "riss":   result["riss"],
        "kci":    result["kci"],
        "groups": result["groups"],
    }


@app.post("/api/search", tags=["검색"])
async def search(body: SearchRequest):
    """
    논문 수집을 시작하고 SSE(Server-Sent Events) 스트림으로 진행상황을 전송.

    이벤트 타입:
      - query:    변환된 쿼리 확인
      - progress: { agent, count, total }
      - done:     { job_id, label, counts, files }
      - error:    { agent, message }
    """
    if not body.keyword_raw.strip():
        raise HTTPException(status_code=400, detail="keyword_raw가 비어있습니다.")

    return StreamingResponse(
        run_stream(body.keyword_raw),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/api/download/{job_id}", tags=["다운로드"])
def download(
    job_id: str,
    file_type: str = Query(
        ...,
        description="파일 종류: riss_hs | riss_hw | kci | all",
    ),
):
    """
    수집 완료 후 CSV 파일 다운로드.
    메모리 캐시를 먼저 확인하고, 없으면 파일시스템에서 탐색한다.
    """
    type_map = {
        "riss_hs": "학술논문(riss)",
        "riss_hw": "학위논문",
        "kci":     "학술논문(kci)",
        "all":     "all",
    }
    if file_type not in type_map:
        raise HTTPException(
            status_code=400,
            detail=f"file_type은 {list(type_map.keys())} 중 하나여야 합니다.",
        )

    try:
        # ── 메모리 캐시 우선 ───────────────────────────────────────────────
        if job_id in _csv_cache and file_type in _csv_cache[job_id]:
            csv_bytes, filename = _csv_cache[job_id][file_type]
            return Response(
                content=csv_bytes,
                media_type="text/csv; charset=utf-8-sig",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        # ── 파일시스템 폴백 ────────────────────────────────────────────────
        suffix = type_map[file_type]
        pattern = os.path.join(OUTPUT_ROOT, "**", job_id, f"*_{suffix}.csv")
        matches = glob.glob(pattern, recursive=True)

        if not matches:
            raise HTTPException(
                status_code=404,
                detail=f"파일 없음: job_id={job_id}, file_type={file_type}. 서버 재시작 후 재검색 필요.",
            )

        path = matches[0]
        filename = os.path.basename(path)

        return FileResponse(
            path,
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[download] 오류: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
