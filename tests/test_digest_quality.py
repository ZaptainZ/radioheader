#!/usr/bin/env python3
"""RadioHeaderMind-1e — tests for native context-digest quality.

Covers the guards that keep the static digest short and focused:
  - active-domain top-N truncation
  - long-tail merge into a single line
  - no fabricated habits section when there is no habit data
  - char budget enforcement
  - empty domain data → no section fabricated

Run:  python3 tests/test_digest_quality.py
No external deps; loads attn-consolidate.py by path (hyphenated module name).
"""
import importlib.util
import os
import tempfile
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD_PATH = os.path.join(_HERE, "..", "attn-consolidate.py")


def _load():
    spec = importlib.util.spec_from_file_location("attn_consolidate", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load()


def test_top_n_truncation_and_tail_merge():
    # 20 domains, counts 20..1 → top-8 shown, remaining 12 merged.
    di = {f"d{i:02d}": list(range(20 - i)) for i in range(20)}  # d00 has 20, d19 has 1
    lines = M.summarize_active_domains(di, top_n=8)
    body = "\n".join(lines)
    assert lines[0] == "## 活跃领域"
    # exactly 8 "name(count)" tokens on the top line
    top_line = lines[2]
    assert top_line.count("(") == 8, top_line
    # highest-spread domain shown, lowest-spread NOT on the top line
    assert "d00(" in top_line and "d19(" not in top_line
    # tail merged: 20 - 8 = 12
    assert "其他 12 个低频领域" in body, body
    print("ok: top-N truncation + tail merge")


def test_no_tail_when_within_top_n():
    di = {"ios": [1, 2, 3], "rust": [1, 2]}
    lines = M.summarize_active_domains(di, top_n=8)
    body = "\n".join(lines)
    assert "其他" not in body, body
    assert "ios(3)" in body and "rust(2)" in body
    print("ok: no tail line when domains <= top_n")


def test_empty_domains_no_section():
    assert M.summarize_active_domains({}) == []
    assert M.summarize_active_domains(None) == []
    # all-zero counts also yield nothing (never fabricate)
    assert M.summarize_active_domains({"x": [], "y": 0}) == []
    print("ok: empty/zero domain data → no section fabricated")


def test_count_from_int_or_list():
    di = {"a": 5, "b": ["p1", "p2"]}  # mixed raw-int and list forms
    lines = M.summarize_active_domains(di, top_n=8)
    body = "\n".join(lines)
    assert "a(5)" in body and "b(2)" in body
    print("ok: count works for both int and list forms")


def test_full_digest_no_fabricated_habits_and_budget():
    with tempfile.TemporaryDirectory() as rdir:
        registry = {
            "projects": [
                {"name": "Proj", "status": "active", "activity": 0.8,
                 "domains": ["ios", "rust"], "path": "/tmp/proj"},
            ],
            "domain_index": {f"d{i}": list(range(i + 1)) for i in range(30)},
        }
        path = M.generate_context_digest(rdir, registry, search_log=[],
                                         error_patterns={}, today=datetime(2026, 6, 14))
        content = open(path, encoding="utf-8").read()
        # no user-profile.md present → no fabricated habits / 习惯 section
        assert "习惯" not in content and "Habits" not in content, content
        # active-domain section present but capped (tail merged)
        assert "## 活跃领域" in content
        assert "其他 22 个低频领域" in content, content  # 30 - 8
        # budget respected (BYTES — matches the loader's wc -c gate)
        assert M._byte_len(content) <= M.MAX_DIGEST_BYTES, M._byte_len(content)
        print("ok: no fabricated habits + domain capped + within budget")


def _make_registry(n_projects, n_items, n_domains):
    projects = [{
        "name": f"Project-{i:02d}", "status": "active",
        "activity": 0.9 - i * 0.01, "user_role": "独立开发者",
        "path": f"~/code/Project-{i:02d}",
        "domains": ["ios", "swiftui", "rust", "python"][: (i % 4) + 1],
        "problems": [f"关注{j}" for j in range(n_items)],
        "pain_points": [f"痛点{j}" for j in range(n_items)],
    } for i in range(n_projects)]
    return {"projects": projects,
            "domain_index": {f"dom{i}": list(range((i % 5) + 1)) for i in range(n_domains)}}


def test_realistic_heavy_no_truncation_all_sections():
    # Realistic heavy load (more projects/domains/errors than today) must fit the
    # byte budget WITHOUT section-drop truncation — the actionable error section
    # must survive.
    with tempfile.TemporaryDirectory() as rdir:
        registry = _make_registry(n_projects=10, n_items=4, n_domains=40)
        error_patterns = {
            f"~/code/Project-{i:02d}": [
                {"pattern": "file-not-found", "count": 20 - i, "snippet": "x" * 80},
                {"pattern": "command-not-found", "count": 3, "snippet": "y" * 80},
            ] for i in range(8)
        }
        path = M.generate_context_digest(rdir, registry, search_log=[],
                                         error_patterns=error_patterns,
                                         today=datetime(2026, 6, 14))
        content = open(path, encoding="utf-8").read()
        assert M._byte_len(content) <= M.MAX_DIGEST_BYTES, M._byte_len(content)
        assert "digest truncated" not in content, "realistic load should not truncate"
        assert "## 项目全景" in content and "## 活跃领域" in content
        assert "## 反复出现的问题" in content, "actionable error section must survive"
        # raw snippets never appear; caps enforced
        assert "x" * 80 not in content, "raw snippets must be dropped"
        landscape = content.split("## 项目全景")[1].split("## ")[0]
        assert landscape.count("- **") <= M.DIGEST_TOP_PROJECTS
        err_block = content.split("## 反复出现的问题")[1]
        assert err_block.count("- **") <= M.DIGEST_TOP_ERROR_PROJECTS
        print("ok: realistic heavy load — no truncation, all sections, compact")


def test_pathological_input_never_exceeds_byte_budget():
    # Even absurd input must never produce a file larger than the loader's byte
    # gate. Here truncation IS allowed to fire; what matters is the guard holds.
    with tempfile.TemporaryDirectory() as rdir:
        registry = _make_registry(n_projects=50, n_items=20, n_domains=200)
        # make every field huge
        for p in registry["projects"]:
            p["problems"] = ["关注" + "字" * 40 for _ in range(20)]
            p["pain_points"] = ["痛点" + "字" * 40 for _ in range(20)]
        error_patterns = {
            f"~/code/Project-{i:02d}": [{"pattern": "file-not-found", "count": 99,
                                         "snippet": "s" * 200}] for i in range(50)
        }
        path = M.generate_context_digest(rdir, registry, search_log=[],
                                         error_patterns=error_patterns,
                                         today=datetime(2026, 6, 14))
        content = open(path, encoding="utf-8").read()
        assert M._byte_len(content) <= M.MAX_DIGEST_BYTES, M._byte_len(content)
        print("ok: pathological input still within byte budget (guard holds)")


if __name__ == "__main__":
    test_top_n_truncation_and_tail_merge()
    test_no_tail_when_within_top_n()
    test_empty_domains_no_section()
    test_count_from_int_or_list()
    test_full_digest_no_fabricated_habits_and_budget()
    test_realistic_heavy_no_truncation_all_sections()
    test_pathological_input_never_exceeds_byte_budget()
    print("\nAll digest-quality tests passed.")
