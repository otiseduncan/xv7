from pathlib import Path
from collections import defaultdict

ROOT = Path(".").resolve()

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", "dist", "build", "coverage", "htmlcov", "test-results",
    "runtime", "generated-sites", ".next", ".turbo"
}

INCLUDE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".md", ".mjs", ".cjs", ".json"
}

CAPS = {
    ".py": 1000,
    ".js": 1500,
    ".jsx": 1500,
    ".ts": 1500,
    ".tsx": 1500,
    ".css": 1500,
    ".html": 1200,
    ".mjs": 1200,
    ".cjs": 1200,
    ".json": 1000,
    ".md": 1000,
}

def should_skip(path):
    return any(part in SKIP_DIRS for part in path.parts)

def count_lines(path):
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

files = []
folders = defaultdict(lambda: {"files": 0, "lines": 0, "leak": 0})

for path in ROOT.rglob("*"):
    if not path.is_file() or should_skip(path):
        continue

    ext = path.suffix.lower()
    if ext not in INCLUDE_EXTS:
        continue

    rel = path.relative_to(ROOT).as_posix()
    folder = rel.split("/")[0] if "/" in rel else "[root]"
    lines = count_lines(path)
    cap = CAPS.get(ext, 1000)
    leak = max(0, lines - cap)

    files.append((rel, folder, lines, cap, leak))
    folders[folder]["files"] += 1
    folders[folder]["lines"] += lines
    folders[folder]["leak"] += leak

print("\n=== FOLDER TOTALS ===")
for folder, data in sorted(folders.items(), key=lambda x: x[1]["lines"], reverse=True):
    print(f"{folder:<18} files {data['files']:>4}  lines {data['lines']:>8,}  leak {data['leak']:>7,}")

print("\n=== TOP LINE-POLICY LEAKS ===")
for i, row in enumerate(sorted(files, key=lambda x: x[4], reverse=True)[:30], 1):
    rel, folder, lines, cap, leak = row
    if leak <= 0:
        break
    print(f"{i:>2}. leak +{leak:>5}  lines {lines:>6} / cap {cap:<5}  {rel}")

print("\n=== FOLDER GRAPH ===")
max_lines = max((data["lines"] for data in folders.values()), default=1)

for folder, data in sorted(folders.items(), key=lambda x: x[1]["lines"], reverse=True):
    bar_len = max(1, round((data["lines"] / max_lines) * 50))
    bar = "#" * bar_len
    print(f"{data['lines']:>8,} | {bar:<50} | {folder}")
