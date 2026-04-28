#!/usr/bin/env python3
"""
Generate a fresh .env from .env.example with cryptographically-strong
INTERNAL_API_KEY and JWT_SECRET values.

Usage:
    python scripts/init_env.py            # safe — refuses to overwrite existing .env
    python scripts/init_env.py --force    # overwrite existing .env
    python scripts/init_env.py --print    # show what would be written, don't touch disk

Cross-platform: pure Python, no sed/awk/PowerShell.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

# Force UTF-8 stdout so the printed .env preview + status lines render
# correctly on Windows consoles (cp1252 default).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env.example"
ENV = ROOT / ".env"

# Keys we (re)generate. Anything else is left at the .env.example default.
GENERATED_KEYS = {
    "INTERNAL_API_KEY": lambda: secrets.token_hex(32),       # 64 hex chars
    "JWT_SECRET":       lambda: secrets.token_urlsafe(48),    # ~64 url-safe chars
}


def render(template_lines: list[str], values: dict[str, str]) -> list[str]:
    """Return the template with KEY=value lines replaced by KEY=values[KEY]."""
    out: list[str] = []
    for line in template_lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in values:
            # preserve any leading whitespace from the template
            indent = line[: len(line) - len(stripped)]
            out.append(f"{indent}{key}={values[key]}\n")
        else:
            out.append(line)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing .env (default: refuse)")
    p.add_argument("--print", dest="print_only", action="store_true",
                   help="Print what would be written, don't touch disk")
    args = p.parse_args()

    if not ENV_EXAMPLE.exists():
        print(f"ERROR: template not found: {ENV_EXAMPLE}", file=sys.stderr)
        return 1

    if ENV.exists() and not args.force and not args.print_only:
        print(f"ERROR: {ENV} already exists. Pass --force to overwrite.", file=sys.stderr)
        return 1

    values = {key: gen() for key, gen in GENERATED_KEYS.items()}
    template = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines(keepends=True)
    rendered = "".join(render(template, values))

    if args.print_only:
        print(rendered, end="")
        return 0

    ENV.write_text(rendered, encoding="utf-8")
    print(f"OK  Wrote {ENV}")
    for key in GENERATED_KEYS:
        masked = values[key][:6] + "…" + values[key][-4:]
        print(f"    {key} = {masked}  ({len(values[key])} chars)")
    print()
    print("Other keys (POSTGRES_*, MINIO_*, GRAFANA_PASSWORD, SLACK_WEBHOOK_URL)")
    print("were left at .env.example defaults — edit .env if you want to change them.")
    print()
    print("Next:  docker compose up -d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
