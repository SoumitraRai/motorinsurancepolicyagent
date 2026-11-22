"""Development CLI (not a substitute for the browser upload):

    python -m rater.cli run <policy.pdf> --out samples/output/<stem>

writes `<stem>.json` (the structured result) and `<stem>.md` (a readable decision trace).
"""

import argparse
import json
import sys
from pathlib import Path

from rater.config import build_deps
from rater.pipeline import run_pipeline
from rater.result import Result


def trace_markdown(result: Result, source: str) -> str:
    body = json.loads(result.to_json())
    lines = [f"# Decision trace: {source}", "", f"**Status:** `{body['status']}`", ""]
    for comp in ("od", "tp"):
        r = body["rates"][comp]
        shown = (
            "not applicable"
            if r["applicable"] is False
            else "—"
            if r["ratePercent"] is None
            else f"{r['ratePercent']:g}%"
        )
        lines.append(
            f"- **{comp.upper()}:** {shown}"
            + (f" ({r['reason']})" if r["reason"] else "")
            + (f" · `{r['gridCitation']}`" if r.get("gridCitation") else "")
        )
    c = body["confidence"]
    lines += ["", f"**Confidence:** {c['level']} ({c['reason']})", "", "## Steps", ""]
    for t in body["trace"]:
        lines.append(f"{t['step']}. **{t['kind']}**: {t['decision']}")
        if t.get("policyCitation"):
            lines.append(f"   - Policy: `{t['policyCitation']}`")
        if t.get("gridCitation"):
            lines.append(f"   - Grid: `{t['gridCitation']}`")
        for w in t.get("warnings", []):
            lines.append(f"   - Warning: {w}")
    if body.get("notApplied"):
        lines += ["", "## Possible, not applied", ""]
        lines += [f"- {n['rule']}: {n['why']} (`{n['gridCitation']}`)" for n in body["notApplied"]]
    lines += [
        "",
        "## Facts",
        "",
        "| Fact | Value | Page | Check | Confidence | Quote |",
        "|---|---|---|---|---|---|",
    ]
    for name, f in body["facts"].items():
        value = "Not found" if f["value"] is None else str(f["value"])
        quote = (f["quote"] or "").replace("|", "\\|")
        lines.append(
            f"| {name} | {value} | {f['page'] or '—'} | {f['verification']} | {f['confidence']} | {quote} |"
        )
    meta = body["meta"]
    lines += [
        "",
        f"_Extractor: {meta.get('extractor')}; OCR: {meta.get('ocr')}; switches: {meta.get('switches')}._",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rater")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="analyse one policy PDF")
    run.add_argument("pdf", type=Path)
    run.add_argument("--out", type=Path, required=True, help="output path without extension")
    args = parser.parse_args(argv)

    result = run_pipeline(args.pdf.read_bytes(), args.pdf.name, build_deps())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".json").write_text(
        json.dumps(json.loads(result.to_json()), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    args.out.with_suffix(".md").write_text(trace_markdown(result, args.pdf.name))
    print(f"{args.pdf.name}: {result.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
