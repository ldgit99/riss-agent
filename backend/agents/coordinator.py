"""
조율 에이전트 (Coordinator)

역할:
  - 검색어 변환
  - RISS 학술 / RISS 학위 / KCI 에이전트를 ThreadPoolExecutor로 병렬 실행
  - 결과 취합 및 중복 제거
  - CSV 저장
  - SSE 이벤트 스트리밍 (AsyncGenerator)
"""

import asyncio
import io
import json
import os
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from threading import Lock
from typing import AsyncGenerator

import pandas as pd

from agents import kci_agent, riss_agent
from utils.query_converter import build_queries

OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "..", "output")

# Railway 재시작 전까지 CSV를 메모리에 보관 (파일시스템 소실 대비)
# { job_id: { "riss_hs": (bytes, filename), ... } }
_csv_cache: dict[str, dict[str, tuple[bytes, str]]] = {}


# ─── SSE 이벤트 헬퍼 ────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─── 동기 수집 래퍼 (Thread 내부 실행) ─────────────────────────────────────

def _run_riss_hs(riss_kw: str, events: list, lock: Lock) -> pd.DataFrame:
    def cb(collected, total):
        with lock:
            events.append({"type": "progress", "agent": "riss_hs",
                            "count": collected, "total": total})
    return riss_agent.collect(riss_kw, "re_a_kor", "학술", progress_cb=cb)


def _run_riss_hw(riss_kw: str, events: list, lock: Lock) -> pd.DataFrame:
    def cb(collected, total):
        with lock:
            events.append({"type": "progress", "agent": "riss_hw",
                            "count": collected, "total": total})
    return riss_agent.collect(riss_kw, "bib_t", "학위", progress_cb=cb)


def _run_kci(kci_kw: str, events: list, lock: Lock) -> pd.DataFrame:
    def cb(collected, total):
        with lock:
            events.append({"type": "progress", "agent": "kci",
                            "count": collected, "total": total})
    return kci_agent.collect(kci_kw, progress_cb=cb)


# ─── 메인 진입점 ─────────────────────────────────────────────────────────────

async def run_stream(keyword_raw: str) -> AsyncGenerator[str, None]:
    """
    SSE 스트림 (AsyncGenerator).
    FastAPI StreamingResponse에서 직접 사용.

    이벤트 형식:
      progress: { type, agent, count, total }
      done:     { type, job_id, counts }
      error:    { type, agent, message }
    """
    queries = build_queries(keyword_raw)
    riss_kw = queries["riss"]
    kci_kw  = queries["kci"]

    # 쿼리 확인 이벤트
    yield _sse({"type": "query", "riss": riss_kw, "kci": kci_kw})

    job_id  = str(uuid.uuid4())[:8]
    events: list[dict] = []
    lock    = Lock()

    loop = asyncio.get_event_loop()

    # ── 병렬 실행 ──────────────────────────────────────────────────────────
    results: dict[str, pd.DataFrame | None] = {
        "riss_hs": None, "riss_hw": None, "kci": None
    }
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures: dict[Future, str] = {
            executor.submit(_run_riss_hs, riss_kw, events, lock): "riss_hs",
            executor.submit(_run_riss_hw, riss_kw, events, lock): "riss_hw",
            executor.submit(_run_kci,     kci_kw,  events, lock): "kci",
        }

        # 완료 순서대로 결과 수집하면서 SSE 이벤트 flush
        pending = set(futures.keys())
        while pending:
            done = set()
            for f in list(pending):
                if f.done():
                    done.add(f)
                    name = futures[f]
                    try:
                        results[name] = f.result(timeout=1)
                    except Exception as e:
                        errors[name] = str(e)
                        results[name] = pd.DataFrame()
                        yield _sse({"type": "error", "agent": name, "message": str(e)})

            # 쌓인 progress 이벤트 flush
            with lock:
                batch = events.copy()
                events.clear()
            for ev in batch:
                yield _sse(ev)

            pending -= done
            if pending:
                await asyncio.sleep(0.3)

    # ── 취합 ──────────────────────────────────────────────────────────────
    df_hs  = results["riss_hs"] if results["riss_hs"] is not None else pd.DataFrame()
    df_hw  = results["riss_hw"] if results["riss_hw"] is not None else pd.DataFrame()
    df_kci = results["kci"]     if results["kci"]     is not None else pd.DataFrame()

    raw_total = len(df_hs) + len(df_hw) + len(df_kci)

    df_all = pd.concat([df_kci, df_hs, df_hw], ignore_index=True)
    if not df_all.empty and "Title" in df_all.columns:
        subset = ["Title", "Journal"] if "Journal" in df_all.columns else ["Title"]
        df_all = df_all.drop_duplicates(subset=subset, keep="first")

    dedup_total    = len(df_all)
    duplicate_count = raw_total - dedup_total

    # ── 저장 ──────────────────────────────────────────────────────────────
    label  = _make_label(queries["groups"])
    folder = os.path.join(OUTPUT_ROOT, label, job_id)
    os.makedirs(folder, exist_ok=True)

    name_map = {
        "riss_hs": f"{label}_학술논문(riss).csv",
        "riss_hw": f"{label}_학위논문.csv",
        "kci":     f"{label}_학술논문(kci).csv",
        "all":     f"{label}_all.csv",
    }
    df_map = {
        "riss_hs": df_hs,
        "riss_hw": df_hw,
        "kci":     df_kci,
        "all":     df_all,
    }

    files = {}
    _csv_cache[job_id] = {}
    for key, df in df_map.items():
        fname = name_map[key]
        files[key] = _save(df, folder, fname)
        buf = io.BytesIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        _csv_cache[job_id][key] = (buf.getvalue(), fname)

    counts = {
        "riss_hs":        len(df_hs),
        "riss_hw":        len(df_hw),
        "kci":            len(df_kci),
        "all":            dedup_total,
        "raw_total":      raw_total,
        "duplicate_count": duplicate_count,
    }

    yield _sse({
        "type":    "done",
        "job_id":  job_id,
        "label":   label,
        "counts":  counts,
        "files":   files,
    })


def run_sync(keyword_raw: str) -> dict:
    """
    동기 실행 (테스트 및 CLI 용).
    """
    queries = build_queries(keyword_raw)
    riss_kw = queries["riss"]
    kci_kw  = queries["kci"]
    lock    = Lock()
    dummy: list = []

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_hs  = ex.submit(_run_riss_hs, riss_kw, dummy, lock)
        f_hw  = ex.submit(_run_riss_hw, riss_kw, dummy, lock)
        f_kci = ex.submit(_run_kci,     kci_kw,  dummy, lock)

    df_hs  = f_hs.result()
    df_hw  = f_hw.result()
    df_kci = f_kci.result()

    df_all = pd.concat([df_kci, df_hs, df_hw], ignore_index=True)
    if not df_all.empty and "Title" in df_all.columns:
        subset = ["Title", "Journal"] if "Journal" in df_all.columns else ["Title"]
        df_all = df_all.drop_duplicates(subset=subset, keep="first")

    job_id = str(uuid.uuid4())[:8]
    label  = _make_label(queries["groups"])
    folder = os.path.join(OUTPUT_ROOT, label, job_id)
    os.makedirs(folder, exist_ok=True)

    return {
        "job_id":  job_id,
        "label":   label,
        "riss_hs": df_hs,
        "riss_hw": df_hw,
        "kci":     df_kci,
        "all":     df_all,
        "files": {
            "riss_hs": _save(df_hs,  folder, f"{label}_학술논문(riss).csv"),
            "riss_hw": _save(df_hw,  folder, f"{label}_학위논문.csv"),
            "kci":     _save(df_kci, folder, f"{label}_학술논문(kci).csv"),
            "all":     _save(df_all, folder, f"{label}_all.csv"),
        },
    }


# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def _save(df: pd.DataFrame, folder: str, filename: str) -> str:
    path = os.path.join(folder, filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _make_label(groups: list[list[str]]) -> str:
    """첫 번째 그룹의 첫 두 키워드로 레이블 생성"""
    if not groups or not groups[0]:
        return "result"
    kws = groups[0][:2]
    label = "_".join(kws)
    # 파일시스템 안전 문자로 치환
    for ch in r'\/:*?"<>|()':
        label = label.replace(ch, "_")
    return label or "result"
