#!/usr/bin/env python3
"""Render Nanobot config from a JSON template and environment variables."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ENV_REF_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
EXACT_ENV_REF_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def _replace_env(match: re.Match[str]) -> str:
    name = match.group(1)
    value = os.environ.get(name)
    if value is None or value == "":
        raise ValueError(f"required environment variable {name!r} is not set")
    return value


def _render_value(value: Any) -> Any:
    if isinstance(value, str):
        exact_match = EXACT_ENV_REF_PATTERN.fullmatch(value)
        if exact_match:
            return _replace_env(exact_match)
        return ENV_REF_PATTERN.sub(_replace_env, value)
    if isinstance(value, list):
        return [_render_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item) for key, item in value.items()}
    return value


def render_template(template_path: Path) -> str:
    with template_path.open(encoding="utf-8") as template_file:
        parsed = json.load(template_file)
    rendered = _render_value(parsed)
    return json.dumps(rendered, indent=2, ensure_ascii=False) + "\n"


def write_config(output_path: Path, content: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f".{output_path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("/app/config.template.json"),
        help="Path to config template JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/home/nanobot/.nanobot/config.json"),
        help="Path to rendered Nanobot config JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rendered = render_template(args.template)
        write_config(args.output, rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"render_config: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
