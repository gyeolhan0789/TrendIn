"""Pure evaluation helpers for labeled concept-linking experiments.

The evaluator deliberately knows nothing about PostgreSQL, embeddings, or an LLM client.
Experiments write one JSONL prediction per gold case and this module scores those saved
artifacts.  That makes an expensive run reproducible without repeating network calls.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trendin.spark.concept.judge import CATEGORIES

GOLD_ACTIONS = frozenset({"LINK", "NEW", "EXCLUDE", "DEFER"})
PREDICTION_DECISIONS = GOLD_ACTIONS
DEFAULT_KS = (1, 3, 5, 10)


@dataclass(frozen=True, slots=True)
class GoldCase:
    case_id: str
    surface: str
    language: str
    category: str
    expected_action: str
    expected_concept: str | None
    english_name: str | None
    context: str | None
    difficulty: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class CandidatePrediction:
    name: str
    category: str | None = None


@dataclass(frozen=True, slots=True)
class Prediction:
    case_id: str
    experiment: str
    decision: str
    concept: str | None
    category: str | None
    candidates: tuple[CandidatePrediction, ...]
    elapsed_ms: float | None
    llm_calls: int
    input_tokens: int
    output_tokens: int


def load_gold(path: Path) -> tuple[GoldCase, ...]:
    rows = _load_jsonl(path)
    cases: list[GoldCase] = []
    seen: set[str] = set()
    for line, row in rows:
        case_id = _required_text(row, "id", path, line)
        if case_id in seen:
            raise ValueError(f"{path}:{line}: duplicate gold id {case_id!r}")
        seen.add(case_id)
        action = _required_text(row, "expected_action", path, line).upper()
        if action not in GOLD_ACTIONS:
            raise ValueError(f"{path}:{line}: unknown expected_action {action!r}")
        category = _required_text(row, "category", path, line).lower()
        if category not in CATEGORIES:
            raise ValueError(f"{path}:{line}: unknown category {category!r}")
        concept = _optional_text(row.get("expected_concept"))
        if action == "LINK" and concept is None:
            raise ValueError(f"{path}:{line}: LINK requires expected_concept")
        if action != "LINK" and concept is not None:
            raise ValueError(f"{path}:{line}: {action} must not have expected_concept")
        cases.append(
            GoldCase(
                case_id=case_id,
                surface=_required_text(row, "surface", path, line),
                language=_required_text(row, "language", path, line).lower(),
                category=category,
                expected_action=action,
                expected_concept=concept,
                english_name=_optional_text(row.get("english_name")),
                context=_optional_text(row.get("context")),
                difficulty=_optional_text(row.get("difficulty")) or "ordinary",
                source_ref=_optional_text(row.get("source_ref")) or "unspecified",
            )
        )
    if not cases:
        raise ValueError(f"{path}: gold set is empty")
    return tuple(cases)


def load_predictions(path: Path) -> tuple[Prediction, ...]:
    rows = _load_jsonl(path)
    predictions: list[Prediction] = []
    seen: set[tuple[str, str]] = set()
    for line, row in rows:
        case_id = _required_text(row, "case_id", path, line)
        experiment = _required_text(row, "experiment", path, line)
        identity = (experiment, case_id)
        if identity in seen:
            raise ValueError(f"{path}:{line}: duplicate prediction {identity!r}")
        seen.add(identity)
        decision = _required_text(row, "decision", path, line).upper()
        if decision not in PREDICTION_DECISIONS:
            raise ValueError(f"{path}:{line}: unknown decision {decision!r}")
        concept = _optional_text(row.get("concept"))
        if decision == "LINK" and concept is None:
            raise ValueError(f"{path}:{line}: LINK requires concept")
        category = _optional_text(row.get("category"))
        if decision == "LINK" and category not in CATEGORIES:
            raise ValueError(f"{path}:{line}: LINK requires a known category")
        raw_candidates = row.get("candidates", [])
        if not isinstance(raw_candidates, list):
            raise ValueError(f"{path}:{line}: candidates must be a list")
        candidates: list[CandidatePrediction] = []
        for index, raw in enumerate(raw_candidates):
            if isinstance(raw, str):
                candidates.append(CandidatePrediction(raw))
            elif isinstance(raw, dict):
                name = _optional_text(raw.get("name"))
                if name is None:
                    raise ValueError(f"{path}:{line}: candidate {index} has no name")
                candidate_category = _optional_text(raw.get("category"))
                if candidate_category is not None and candidate_category not in CATEGORIES:
                    raise ValueError(
                        f"{path}:{line}: candidate {index} has unknown category "
                        f"{candidate_category!r}"
                    )
                candidates.append(CandidatePrediction(name, candidate_category))
            else:
                raise ValueError(f"{path}:{line}: candidate {index} must be text or object")
        predictions.append(
            Prediction(
                case_id=case_id,
                experiment=experiment,
                decision=decision,
                concept=concept,
                category=category,
                candidates=tuple(candidates),
                elapsed_ms=_optional_nonnegative_float(row.get("elapsed_ms"), path, line),
                llm_calls=_nonnegative_int(row.get("llm_calls", 0), "llm_calls", path, line),
                input_tokens=_nonnegative_int(
                    row.get("input_tokens", 0), "input_tokens", path, line
                ),
                output_tokens=_nonnegative_int(
                    row.get("output_tokens", 0), "output_tokens", path, line
                ),
            )
        )
    if not predictions:
        raise ValueError(f"{path}: predictions are empty")
    return tuple(predictions)


def evaluate(
    gold: tuple[GoldCase, ...],
    predictions: tuple[Prediction, ...],
    *,
    ks: tuple[int, ...] = DEFAULT_KS,
    input_usd_per_million: float = 0.0,
    output_usd_per_million: float = 0.0,
) -> dict[str, Any]:
    """Score every experiment, retaining overall and sliced metrics."""
    ks = tuple(sorted(set(ks)))
    if not ks or any(k < 1 for k in ks):
        raise ValueError("ks must contain positive integers")
    if min(input_usd_per_million, output_usd_per_million) < 0:
        raise ValueError("token prices must be nonnegative")

    gold_by_id = {case.case_id: case for case in gold}
    by_experiment: dict[str, list[Prediction]] = defaultdict(list)
    for prediction in predictions:
        if prediction.case_id not in gold_by_id:
            raise ValueError(
                f"prediction {prediction.experiment}/{prediction.case_id} is not in the gold set"
            )
        by_experiment[prediction.experiment].append(prediction)

    return {
        "gold": _gold_summary(gold),
        "top_k": list(ks),
        "prices_usd_per_million_tokens": {
            "input": input_usd_per_million,
            "output": output_usd_per_million,
        },
        "experiments": {
            name: _evaluate_experiment(
                gold,
                rows,
                ks=ks,
                input_price=input_usd_per_million,
                output_price=output_usd_per_million,
            )
            for name, rows in sorted(by_experiment.items())
        },
    }


def _evaluate_experiment(
    gold: tuple[GoldCase, ...],
    predictions: list[Prediction],
    *,
    ks: tuple[int, ...],
    input_price: float,
    output_price: float,
) -> dict[str, Any]:
    by_id = {row.case_id: row for row in predictions}
    paired = [(case, by_id[case.case_id]) for case in gold if case.case_id in by_id]
    missing = [case.case_id for case in gold if case.case_id not in by_id]
    return {
        "coverage": {
            "predicted": len(paired),
            "gold": len(gold),
            "rate": _ratio(len(paired), len(gold)),
            "missing_case_ids": missing,
        },
        "overall": _score_group(paired, ks, input_price, output_price),
        "by_language": _slices(paired, lambda case: case.language, ks, input_price, output_price),
        "by_category": _slices(paired, lambda case: case.category, ks, input_price, output_price),
        "errors": _errors(paired, max(ks)),
    }


def _slices(paired, key, ks, input_price, output_price) -> dict[str, Any]:
    groups: dict[str, list] = defaultdict(list)
    for case, prediction in paired:
        groups[key(case)].append((case, prediction))
    return {
        name: _score_group(rows, ks, input_price, output_price)
        for name, rows in sorted(groups.items())
    }


def _score_group(paired, ks, input_price, output_price) -> dict[str, Any]:
    total = len(paired)
    expected_links = sum(case.expected_action == "LINK" for case, _ in paired)
    predicted_links = sum(prediction.decision == "LINK" for _, prediction in paired)
    true_links = sum(_correct_link(case, prediction) for case, prediction in paired)
    wrong_links = predicted_links - true_links
    exact_actions = sum(
        prediction.decision == case.expected_action
        and (prediction.decision != "LINK" or _correct_link(case, prediction))
        for case, prediction in paired
    )
    defers = sum(prediction.decision == "DEFER" for _, prediction in paired)
    review = total - predicted_links

    retrieval_rows = [
        (case, prediction)
        for case, prediction in paired
        if case.expected_action == "LINK"
    ]
    recall = {
        f"recall_at_{k}": _ratio(
            sum(_candidate_rank(case, prediction) in range(1, k + 1)
                for case, prediction in retrieval_rows),
            len(retrieval_rows),
        )
        for k in ks
    }
    latency = [
        prediction.elapsed_ms
        for _, prediction in paired
        if prediction.elapsed_ms is not None
    ]
    input_tokens = sum(prediction.input_tokens for _, prediction in paired)
    output_tokens = sum(prediction.output_tokens for _, prediction in paired)
    calls = sum(prediction.llm_calls for _, prediction in paired)
    cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    precision = _ratio(true_links, predicted_links)
    link_recall = _ratio(true_links, expected_links)
    return {
        "cases": total,
        "gold_actions": dict(sorted(Counter(case.expected_action for case, _ in paired).items())),
        "retrieval": {"eligible_cases": len(retrieval_rows), **recall},
        "link": {
            "true": true_links,
            "predicted": predicted_links,
            "expected": expected_links,
            "precision": precision,
            "precision_wilson_lower_95": _wilson(true_links, predicted_links, upper=False),
            "recall": link_recall,
            "f1": _f1(precision, link_recall),
            "wrong_auto_link_rate": _ratio(wrong_links, predicted_links),
            "wrong_auto_link_wilson_upper_95": _wilson(
                wrong_links, predicted_links, upper=True
            ),
        },
        "decision_accuracy": _ratio(exact_actions, total),
        "defer_rate": _ratio(defers, total),
        "manual_review": {"cases": review, "rate": _ratio(review, total)},
        "latency_ms": _latency(latency),
        "llm": {
            "calls": calls,
            "calls_per_case": _ratio(calls, total),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": round(cost, 8),
            "estimated_cost_usd_per_case": round(cost / total, 8) if total else None,
        },
    }


def _errors(paired, max_k: int) -> dict[str, list[dict[str, Any]]]:
    errors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case, prediction in paired:
        rank = _candidate_rank(case, prediction)
        base = {
            "case_id": case.case_id,
            "surface": case.surface,
            "language": case.language,
            "category": case.category,
            "difficulty": case.difficulty,
        }
        if case.expected_action == "LINK" and (rank is None or rank > max_k):
            errors["candidate_miss"].append(base)
        if prediction.decision == "LINK" and not _correct_link(case, prediction):
            errors["wrong_link"].append(
                {
                    **base,
                    "expected": case.expected_concept or case.expected_action,
                    "predicted": prediction.concept,
                }
            )
            if prediction.category and prediction.category != case.category:
                errors["category_mismatch"].append(base)
        if case.expected_action == "LINK" and prediction.decision != "LINK":
            errors["unresolved_link"].append(base)
    return {name: rows for name, rows in sorted(errors.items())}


def _candidate_rank(case: GoldCase, prediction: Prediction) -> int | None:
    expected = _identity(case.expected_concept)
    if not expected:
        return None
    for index, candidate in enumerate(prediction.candidates, start=1):
        if _identity(candidate.name) == expected and (
            candidate.category is None or candidate.category == case.category
        ):
            return index
    return None


def _correct_link(case: GoldCase, prediction: Prediction) -> bool:
    return (
        case.expected_action == "LINK"
        and prediction.decision == "LINK"
        and _identity(case.expected_concept) == _identity(prediction.concept)
        and prediction.category == case.category
    )


def _identity(value: str | None) -> str:
    return " ".join((value or "").casefold().replace("-", " ").split())


def _gold_summary(gold: tuple[GoldCase, ...]) -> dict[str, Any]:
    return {
        "cases": len(gold),
        "by_action": dict(sorted(Counter(case.expected_action for case in gold).items())),
        "by_language": dict(sorted(Counter(case.language for case in gold).items())),
        "by_category": dict(sorted(Counter(case.category for case in gold).items())),
        "by_difficulty": dict(sorted(Counter(case.difficulty for case in gold).items())),
    }


def _latency(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"measured": 0, "mean": None, "p50": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {
        "measured": len(values),
        "mean": round(statistics.fmean(values), 3),
        "p50": round(statistics.median(values), 3),
        "p95": round(_percentile(ordered, 0.95), 3),
        "max": round(max(values), 3),
    }


def _percentile(ordered: list[float], fraction: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _wilson(successes: int, total: int, *, upper: bool) -> float | None:
    """One side of the two-sided 95% Wilson score interval."""
    if not total:
        return None
    z = 1.959963984540054
    observed = successes / total
    denominator = 1 + z * z / total
    center = (observed + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(observed * (1 - observed) / total + z * z / (4 * total * total))
    return round(center + margin / denominator if upper else center - margin / denominator, 4)


def _load_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, raw in enumerate(stream, start=1):
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: each line must be an object")
            rows.append((line_number, row))
    return rows


def _required_text(row: dict[str, Any], key: str, path: Path, line: int) -> str:
    value = _optional_text(row.get(key))
    if value is None:
        raise ValueError(f"{path}:{line}: {key} is required")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_nonnegative_float(value: Any, path: Path, line: int) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{path}:{line}: elapsed_ms must be a nonnegative number")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path}:{line}: elapsed_ms must be a nonnegative number") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{path}:{line}: elapsed_ms must be a nonnegative number")
    return number


def _nonnegative_int(value: Any, key: str, path: Path, line: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path}:{line}: {key} must be a nonnegative integer")
    return value
