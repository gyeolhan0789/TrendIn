#!/usr/bin/env python
"""Score saved concept-linking experiments against the versioned gold set.

Example:
  python scripts/concept-quality-eval.py \
    --predictions artifacts/concept-quality-predictions.jsonl \
    --output artifacts/concept-quality-report.json

The command performs no DB access and no LLM calls. Token prices are explicit inputs because
the GMS model tariff is deployment policy, not a constant owned by this repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.concept.evaluation import (  # noqa: E402
    DEFAULT_KS,
    evaluate,
    load_gold,
    load_predictions,
)

DEFAULT_GOLD = ROOT / "spark" / "tests" / "fixtures" / "concept" / "quality-gold-v1.jsonl"


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--top-k", type=int, nargs="+", default=list(DEFAULT_KS))
    parser.add_argument("--input-usd-per-million", type=float, default=0.0)
    parser.add_argument("--output-usd-per-million", type=float, default=0.0)
    parser.add_argument("--output", type=Path, help="write JSON report here; stdout is always used")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate and summarize the gold set without requiring predictions",
    )
    args = parser.parse_args(argv)
    try:
        gold = load_gold(args.gold)
        if args.validate_only:
            payload = evaluate_gold(gold)
        else:
            if args.predictions is None:
                parser.error("--predictions is required unless --validate-only is used")
            predictions = load_predictions(args.predictions)
            payload = evaluate(
                gold,
                predictions,
                ks=tuple(args.top_k),
                input_usd_per_million=args.input_usd_per_million,
                output_usd_per_million=args.output_usd_per_million,
            )
    except ValueError as error:
        parser.error(str(error))
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def evaluate_gold(gold) -> dict:
    from collections import Counter

    return {
        "valid": True,
        "cases": len(gold),
        "by_action": dict(sorted(Counter(case.expected_action for case in gold).items())),
        "by_language": dict(sorted(Counter(case.language for case in gold).items())),
        "by_category": dict(sorted(Counter(case.category for case in gold).items())),
        "by_difficulty": dict(sorted(Counter(case.difficulty for case in gold).items())),
    }


if __name__ == "__main__":
    raise SystemExit(main())
