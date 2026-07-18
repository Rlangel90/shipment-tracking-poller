"""Pre-commit hook: block commits that look like they contain real
credentials.

This is a generic, pattern-based guard (private key blocks, AWS-style access
key IDs, obviously-hardcoded API keys/secrets/tokens/passwords, and the
literal .env file) - not a comprehensive secrets scanner. It's meant to catch
the common accidental-commit cases a solo project is actually at risk of.
"""

import re
import sys

ENV_FILENAME_BLOCK = re.compile(r"(^|/)\.env$")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----")
AWS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

CODE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password)\w*\s*[:=]\s*[\"']([^\"']{8,})[\"']"
)
ENV_ASSIGNMENT_RE = re.compile(
    r"(?im)^([A-Z_]*?(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD)[A-Z_]*)\s*=\s*(\S{8,})\s*$"
)

PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "changeme",
    "your-",
    "xxxx",
    "<",
    "todo",
    "insert-",
    "replace",
    "fake",
    "dummy",
)


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def scan_text(text: str) -> list[str]:
    """Content-only checks, independent of where the text came from."""
    problems = []

    if PRIVATE_KEY_RE.search(text):
        problems.append("contains what looks like a private key")

    if AWS_KEY_RE.search(text):
        problems.append("contains what looks like an AWS access key ID")

    for match in CODE_ASSIGNMENT_RE.finditer(text):
        if not _looks_like_placeholder(match.group(2)):
            problems.append(f"possible hardcoded credential near '{match.group(1)}'")

    for match in ENV_ASSIGNMENT_RE.finditer(text):
        name, value = match.group(1), match.group(2)
        if not _looks_like_placeholder(value) and not _looks_like_placeholder(name):
            problems.append(f"possible hardcoded credential in '{name}'")

    return problems


def scan_file(path: str) -> list[str]:
    if ENV_FILENAME_BLOCK.search(path.replace("\\", "/")):
        return [f"{path}: refusing to commit a .env file"]

    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return []

    return [f"{path}: {problem}" for problem in scan_text(text)]


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    all_problems = []
    for path in paths:
        all_problems.extend(scan_file(path))

    if all_problems:
        print("secrets check failed:")
        for problem in all_problems:
            print(f"  - {problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
