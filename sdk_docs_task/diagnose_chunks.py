import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from chunk_document import recursive_chunk_text, structure_aware_chunk_markdown

PAGES_DIR = Path(__file__).resolve().parent / "pages"
CHUNKER = recursive_chunk_text if "--recursive" in sys.argv else structure_aware_chunk_markdown


def check_chunk(chunk):
    issues = []
    fence_count = chunk.count("```")
    if fence_count % 2 == 1:
        issues.append("ODD_FENCE_COUNT (fence split across boundary)")
    if "|" in chunk:
        lines = chunk.splitlines()
        table_lines = [l for l in lines if l.strip().startswith("|")]
        if table_lines and not any("---" in l for l in table_lines):
            issues.append("TABLE_ROWS_WITHOUT_SEPARATOR_ROW (header likely missing)")
    return issues


for md_file in sorted(PAGES_DIR.rglob("*.md")):
    text = md_file.read_text(encoding="utf-8")
    chunks = CHUNKER(text)
    print(f"\n===== {md_file.relative_to(PAGES_DIR)} : {len(chunks)} chunks =====")
    for i, c in enumerate(chunks):
        issues = check_chunk(c)
        flag = f"  <-- {issues}" if issues else ""
        print(f"  chunk {i}: {len(c)} chars{flag}")
        if issues:
            print("  ---- content ----")
            print("  " + c.replace("\n", "\n  "))
            print("  -----------------")
