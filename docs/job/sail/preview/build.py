#!/usr/bin/env python3
"""Build static HTML previews for numbered markdown packs."""

from __future__ import annotations

import html
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "preview"

STYLE = """
:root {
  --ink: #1a1a1a;
  --muted: #5c5c5c;
  --line: #e6e2da;
  --bg: #f6f3ee;
  --paper: #fffcf7;
  --accent: #1a535c;
  --accent-soft: #e7f1f2;
}
* { box-sizing: border-box; }
html { font-size: 16px; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "IBM Plex Sans", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  line-height: 1.65;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.top {
  position: sticky; top: 0; z-index: 5;
  background: rgba(246,243,238,.92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
}
.top-inner, .wrap {
  max-width: 880px;
  margin: 0 auto;
  padding: 0 20px;
}
.top-inner {
  display: flex; gap: 10px; flex-wrap: wrap;
  align-items: center;
  min-height: 56px;
}
.brand { font-weight: 700; color: var(--accent); margin-right: 8px; }
.top a.nav {
  padding: 4px 10px;
  border-radius: 999px;
  color: var(--muted);
  font-size: 13px;
}
.top a.nav.active, .top a.nav:hover {
  background: var(--accent-soft);
  color: var(--accent);
  text-decoration: none;
}
.wrap { padding: 28px 20px 64px; }
.paper {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 36px 40px 48px;
  box-shadow: 0 12px 40px rgba(26,83,92,.06);
}
.kicker {
  font-size: 12px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 8px;
}
h1 { font-size: 28px; line-height: 1.25; margin: 0 0 16px; }
h2 { font-size: 20px; margin: 32px 0 12px; padding-top: 8px; border-top: 1px solid var(--line); }
h3 { font-size: 16px; margin: 24px 0 8px; }
p, li { font-size: 15px; }
blockquote {
  margin: 12px 0;
  padding: 8px 14px;
  border-left: 3px solid var(--accent);
  background: var(--accent-soft);
  color: #234;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  margin: 12px 0 20px;
}
th, td {
  border: 1px solid var(--line);
  padding: 8px 10px;
  vertical-align: top;
  text-align: left;
}
th { background: #f3efe7; }
code {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: .92em;
  background: #efeae2;
  padding: 1px 5px;
  border-radius: 4px;
}
hr { border: 0; border-top: 1px solid var(--line); margin: 24px 0; }
.cards { display: grid; gap: 14px; }
@media (min-width: 720px) { .cards { grid-template-columns: 1fr 1fr; } }
.card {
  display: block;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 18px 18px 16px;
  color: inherit;
}
.card:hover { border-color: var(--accent); text-decoration: none; }
.num { font-size: 12px; color: var(--accent); font-weight: 700; }
.card h2 { border: 0; margin: 6px 0 8px; font-size: 18px; padding: 0; }
.note { color: var(--muted); font-size: 14px; }
footer { margin-top: 20px; color: var(--muted); font-size: 13px; }
@media print {
  .top { display: none; }
  body { background: #fff; }
  .paper { box-shadow: none; border: 0; padding: 0; }
}
"""

NAV = [
    ("index.html", "目录"),
    ("001-岗位调研.html", "001 调研"),
    ("002-改后简历.html", "002 简历"),
    ("003-面试准备.html", "003 面试"),
]


def md_to_html(text: str) -> str:
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    )


def wrap(title: str, body: str, active: str) -> str:
    nav = []
    for href, label in NAV:
        cls = "nav active" if href == active else "nav"
        nav.append(f'<a class="{cls}" href="{html.escape(href)}">{html.escape(label)}</a>')
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="top"><div class="top-inner">
    <span class="brand">Sail · AI Agent</span>
    {''.join(nav)}
  </div></header>
  <main class="wrap"><article class="paper">
    <p class="kicker">get-job preview</p>
    {body}
  </article>
  <footer>编号从 001 递增。Markdown 源文件在上一级目录，本页仅供预览。</footer>
  </main>
</body>
</html>
"""


def write(name: str, title: str, body: str) -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    (PREVIEW / name).write_text(wrap(title, body, name), encoding="utf-8")


def main() -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    (PREVIEW / "styles.css").write_text(STYLE.strip() + "\n", encoding="utf-8")

    research = md_to_html((ROOT / "001-岗位调研.md").read_text(encoding="utf-8"))
    write("001-岗位调研.html", "001 岗位调研 · Sail", research)

    resume = md_to_html((ROOT / "002-改后简历.md").read_text(encoding="utf-8"))
    write("002-改后简历.html", "002 改后简历 · Sail", resume)

    interview_parts = []
    for path in sorted((ROOT / "003-面试准备").glob("*.md")):
        interview_parts.append(f'<h1 id="{html.escape(path.stem)}">{html.escape(path.stem)}</h1>')
        interview_parts.append(md_to_html(path.read_text(encoding="utf-8")))
    toc = """
    <p class="note">面试准备合集。也可单独打开：
      <a href="003-00-总览.html">00 总览</a> ·
      <a href="003-01-简历bullet逐条深挖.html">01 深挖</a> ·
      <a href="003-02-表达状态与自我介绍.html">02 表达</a> ·
      <a href="003-03-项目深挖技术面.html">03 技术面</a> ·
      <a href="003-99-面后复盘题库.html">99 复盘</a>
    </p>
    """
    write("003-面试准备.html", "003 面试准备 · Sail", toc + "\n".join(interview_parts))

    for path in sorted((ROOT / "003-面试准备").glob("*.md")):
        name = f"003-{path.name.replace('.md', '.html')}"
        write(name, f"003 {path.stem} · Sail", md_to_html(path.read_text(encoding="utf-8")))

    index_body = """
    <h1>Sail · AI Agent 应用</h1>
    <p class="note">按 get-job 三段链路编号。打开 HTML 即可预览，打印简历页可用浏览器「打印」。</p>
    <div class="cards">
      <a class="card" href="001-岗位调研.html"><div class="num">001</div><h2>岗位调研</h2><p>靶心、JD 取舍、轮次置信度、缺口。</p></a>
      <a class="card" href="002-改后简历.html"><div class="num">002</div><h2>改后简历</h2><p>对外成稿。docx 在上一级目录。</p></a>
      <a class="card" href="003-面试准备.html"><div class="num">003</div><h2>面试准备</h2><p>总览、逐条深挖、自我介绍、技术面、复盘。</p></a>
    </div>
    """
    (PREVIEW / "index.html").write_text(wrap("Sail 求职预览", index_body, "index.html"), encoding="utf-8")
    print(f"wrote {PREVIEW}")


if __name__ == "__main__":
    main()
