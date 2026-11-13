import json
from pathlib import Path

transcript = Path(
    r"C:\Users\NewUser\.cursor\projects\c-projects-copytrust-testdeploydocker"
    r"\agent-transcripts\2e388c6f-1b36-4f09-a249-1a9d9fe24e4b"
    r"\2e388c6f-1b36-4f09-a249-1a9d9fe24e4b.jsonl"
)
target = Path(__file__).resolve().parents[1] / "architecture" / "cicd.md"

for line in transcript.read_text(encoding="utf-8").splitlines():
    if "cicd.md" not in line or '"Write"' not in line:
        continue
    obj = json.loads(line)
    for block in obj.get("message", {}).get("content", []):
        if block.get("name") != "Write":
            continue
        inp = block.get("input", {})
        if not str(inp.get("path", "")).endswith("cicd.md"):
            continue
        text = inp["contents"]
        target.write_text(text, encoding="utf-8")
        print(f"restored {len(text)} chars to {target}")
        print("ok:", "## \u0421\u0443\u0442\u044c" in text)
        raise SystemExit(0)

raise SystemExit("Write payload not found in transcript")
