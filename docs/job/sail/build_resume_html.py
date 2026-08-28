#!/usr/bin/env python3
"""Generate HTML preview for numbered resume files: NNN-改后简历.md"""

from __future__ import annotations

import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
RESUME_RE = re.compile(r"^(\d{3})-改后简历\.md$")

CSS = """
:root { --ink:#1a1a1a; --muted:#5c5c5c; --line:#e6e2da; --accent:#1a535c; --paper:#fffcf7; }
* { box-sizing: border-box; }
body { margin:0; background:#f6f3ee; color:var(--ink);
  font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif; line-height:1.65; }
a { color:var(--accent); }
.sheet { max-width:800px; margin:24px auto 64px; background:var(--paper);
  border:1px solid var(--line); border-radius:16px; padding:40px 44px 48px; }
.num { font-size:12px; letter-spacing:.14em; color:var(--accent); }
h1 { font-size:26px; margin:6px 0 16px; }
h2 { font-size:18px; margin:28px 0 10px; padding-top:10px; border-top:1px solid var(--line); }
p, li { font-size:15px; }
blockquote { margin:12px 0; padding:8px 14px; border-left:3px solid var(--accent); background:#e7f1f2; }
table { width:100%; border-collapse:collapse; font-size:14px; margin:12px 0; }
th, td { border:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; }
th { background:#f3efe7; }
@media print { body { background:#fff; } .sheet { border:0; margin:0; padding:0; } }
"""


def main() -> None:
    files = sorted(p for p in ROOT.glob("*.md") if RESUME_RE.match(p.name))
    if not files:
        raise SystemExit("no numbered resume markdown found")
    for path in files:
        num = RESUME_RE.match(path.name).group(1)
        body = markdown.markdown(
            path.read_text(encoding="utf-8"),
            extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
        )
        out = ROOT / f"{num}-改后简历.html"
        out.write_text(
            f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(num)} 改后简历 · Sail</title>
  <style>{CSS}</style>
</head>
<body>
  <article class="sheet">
    <div class="num">{html.escape(num)}</div>
    {body}
  </article>
</body>
</html>
""",
            encoding="utf-8",
        )
        print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
