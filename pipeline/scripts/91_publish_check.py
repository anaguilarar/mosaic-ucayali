"""Step 91 - final check before any push/upload: file sizes, SITE (GitHub) vs Hugging Face split,
GitHub's 100 MB limit, withheld/internal patterns and a secret scan. Read-only; exits 1 on a
blocker so run_all stops before publishing by hand.

Usage:  python scripts/91_publish_check.py [--area pilot|full]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

SECRET_PAT = re.compile(r"(EARTHDATA_PASSWORD\s*=\s*\S|machine\s+urs\.earthdata|api[_-]?key\s*[:=]\s*['\"]?\w{8,})", re.I)
NEVER_PUBLISH = ["raisg", "indigenous_territor", "nus_crop", "MFL-2026-055", "netrc"]


def parse_site_list() -> list[str]:
    cfg = (common.REPO / "site" / "js" / "config.js").read_text(encoding="utf-8")
    m = re.search(r"export const SITE = \[(.*?)\]", cfg, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def main():
    common.setup("91_publish_check")
    site = parse_site_list()
    on_site = lambda rel: any(rel == s or (s.endswith("/") and rel.startswith(s)) for s in site)
    data = common.DATA
    bad = 0
    rows = []
    for p in sorted(data.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(data).as_posix()
        mb = p.stat().st_size / 1e6
        dest = "GitHub (SITE)" if on_site(rel) else "Hugging Face"
        flag = ""
        if dest.startswith("GitHub") and mb > 95:
            flag = "OVER GitHub 100 MB limit"; bad += 1
        if any(k in rel.lower() for k in NEVER_PUBLISH):
            flag = "WITHHELD PATTERN - must not be published"; bad += 1
        rows.append((rel, mb, dest, flag))
    w = max((len(r[0]) for r in rows), default=20)
    print(f"{'file'.ljust(w)}  {'MB':>8}  destination        flag")
    for rel, mb, dest, flag in rows:
        print(f"{rel.ljust(w)}  {mb:8.1f}  {dest:<18} {flag}")
    gh = sum(r[1] for r in rows if r[2].startswith("GitHub"))
    hf = sum(r[1] for r in rows if not r[2].startswith("GitHub"))
    print(f"\ntotals: GitHub (SITE) {gh:.1f} MB · Hugging Face {hf:.1f} MB · {len(rows)} files")

    # secret scan over text files in the repo (not data/)
    for p in common.REPO.rglob("*"):
        if p.is_dir() or p.suffix not in {".py", ".js", ".json", ".md", ".toml", ".yml", ".ps1", ".sh", ".html", ".css"}:
            continue
        if ".git" in p.parts or "node_modules" in p.parts:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in SECRET_PAT.finditer(txt):
            frag = m.group(0)[:40]
            line = txt[txt.rfind("\n", 0, m.start()) + 1:txt.find("\n", m.end())]
            if "<" in line or p.name == "91_publish_check.py":
                continue       # documentation template with <placeholders>, or this scanner itself
            print(f"SECRET-LIKE TEXT in {p}: {frag!r}")
            bad += 1
    if bad:
        print(f"\n{bad} blocker(s) - fix before publishing")
        sys.exit(1)
    print("\npublish check passed")


if __name__ == "__main__":
    main()
