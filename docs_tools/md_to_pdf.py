import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

STYLE = """
body { font-family: Segoe UI, Arial, sans-serif; font-size: 10.5pt; color: #111; margin: 0; line-height: 1.45; }
h1 { font-size: 20pt; margin: 0 0 10px; }
h2 { font-size: 14pt; margin: 22px 0 8px; border-bottom: 1px solid #ccc; padding-bottom: 3px; }
h3 { font-size: 11.5pt; margin: 16px 0 6px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
h1, h2, h3 { break-after: avoid; }
th, td { border: 1px solid #bbb; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #eee; }
td.bar { color: #2b5797; white-space: nowrap; text-align: center; }
code { font-family: Consolas, monospace; font-size: 9.5pt; background: #f2f2f2; padding: 0 2px; }
ul { margin: 6px 0; padding-left: 20px; }
@page { size: A4 landscape; margin: 14mm; }
"""


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', text)
    return text


def cells(row):
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def render_table(rows):
    head = cells(rows[0])
    out = ["<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"]
    for row in rows[2:]:
        tds = []
        for cell in cells(row):
            css = ' class="bar"' if cell and set(cell) <= {"\u2588"} else ""
            tds.append(f"<td{css}>{inline(cell)}</td>")
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def render(markdown):
    lines = markdown.splitlines()
    out = []
    paragraph = []
    items = []
    index = 0

    def flush():
        if paragraph:
            out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        heading = re.match(r"(#{1,6})\s+(.*)", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif stripped.startswith("|"):
            flush()
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index])
                index += 1
            out.append(render_table(rows))
            continue
        elif stripped.startswith("- "):
            if paragraph:
                flush()
            items.append(stripped[2:])
        elif line.startswith("  ") and items and stripped:
            items[-1] += " " + stripped
        elif not stripped:
            flush()
        else:
            if items:
                flush()
            paragraph.append(stripped)
        index += 1
    flush()
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Render a Markdown file to PDF through headless Edge.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    body = render(args.source.read_text(encoding="utf-8"))
    title = html.escape(args.source.stem)
    page = f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title><style>{STYLE}</style></head><body>{body}</body></html>"

    with tempfile.TemporaryDirectory() as scratch:
        page_path = Path(scratch) / "page.html"
        page_path.write_text(page, encoding="utf-8")
        subprocess.run(
            [str(EDGE), "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={scratch}", f"--print-to-pdf={args.output.resolve()}", page_path.as_uri()],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    print(f"wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
