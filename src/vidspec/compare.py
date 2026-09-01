"""Status and metric regression comparison for two InkToFilm JSON reports."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from vidspec.models import STATUS_ORDER


class ComparisonError(ValueError):
    pass


def _load(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"Could not read report {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
        raise ComparisonError(f"{path} is not an InkToFilm report")
    return value


def compare_report_files(baseline_path: Path, candidate_path: Path) -> Dict[str, Any]:
    baseline = _load(baseline_path)
    candidate = _load(candidate_path)
    baseline_cases = {case["id"]: case for case in baseline["cases"]}
    candidate_cases = {case["id"]: case for case in candidate["cases"]}
    changes: List[Dict[str, Any]] = []

    for case_id in sorted(set(baseline_cases) | set(candidate_cases)):
        old = baseline_cases.get(case_id)
        new = candidate_cases.get(case_id)
        if old is None:
            changes.append({"case": case_id, "kind": "added", "before": None, "after": new["status"]})
            continue
        if new is None:
            changes.append({"case": case_id, "kind": "removed", "before": old["status"], "after": None})
            continue
        if old.get("status") != new.get("status"):
            before = str(old.get("status"))
            after = str(new.get("status"))
            kind = "regression" if STATUS_ORDER[after] > STATUS_ORDER[before] else "improvement"
            changes.append({"case": case_id, "kind": kind, "before": before, "after": after})

    regressions = sum(change["kind"] in ("regression", "removed") for change in changes)
    return {
        "schema_version": "1.0",
        "baseline": str(baseline_path),
        "candidate": str(candidate_path),
        "regressions": regressions,
        "changes": changes,
    }


def write_comparison(result: Dict[str, Any], json_path: Path, html_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = []
    for change in result["changes"]:
        rows.append(
            "<tr><td>{0}</td><td><b class='{1}'>{1}</b></td><td>{2}</td><td>{3}</td></tr>".format(
                html.escape(change["case"]),
                html.escape(change["kind"]),
                html.escape(str(change["before"] or "—")),
                html.escape(str(change["after"] or "—")),
            )
        )
    body = """<!doctype html><html><head><meta charset="utf-8"><title>InkToFilm comparison</title>
<style>body{{max-width:900px;margin:60px auto;padding:0 24px;background:#080b13;color:#f5f7ff;font:16px system-ui}}
h1{{font-size:48px}}p{{color:#9aa7bd}}table{{width:100%;border-collapse:collapse;background:#111725;border-radius:16px;overflow:hidden}}
th,td{{padding:16px;text-align:left;border-bottom:1px solid #273149}}.regression,.removed{{color:#ff6b76}}.improvement{{color:#55d68b}}.added{{color:#5ee6d0}}</style></head>
<body><p>INKTOFILM / REGRESSION REPORT</p><h1>{count} regression{suffix}</h1>
<p>{baseline}<br>↓<br>{candidate}</p><table><thead><tr><th>Case</th><th>Change</th><th>Before</th><th>After</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>""".format(
        count=result["regressions"],
        suffix="" if result["regressions"] == 1 else "s",
        baseline=html.escape(result["baseline"]),
        candidate=html.escape(result["candidate"]),
        rows="".join(rows) or "<tr><td colspan='4'>No status changes</td></tr>",
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(body, encoding="utf-8")


def output_paths(output: Path) -> Tuple[Path, Path]:
    return output / "comparison.json", output / "comparison.html"
