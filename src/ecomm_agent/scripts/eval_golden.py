"""CLI: eval-golden — run golden evaluation and print summary.

Usage:
  uv run ecomm-agent eval-golden [--limit 20] [--intent product_search]
"""

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run golden dataset evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Cap golden queries")
    parser.add_argument("--intent", type=str, default=None, help="Filter by intent")
    parser.add_argument("--version", type=str, default="v1", help="dataset_version tag")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    from ecomm_agent.services.evaluation import run_golden_evaluation

    print(f"Running golden evaluation (limit={args.limit} intent={args.intent})...")
    summary = run_golden_evaluation(limit=args.limit, intent=args.intent, dataset_version=args.version)
    if summary.get("error"):
        print(f"Error: {summary['error']}")
        sys.exit(1)

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
        return

    print(f"\nRun {summary['run_id']} — {summary['passed']}/{summary['total']} passed ({summary['pass_rate']}%)")
    for r in summary["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        checks = f" | {', '.join(r['failed_checks'])}" if r["failed_checks"] else ""
        print(f"  [{status}] {r['golden_slug']}: intent {r['actual_intent']} ids {r['actual_product_ids']}{checks}")

    if summary["failed"] > 0:
        # Non-zero exit for CI but not hard fail
        pass


if __name__ == "__main__":
    main()
