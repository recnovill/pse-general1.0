"""Command-line entry point for the PSE local workflow."""
import argparse
import json
from pathlib import Path
import sys

from . import engine


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m pse", description="PSE General: controles locales de investigación asistida")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("plan"); p.add_argument("--out", required=True)
    p = sub.add_parser("branch"); p.add_argument("case"); p.add_argument("branch_id")
    for name in ("run", "status", "verify"):
        p = sub.add_parser(name); p.add_argument("case")
    p = sub.add_parser("close"); p.add_argument("case"); p.add_argument("--decision", required=True)
    p = sub.add_parser("propose"); p.add_argument("case"); p.add_argument("--draft", required=True)
    p = sub.add_parser("review"); p.add_argument("case"); p.add_argument("--review", required=True)
    p = sub.add_parser("review-packet"); p.add_argument("case"); p.add_argument("proposal_id")
    p = sub.add_parser("tip"); p.add_argument("case"); p.add_argument("tip")
    p = sub.add_parser("revise"); p.add_argument("case"); p.add_argument("plan")
    p = sub.add_parser("report"); p.add_argument("case"); p.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = engine.init_case(args.plan, args.out)
        elif args.command == "branch":
            result = engine.branch_view(args.case, args.branch_id)
        elif args.command == "run":
            result = engine.run_case(args.case)
        elif args.command == "status":
            result = engine.status(args.case)
        elif args.command == "verify":
            result = engine.verify_case(args.case)
        elif args.command == "close":
            result = engine.close_case(args.case, engine.read_json(args.decision))
        elif args.command == "propose":
            result = engine.propose_case(args.case, engine.read_json(args.draft))
        elif args.command == "review":
            result = engine.review_case(args.case, engine.read_json(args.review))
        elif args.command == "review-packet":
            result = engine.review_packet(args.case, args.proposal_id)
        elif args.command == "tip":
            result = engine.add_tip(args.case, engine.read_json(args.tip))
        elif args.command == "revise":
            result = engine.revise_case(args.case, args.plan)
        else:
            report = engine.render_report(args.case)
            target = Path(args.out)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as stream:
                stream.write(report)
            result = {"report_written": True, "path": str(target)}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (engine.EngineError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
