"""Self-contained JSON and HTML reports."""

from __future__ import annotations

import html
import json
from collections.abc import Iterable
from pathlib import Path
from typing import List

from vidspec.models import CaseReport, Finding, Interval, RunReport


def write_json(report: RunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _escape(value: object) -> str:
    return html.escape(str(value))


def _timeline(intervals: Iterable[Interval], duration: float) -> str:
    bars: List[str] = []
    for interval in intervals:
        left = min(100.0, max(0.0, interval.start_seconds / max(duration, 0.001) * 100.0))
        width = min(100.0 - left, max(0.7, interval.duration_seconds / max(duration, 0.001) * 100.0))
        bars.append(
            f'<span class="event {_escape(interval.kind)}" style="left:{left:.3f}%;width:{width:.3f}%" '
            f'title="{_escape(interval.kind)}: {interval.start_seconds:.2f}s–{interval.end_seconds:.2f}s"></span>'
        )
    if not bars:
        return ""
    return '<div class="timeline"><span class="track"></span>{0}</div>'.format("".join(bars))


def _finding_row(finding: Finding) -> str:
    provenance = " · ".join(
        f"{key}={value}" for key, value in sorted(finding.provenance.items())
    )
    details = " · ".join(value for value in (finding.details, provenance) if value)
    evidence = ""
    if finding.evidence:
        evidence = '<div class="evidence-grid">{0}</div>'.format(
            "".join(
                '<figure><img src="{image}" alt="Evidence frame {index}"><figcaption>'
                '{time:.2f}s · {description}</figcaption></figure>'.format(
                    image=_escape(item.image),
                    index=item.frame_index or "",
                    time=item.timestamp_seconds,
                    description=_escape(item.description or "semantic evidence"),
                )
                for item in finding.evidence
                if item.image
            )
        )
    return """<tr>
      <td><span class="pill {status}">{status}</span></td>
      <td><strong>{check}</strong><small>{summary}</small>{evidence}</td>
      <td><code>{observed}</code></td>
      <td><code>{expected}</code><small>{details}</small></td>
    </tr>""".format(
        status=_escape(finding.status),
        check=_escape(finding.check),
        summary=_escape(finding.summary),
        observed=_escape(finding.observed if finding.observed is not None else "—"),
        expected=_escape(finding.expected if finding.expected is not None else "—"),
        details=_escape(details),
        evidence=evidence,
    )


def _case_card(case: CaseReport) -> str:
    probe = case.probe
    if probe:
        metadata = (
            f"{probe.width}×{probe.height} · {probe.fps:.2f} fps · {probe.duration_seconds:.2f}s · {probe.codec}"
            
        )
        duration = probe.duration_seconds
    else:
        metadata = "Video metadata unavailable"
        duration = 0.0
    intervals = [interval for finding in case.findings for interval in finding.intervals]
    prompt = (
        f'<blockquote><span>Prompt</span>{_escape(case.prompt)}</blockquote>'
        if case.prompt
        else ""
    )
    return """<article class="case-card">
      <header>
        <div><span class="eyebrow">TEST CASE</span><h2>{case_id}</h2></div>
        <span class="case-status {status}">{status}</span>
      </header>
      <p class="path">{video}</p>
      <p class="metadata">{metadata}</p>
      {prompt}
      {timeline}
      <table>
        <thead><tr><th>Status</th><th>Check</th><th>Observed</th><th>Expected</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </article>""".format(
        case_id=_escape(case.case_id),
        status=_escape(case.status),
        video=_escape(case.video),
        metadata=_escape(metadata),
        prompt=prompt,
        timeline=_timeline(intervals, duration),
        rows="".join(_finding_row(finding) for finding in case.findings),
    )


_STYLE = """
:root { color-scheme: dark; --bg:#080b13; --panel:#111725; --line:#273149;
  --text:#f6f8ff; --muted:#98a5bd; --cyan:#5ee6d0; --violet:#9a8cff;
  --pass:#55d68b; --warn:#f4c95d; --fail:#ff6b76; --error:#ff4d9a; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;
  background:radial-gradient(circle at 80% -10%,#29205a55,transparent 38%),var(--bg); color:var(--text); }
.shell { max-width:1160px; margin:auto; padding:64px 24px 96px; }
.hero { display:grid; grid-template-columns:1fr auto; gap:32px; align-items:end; margin-bottom:40px; }
.brand { color:var(--cyan); font-weight:800; letter-spacing:.18em; font-size:12px; }
h1 { font-size:clamp(38px,7vw,76px); letter-spacing:-.055em; line-height:.95; margin:15px 0 18px; }
.hero p,.metadata,.path { color:var(--muted); }
.run-status { width:116px;height:116px;border-radius:50%;display:grid;place-items:center;
  border:1px solid var(--line);background:#101627;font-weight:900;text-transform:uppercase; }
.run-status.pass { box-shadow:inset 0 0 0 8px #55d68b22;color:var(--pass); }
.run-status.fail,.run-status.error { box-shadow:inset 0 0 0 8px #ff6b7622;color:var(--fail); }
.summary { display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:32px; }
.stat { border:1px solid var(--line);border-radius:16px;padding:18px;background:#0e1421aa; }
.stat strong { display:block;font-size:28px; }.stat span { color:var(--muted);text-transform:uppercase;font-size:11px;letter-spacing:.12em; }
.case-card { border:1px solid var(--line);border-radius:22px;padding:26px;margin:18px 0;background:var(--panel);overflow:hidden; }
.case-card header { display:flex;justify-content:space-between;align-items:start;gap:20px; }
.eyebrow { color:var(--muted);font-size:10px;letter-spacing:.15em; }.case-card h2 { margin:3px 0;font-size:26px; }
.case-status,.pill { border-radius:99px;padding:5px 10px;font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.08em; }
.pass { color:var(--pass);background:#55d68b15; }.warn { color:var(--warn);background:#f4c95d15; }
.fail { color:var(--fail);background:#ff6b7615; }.error { color:var(--error);background:#ff4d9a15; }.skipped { color:var(--muted); }
.path { font-family:ui-monospace,monospace;margin:8px 0 0; }.metadata { margin:3px 0 22px; }
blockquote { border-left:3px solid var(--violet);margin:20px 0;padding:12px 16px;background:#0b101c;border-radius:0 10px 10px 0; }
blockquote span { display:block;color:var(--violet);font-size:10px;text-transform:uppercase;letter-spacing:.12em;margin-bottom:4px; }
.timeline { position:relative;height:44px;margin:22px 0;background:#0a0e18;border-radius:10px;border:1px solid var(--line);overflow:hidden; }
.track { position:absolute;left:0;right:0;top:21px;border-top:2px solid #3a4660; }.event { position:absolute;top:9px;height:24px;border-radius:6px;min-width:3px; }
.event.black { background:#9a8cff; }.event.freeze { background:#ff6b76; }
.evidence-grid { display:flex;gap:8px;flex-wrap:wrap;margin-top:10px; }
.evidence-grid figure { width:142px;margin:0;border:1px solid var(--line);border-radius:9px;overflow:hidden;background:#080c16; }
.evidence-grid img { display:block;width:100%;aspect-ratio:16/9;object-fit:cover; }
.evidence-grid figcaption { color:var(--muted);font-size:10px;line-height:1.35;padding:6px 8px; }
table { width:100%;border-collapse:collapse;margin-top:10px; } th { color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.1em;text-align:left; }
th,td { padding:13px 10px;border-bottom:1px solid var(--line);vertical-align:top; } td small { display:block;color:var(--muted);margin-top:2px; }
code { color:#c9d2e8;white-space:normal; } footer { color:var(--muted);margin-top:36px;text-align:center;font-size:12px; }
@media(max-width:760px){.hero{grid-template-columns:1fr}.run-status{width:82px;height:82px}.summary{grid-template-columns:repeat(2,1fr)}table{display:block;overflow-x:auto}}
"""


def render_html(report: RunReport) -> str:
    summary = report.summary
    stats = "".join(
        f'<div class="stat"><strong>{summary.get(status, 0)}</strong><span>{status}</span></div>'
        for status in ("pass", "warn", "fail", "error", "total")
    )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{suite} · InkToFilm report</title><style>{style}</style></head>
<body><main class="shell">
  <section class="hero"><div><span class="brand">INKTOFILM / RUN REPORT</span><h1>{suite}</h1>
  <p>Generated {generated}</p></div><div class="run-status {status}">{status}</div></section>
  <section class="summary">{stats}</section>
  <section>{cases}</section>
  <footer>Generated by InkToFilm · repeatable video tests, inspectable evidence</footer>
</main></body></html>""".format(
        suite=_escape(report.suite_name),
        generated=_escape(report.generated_at),
        status=_escape(report.status),
        style=_STYLE,
        stats=stats,
        cases="".join(_case_card(case) for case in report.cases),
    )


def write_html(report: RunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report), encoding="utf-8")
