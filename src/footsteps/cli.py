"""Command line entry point: one subcommand per pipeline stage."""

import argparse
import sys
from pathlib import Path

from footsteps import export, ingest, tasks

# Stage order follows the pipeline in docs/ARCHITECTURE.md.
STAGES = {
    "ingest": "normalize runs and compute step facts",
    "tasks": "self-test the custom demo tasks",
    "runner": "run planted behaviours through Claude Code",
    "features": "compute sequence features from step facts",
    "segment": "cluster steps into behaviours",
    "label": "name behaviours with the LLM wrapper",
    "evaluate": "compute the pre-registered tests",
    "export": "write results/site.json",
}


# Stages that are built; the rest report that they are not implemented yet.
IMPLEMENTED = {"ingest": ingest.run, "export": export.run, "tasks": tasks.run}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="footsteps", description="Run one stage of the footsteps pipeline."
    )
    subparsers = parser.add_subparsers(dest="stage", metavar="<stage>", required=True)
    for name, summary in STAGES.items():
        stage_parser = subparsers.add_parser(name, help=summary, description=summary)
        if name == "ingest":
            stage_parser.add_argument(
                "--pilot",
                nargs="+",
                type=Path,
                metavar="TRANSCRIPT",
                help="reduce Claude Code stream-json transcripts instead of downloading the public data",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.stage == "ingest" and args.pilot:
        ingest.run_pilot(args.pilot)
        return 0
    if args.stage in IMPLEMENTED:
        IMPLEMENTED[args.stage]()
        return 0
    print(f"footsteps {args.stage}: not implemented yet", file=sys.stderr)
    return 1
