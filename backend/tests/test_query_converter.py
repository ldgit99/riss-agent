"""
query_converter 단위 테스트
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.query_converter import (
    parse_user_input,
    convert_to_riss_query,
    convert_to_kci_query,
    build_queries,
)


# ─── parse_user_input ────────────────────────────────────────────────────────

def test_parse_single_keyword():
    assert parse_user_input("인공지능") == [["인공지능"]]


def test_parse_or_group():
    result = parse_user_input("생성형AI, ChatGPT, 챗GPT")
    assert result == [["생성형AI", "ChatGPT", "챗GPT"]]


def test_parse_and_groups():
    result = parse_user_input("생성형AI,ChatGPT / 인공지능,AI / 교육,수업")
    assert result == [
        ["생성형AI", "ChatGPT"],
        ["인공지능", "AI"],
        ["교육", "수업"],
    ]


def test_parse_empty():
    assert parse_user_input("") == []
    assert parse_user_input("   ") == []


def test_parse_strips_whitespace():
    result = parse_user_input("  생성형AI , ChatGPT  /  교육 , 수업  ")
    assert result == [["생성형AI", "ChatGPT"], ["교육", "수업"]]


# ─── convert_to_riss_query ──────────────────────────────────────────────────

def test_riss_single_keyword():
    assert convert_to_riss_query([["인공지능"]]) == "인공지능"


def test_riss_or_group():
    result = convert_to_riss_query([["생성형AI", "ChatGPT", "챗GPT"]])
    assert result == "((생성형AI)|(ChatGPT)|(챗GPT))"


def test_riss_multi_group():
    groups = [["생성형AI", "ChatGPT"], ["인공지능", "AI"], ["교육", "수업"]]
    result = convert_to_riss_query(groups)
    assert result == "((생성형AI)|(ChatGPT)) ((인공지능)|(AI)) ((교육)|(수업))"


def test_riss_single_in_group():
    groups = [["인공지능"], ["교육"]]
    result = convert_to_riss_query(groups)
    assert result == "((인공지능)) ((교육))"


def test_riss_empty():
    assert convert_to_riss_query([]) == ""


# ─── convert_to_kci_query ───────────────────────────────────────────────────

def test_kci_single_keyword():
    assert convert_to_kci_query([["인공지능"]]) == "인공지능"


def test_kci_or_group():
    result = convert_to_kci_query([["생성형AI", "ChatGPT", "챗GPT"]])
    assert result == "(생성형AI|ChatGPT|챗GPT)"


def test_kci_multi_group():
    groups = [["생성형AI", "ChatGPT"], ["인공지능", "AI"], ["교육", "수업"]]
    result = convert_to_kci_query(groups)
    assert result == "(생성형AI|ChatGPT) AND (인공지능|AI) AND (교육|수업)"


def test_kci_empty():
    assert convert_to_kci_query([]) == ""


# ─── build_queries ──────────────────────────────────────────────────────────

def test_build_queries_roundtrip():
    raw = "생성형AI,ChatGPT / 교육,수업"
    result = build_queries(raw)
    assert result["groups"] == [["생성형AI", "ChatGPT"], ["교육", "수업"]]
    assert result["riss"] == "((생성형AI)|(ChatGPT)) ((교육)|(수업))"
    assert result["kci"]  == "(생성형AI|ChatGPT) AND (교육|수업)"
