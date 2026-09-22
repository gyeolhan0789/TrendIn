from __future__ import annotations

import json

import pytest

from trendin.spark.concept.evaluation import evaluate, load_gold, load_predictions


def _write(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _gold(tmp_path):
    return load_gold(
        _write(
            tmp_path / "gold.jsonl",
            [
                {
                    "id": "ko-link",
                    "surface": "조끼",
                    "language": "ko",
                    "category": "apparel",
                    "expected_action": "LINK",
                    "expected_concept": "vest",
                    "english_name": "vest",
                    "difficulty": "translation",
                },
                {
                    "id": "ko-exclude",
                    "surface": "인스타그램",
                    "language": "ko",
                    "category": "generic",
                    "expected_action": "EXCLUDE",
                    "expected_concept": None,
                },
                {
                    "id": "ja-new",
                    "surface": "架空人名",
                    "language": "ja",
                    "category": "person",
                    "expected_action": "NEW",
                    "expected_concept": None,
                },
            ],
        )
    )


def test_scores_retrieval_links_safety_latency_and_cost(tmp_path):
    gold = _gold(tmp_path)
    predictions = load_predictions(
        _write(
            tmp_path / "predictions.jsonl",
            [
                {
                    "case_id": "ko-link",
                    "experiment": "combined-k5",
                    "decision": "LINK",
                    "concept": "vest",
                    "category": "apparel",
                    "candidates": ["jacket", "vest"],
                    "elapsed_ms": 20,
                    "llm_calls": 2,
                    "input_tokens": 100,
                    "output_tokens": 20,
                },
                {
                    "case_id": "ko-exclude",
                    "experiment": "combined-k5",
                    "decision": "DEFER",
                    "candidates": ["Instagram"],
                    "elapsed_ms": 10,
                    "llm_calls": 1,
                    "input_tokens": 50,
                    "output_tokens": 10,
                },
                {
                    "case_id": "ja-new",
                    "experiment": "combined-k5",
                    "decision": "NEW",
                    "candidates": [],
                    "elapsed_ms": 30,
                    "llm_calls": 1,
                    "input_tokens": 50,
                    "output_tokens": 10,
                },
            ],
        )
    )
    report = evaluate(
        gold,
        predictions,
        ks=(1, 3, 5),
        input_usd_per_million=1.0,
        output_usd_per_million=2.0,
    )
    overall = report["experiments"]["combined-k5"]["overall"]
    assert overall["retrieval"]["recall_at_1"] == 0.0
    assert overall["retrieval"]["recall_at_3"] == 1.0
    assert overall["link"]["precision"] == 1.0
    assert overall["link"]["recall"] == 1.0
    assert overall["link"]["wrong_auto_link_rate"] == 0.0
    assert overall["defer_rate"] == 0.3333
    assert overall["latency_ms"] == {
        "measured": 3,
        "mean": 20.0,
        "p50": 20.0,
        "p95": 29.0,
        "max": 30.0,
    }
    assert overall["llm"]["estimated_cost_usd"] == 0.00028
    assert set(report["experiments"]["combined-k5"]["by_language"]) == {"ja", "ko"}


def test_empty_candidate_list_counts_as_retrieval_miss(tmp_path):
    gold = _gold(tmp_path)
    predictions = load_predictions(
        _write(
            tmp_path / "predictions.jsonl",
            [{"case_id": "ko-link", "experiment": "none", "decision": "DEFER"}],
        )
    )
    retrieval = evaluate(gold, predictions)["experiments"]["none"]["overall"]["retrieval"]
    assert retrieval["eligible_cases"] == 1
    assert retrieval["recall_at_10"] == 0.0
    errors = evaluate(gold, predictions)["experiments"]["none"]["errors"]
    assert [row["case_id"] for row in errors["candidate_miss"]] == ["ko-link"]


def test_wrong_link_is_false_positive_and_false_negative(tmp_path):
    gold = _gold(tmp_path)
    predictions = load_predictions(
        _write(
            tmp_path / "predictions.jsonl",
            [
                {
                    "case_id": "ko-link",
                    "experiment": "unsafe",
                    "decision": "LINK",
                    "concept": "jacket",
                    "category": "apparel",
                    "candidates": ["jacket"],
                },
                {
                    "case_id": "ko-exclude",
                    "experiment": "unsafe",
                    "decision": "LINK",
                    "concept": "Instagram",
                    "category": "brand",
                },
            ],
        )
    )
    experiment = evaluate(gold, predictions)["experiments"]["unsafe"]
    link = experiment["overall"]["link"]
    assert link == {
        "true": 0,
        "predicted": 2,
        "expected": 1,
        "precision": 0.0,
        "precision_wilson_lower_95": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "wrong_auto_link_rate": 1.0,
        "wrong_auto_link_wilson_upper_95": 1.0,
    }
    assert experiment["coverage"]["missing_case_ids"] == ["ja-new"]
    assert len(experiment["errors"]["wrong_link"]) == 2
    assert len(experiment["errors"]["category_mismatch"]) == 1


def test_gold_contract_rejects_link_without_concept(tmp_path):
    path = _write(
        tmp_path / "bad.jsonl",
        [{
            "id": "bad", "surface": "x", "language": "en", "category": "style",
            "expected_action": "LINK",
        }],
    )
    with pytest.raises(ValueError, match="LINK requires expected_concept"):
        load_gold(path)


def test_prediction_contract_rejects_duplicate_experiment_case(tmp_path):
    row = {"case_id": "one", "experiment": "same", "decision": "DEFER"}
    path = _write(tmp_path / "bad.jsonl", [row, row])
    with pytest.raises(ValueError, match="duplicate prediction"):
        load_predictions(path)
