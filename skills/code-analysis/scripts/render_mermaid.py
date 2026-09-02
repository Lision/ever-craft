#!/usr/bin/env python3
"""Extract Mermaid blocks from a Markdown report and render SVG assets."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


MERMAID_BLOCK = re.compile(
    r"^[ \t]*(?P<fence>`{3,})[ \t]*mermaid[^\r\n]*\r?\n"
    r"(?P<body>.*?)"
    r"\r?\n^[ \t]*(?P=fence)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render every Mermaid block in a Markdown report as SVG."
    )
    parser.add_argument("report", type=Path, help="Markdown report to render")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory; defaults to a unique code-analysis cache directory",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="Maximum time for each SVG render (default: 60)",
    )
    return parser.parse_args()


def extract_diagrams(markdown: str) -> list[str]:
    return [match.group("body").strip() + "\n" for match in MERMAID_BLOCK.finditer(markdown)]


def cache_root() -> Path:
    configured_root = os.environ.get("XDG_CACHE_HOME")
    if configured_root:
        return Path(configured_root).expanduser() / "code-analysis"
    return Path(tempfile.gettempdir()) / "code-analysis"


def create_output_dir(report: Path, requested: Path | None) -> Path:
    if requested is not None:
        output_dir = requested.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", report.stem).strip("-.") or "report"
    return Path(tempfile.mkdtemp(prefix=f"{safe_stem}-", dir=root)).resolve()


def mermaid_command() -> list[str]:
    executable = shutil.which("mmdc")
    if executable:
        return [executable]

    npx = shutil.which("npx")
    if npx:
        return [npx, "-y", "-p", "@mermaid-js/mermaid-cli", "mmdc"]

    raise RuntimeError(
        "Mermaid CLI is unavailable: install mmdc or make npx available for the fallback."
    )


def mermaid_environment() -> dict[str, str]:
    environment = os.environ.copy()
    if environment.get("PUPPETEER_EXECUTABLE_PATH"):
        return environment

    executable_names = (
        "chromium",
        "chromium-browser",
        "google-chrome-stable",
        "google-chrome",
        "chrome",
        "microsoft-edge",
    )
    executable_paths = [shutil.which(name) for name in executable_names]
    executable_paths.extend(
        [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    )
    for executable in executable_paths:
        if executable and Path(executable).is_file() and os.access(executable, os.X_OK):
            environment["PUPPETEER_EXECUTABLE_PATH"] = executable
            break
    return environment


def render(
    command: list[str], source: Path, destination: Path, timeout_seconds: float
) -> None:
    try:
        completed = subprocess.run(
            [*command, "-i", str(source), "-o", str(destination)],
            check=False,
            capture_output=True,
            env=mermaid_environment(),
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"Timed out after {timeout_seconds:g}s rendering "
            f"{source.name} as {destination.suffix}."
        ) from error
    if completed.returncode == 0 and destination.is_file() and destination.stat().st_size > 0:
        return

    details = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    raise RuntimeError(
        f"Failed to render {source.name} as {destination.suffix}:\n{details}"
    )


def markdown_destination(path: Path) -> str:
    return f"<{path}>"


def build_manifest(output_dir: Path, assets: list[tuple[Path, Path]]) -> str:
    lines = [
        "### Mermaid 图像产物",
        "",
        f"缓存目录：`{output_dir}`",
        "",
    ]
    for index, (source, svg) in enumerate(assets, start=1):
        lines.extend(
            [
                f"#### 图 {index}",
                "",
                f"![图 {index} SVG]({markdown_destination(svg)})",
                "",
                f"- SVG：[打开]({markdown_destination(svg)}) — `{svg}`",
                f"- Mermaid 源文件：[打开]({markdown_destination(source)}) — `{source}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if args.timeout_seconds <= 0:
        print("--timeout-seconds must be greater than zero", file=sys.stderr)
        return 2

    report = args.report.expanduser().resolve()
    if not report.is_file():
        print(f"Report does not exist: {report}", file=sys.stderr)
        return 2

    diagrams = extract_diagrams(report.read_text(encoding="utf-8"))
    if not diagrams:
        print(f"No Mermaid fenced blocks found in {report}", file=sys.stderr)
        return 2

    output_dir = create_output_dir(report, args.output_dir)
    try:
        command = mermaid_command()
        assets: list[tuple[Path, Path]] = []
        for index, diagram in enumerate(diagrams, start=1):
            source = output_dir / f"diagram-{index:02d}.mmd"
            svg = output_dir / f"diagram-{index:02d}.svg"
            source.write_text(diagram, encoding="utf-8")
            render(command, source, svg, args.timeout_seconds)
            assets.append((source, svg))

        manifest = output_dir / "manifest.md"
        manifest.write_text(build_manifest(output_dir, assets), encoding="utf-8")
    except RuntimeError as error:
        print(error, file=sys.stderr)
        print(f"Partial output directory: {output_dir}", file=sys.stderr)
        return 1

    print(f"Rendered {len(assets)} Mermaid diagram(s) as SVG.")
    print(f"Output directory: {output_dir}")
    print(f"Markdown manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
