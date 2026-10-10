"""Scan tracked + untracked (not ignored) files for things that must never be pushed.

API keys, private keys, committed .env files, symlinks. Exit 1 on findings.
Usage: python scripts/check_safety.py  (part of scripts/check.sh and CI)
"""
import re
import subprocess
import sys
from pathlib import Path

# (name, pattern, allow-list pattern for placeholders)
RULES = [
    ("Anthropic key", r"\bsk-ant-[A-Za-z0-9_-]{10,}", None),
    ("OpenAI key", r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}", None),
    ("Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b", None),
    ("Gradium key", r"\bgd_[A-Za-z0-9]{20,}", None),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}", None),
    ("AWS access key", r"\bAKIA[0-9A-Z]{16}\b", None),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}", None),
    ("Private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", None),
    ("Stripe key", r"\b[sr]k_(live|test)_[A-Za-z0-9]{16,}", None),
    ("Hugging Face token", r"\bhf_[A-Za-z0-9]{30,}", None),
    ("JWT", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", None),
    (
        "Database URL with password",
        r"\b(postgres(ql)?|mysql|mongodb(\+srv)?|rediss?|amqps?)://[^:\s/@]+:[^@\s]{6,}@",
        r":(password|pass|secret|changeme|<[^>]+>|\$\{?[A-Z_]+\}?|\*+)@",
    ),
]
RULES = [(n, re.compile(p), re.compile(a, re.I) if a else None) for n, p, a in RULES]
SKIP_CONTENT = {"scripts/check_safety.py"}


def is_env_file(path):
    if path.endswith(".env.example"):
        return False
    return bool(re.search(r"(^|/)\.env(\.|$)", path) or path.endswith(".env"))


def scan_text(path, text):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for name, pattern, allow in RULES:
            for m in pattern.finditer(line):
                if allow and allow.search(m.group(0)):
                    continue
                out.append(f"{path}:{i}: {name}: {m.group(0)[:8]}…")
    return out


def main():
    listing = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             check=True, capture_output=True).stdout.decode()
    files = [f for f in listing.split("\0") if f]
    findings = []
    for f in files:
        p = Path(f)
        if p.is_symlink():
            findings.append(f"{f}: is a symlink (breaks on Windows; use a real file)")
            continue
        if not p.exists():
            continue  # deleted in working tree
        if is_env_file(f):
            findings.append(f"{f}: env file must never be committed")
            continue
        if f in SKIP_CONTENT or not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        data = p.read_bytes()
        if b"\0" in data:
            continue  # binary
        findings += scan_text(f, data.decode("utf-8", errors="replace"))
    if findings:
        print("✖ Safety check found problems. Remove the secret (and rotate it if it was ever pushed), never bypass:\n", file=sys.stderr)
        for x in findings:
            print(f"  - {x}", file=sys.stderr)
        sys.exit(1)
    print(f"✔ Safety check: {len(files)} files clean.")


if __name__ == "__main__":
    main()
