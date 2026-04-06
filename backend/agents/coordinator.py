"""
조율 에이전트 (Coordinator)

역할:
  - 검색어 변환
  - RISS 학술 / RISS 학위 에이전트를 ThreadPoolExecutor로 병렬 실행
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

from agents import riss_agent
from utils.query_converter import build_queries

OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "..", "output")

# 재시작 전까지 CSV를 메모리에 보관
_csv_cache: dict[str, dict[str, tuple[bytes, str]]] = {}


# ─── SSE 이벤트 헬퍼 ────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─── 동기 수집 래퍼 ─────────────────────────────────────────────────────────

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


# ─── 메인 진입점 ─────────────────────────────────────────────────────────────

async def run_stream(keyword_raw: str) -> AsyncGenerator[str, None]:
    queries = build_queries(keyword_raw)
    riss_kw = queries["riss"]

    yield _sse({"type": "query", "riss": riss_kw, "kci": ""})

    job_id  = str(uuid.uuid4())[:8]
    events: list[dict] = []
    lock    = Lock()

    results: dict[str, pd.DataFrame | None] = {
        "riss_hs": None, "riss_hw": None,
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures: dict[Future, str] = {
            executor.submit(_run_riss_hs, riss_kw, events, lock): "riss_hs",
            executor.submit(_run_riss_hw, riss_kw, events, lock): "riss_hw",
        }

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
                        results[name] = pd.DataFrame()
                        yield _sse({"type": "error", "agent": name, "message": str(e)})

            with lock:
                batch = events.copy()
                events.clear()
            for ev in batch:
                yield _sse(ev)

            pending -= done
            if pending:
                await asyncio.sleep(0.3)

    df_hs = results["riss_hs"] if results["riss_hs"] is not None else pd.DataFrame()
    df_hw = results["riss_hw"] if results["riss_hw"] is not None else pd.DataFrame()

    raw_total = len(df_hs) + len(df_hw)

    df_all = pd.concat([df_hs, df_hw], ignore_index=True)
    if not df_all.empty and "Title" in df_all.columns:
        subset = ["Title", "Journal"] if "Journal" in df_all.columns else ["Title"]
        df_all = df_all.drop_duplicates(subset=subset, keep="first")

    dedup_total     = len(df_all)
    duplicate_count = raw_total - dedup_total

    label  = _make_label(queries["groups"])
    folder = os.path.join(OUTPUT_ROOT, label, job_id)
    os.makedirs(folder, exist_ok=True)

    name_map = {
        "riss_hs": f"{label}_학술논문(riss).csv",
        "riss_hw": f"{label}_학위논문.csv",
        "all":     f"{label}_all.csv",
    }
    df_map = {"riss_hs": df_hs, "riss_hw": df_hw, "all": df_all}

    files = {}
    _csv_cache[job_id] = {}
    for key, df in df_map.items():
        fname = name_map[key]
        files[key] = _save(df, folder, fname)
        buf = io.BytesIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        _csv_cache[job_id][key] = (buf.getvalue(), fname)

    counts = {
        "riss_hs":         len(df_hs),
        "riss_hw":         len(df_hw),
        "all":             dedup_total,
        "raw_total":       raw_total,
        "duplicate_count": duplicate_count,
    }

    yield _sse({
        "type":   "done",
        "job_id": job_id,
        "label":  label,
        "counts": counts,
        "files":  files,
    })


# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def _save(df: pd.DataFrame, folder: str, filename: str) -> str:
    path = os.path.join(folder, filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _make_label(groups: list[list[str]]) -> str:
    if not groups or not groups[0]:
        return "result"
    kws = groups[0][:2]
    label = "_".join(kws)
    for ch in r'\/:*?"<>|()':
        label = label.replace(ch, "_")
    return label or "result"
