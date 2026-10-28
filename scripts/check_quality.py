"""Enforce static checks without grandfathering new violations in legacy files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts/quality-baseline.json"


def run(args: list[str]) -> str:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def relative(path: str) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def fingerprint(path: str, rule: str, message: str, line: int) -> str:
    source = (ROOT / path).read_text(encoding="utf-8").splitlines()
    return json.dumps([path, rule, message, source[line - 1].strip()])


def lint() -> dict[str, int]:
    found: Counter[str] = Counter()
    for item in json.loads(
        run([sys.executable, "-m", "ruff", "check", ".", "--output-format=json"])
    ):
        path = relative(item["filename"])
        if item["code"] is None or item["code"].startswith("E9"):
            raise RuntimeError(f"Python syntax error: {path}: {item['message']}")
        found[
            fingerprint(path, item["code"], item["message"], item["location"]["row"])
        ] += 1
    eslint = shutil.which("eslint", path=str(ROOT / "node_modules/.bin"))
    if not eslint:
        raise RuntimeError("ESLint missing; run npm ci")
    for item in json.loads(run([eslint, "frontend", "--format=json"])):
        path = relative(item["filePath"])
        for message in item["messages"]:
            if message.get("fatal"):
                raise RuntimeError(
                    f"TypeScript parse error: {path}: {message['message']}"
                )
            found[
                fingerprint(
                    path, message["ruleId"], message["message"], message["line"]
                )
            ] += 1
    return dict(sorted(found.items()))


def formatting() -> dict[str, str]:
    paths = run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            ".",
            "--check",
            "--output-format=concise",
        ]
    )
    files = [
        line.removeprefix("Would reformat: ")
        for line in paths.splitlines()
        if line.startswith("Would reformat: ")
    ]
    prettier = shutil.which("prettier", path=str(ROOT / "node_modules/.bin"))
    if not prettier:
        raise RuntimeError("Prettier missing; run npm ci")
    files += run([prettier, "frontend", "--list-different"]).splitlines()
    return {
        path: hashlib.sha256(
            (ROOT / path).read_text(encoding="utf-8").encode()
        ).hexdigest()
        for path in sorted(files)
    }


def regressions(current: dict, baseline: dict, mode: str) -> list[str]:
    if mode == "lint":
        return [key for key, count in current.items() if count > baseline.get(key, 0)]
    return [path for path, digest in current.items() if baseline.get(path) != digest]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["lint", "format"])
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Explicit reviewed migration only; never run in CI",
    )
    args = parser.parse_args()
    current = lint() if args.mode == "lint" else formatting()
    baseline = (
        json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    )
    if args.write_baseline:
        baseline[args.mode] = current
        BASELINE.write_text(
            json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"Recorded {len(current)} legacy {args.mode} entries; review the baseline diff."
        )
        return 0
    if args.mode not in baseline:
        raise RuntimeError("Missing reviewed quality baseline")
    new = regressions(current, baseline[args.mode], args.mode)
    for item in new:
        print(item)
    print(f"{args.mode}: {len(current)} legacy entries remain; {len(new)} regressions")
    return bool(new)


if __name__ == "__main__":
    raise SystemExit(main())
