"""Command line entry point: one subcommand per pipeline stage."""

import argparse
import sys

from footsteps import export, ingest

# Stage order follows the pipeline in docs/ARCHITECTURE.md.
STAGES = {
    "ingest": "normalize runs and compute step facts",
    "runner": "run planted behaviours through Claude Code",
    "features": "compute sequence features from step facts",
    "segment": "cluster steps into behaviours",
    "label": "name behaviours with the LLM wrapper",
    "evaluate": "compute the pre-registered tests",
    "export": "write results/site.json",
}


# Stages that are built; the rest report that they are not implemented yet.
IMPLEMENTED = {"ingest": ingest.run, "export": export.run}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="footsteps", description="Run one stage of the footsteps pipeline."
    )
    subparsers = parser.add_subparsers(dest="stage", metavar="<stage>", required=True)
    for name, summary in STAGES.items():
        subparsers.add_parser(name, help=summary, description=summary)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.stage in IMPLEMENTED:
        IMPLEMENTED[args.stage]()
        return 0
    print(f"footsteps {args.stage}: not implemented yet", file=sys.stderr)
    return 1
