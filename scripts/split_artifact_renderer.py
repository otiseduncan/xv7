from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / "public/app/artifact-renderer.js"
helper_path = ROOT / "public/app/artifact-renderer-utils.js"
source = source_path.read_text(encoding="utf-8")
if "artifact-renderer-utils.js" in source:
    raise SystemExit(0)
marker = "export function appendSiteBundleCard"
index = source.find(marker)
if index < 0:
    raise SystemExit("marker not found")
helper_source = source[:index].rstrip() + "\n"
remaining_source = source[index:]
helper_path.write_text(helper_source, encoding="utf-8")
names = []
for line in helper_source.splitlines():
    stripped = line.strip()
    if stripped.startswith("export function "):
        name = stripped.removeprefix("export function ").split("(", 1)[0].strip()
        if name:
            names.append(name)
if not names:
    raise SystemExit("no helper names found")
header = "import {\n" + "\n".join(f"  {name}," for name in names) + "\n} from './artifact-renderer-utils.js';\n\n"
header += "export {\n" + "\n".join(f"  {name}," for name in names) + "\n};\n\n"
source_path.write_text(header + remaining_source, encoding="utf-8")
print("artifact renderer split complete")
