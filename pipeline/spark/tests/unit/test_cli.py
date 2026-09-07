"""진입점 인자 파싱. spark-submit 없이 검사한다."""

from __future__ import annotations

import pytest

from trendin.spark.common.cli import build_parser


def test_공통_인자는_세_Job_이_같다():
    args = build_parser("ingest").parse_args(["--profile", "dev", "--log-level", "DEBUG"])

    assert args.profile == "dev"
    assert args.log_level == "DEBUG"
    assert args.conf_dir is None


def test_인자가_없으면_전부_None_이라_설정이_정한다():
    args = build_parser("extract").parse_args([])

    assert args.profile is None
    assert args.conf_dir is None
    assert args.log_level is None


def test_모르는_인자는_거부한다():
    with pytest.raises(SystemExit):
        build_parser("ingest").parse_args(["--없는인자"])


# --- 진입점 세 개가 실제로 import 되는지 -----------------------------------
# conftest.py 가 spark/jobs 를 경로에 얹는다. import 가 깨지면 spark-submit 도 깨진다.


def test_ingest_는_source_와_manifest_를_받는다():
    import ingest

    parser = build_parser("ingest", ingest.add_arguments)
    assert parser.parse_args([]).source == "kafka"
    assert parser.parse_args(["--source", "manifest"]).source == "manifest"
    with pytest.raises(SystemExit):
        parser.parse_args(["--source", "없는소스"])


def test_extract_는_partitions_를_받는다():
    import extract

    parser = build_parser("extract", extract.add_arguments)
    assert parser.parse_args([]).partitions is None


def test_aggregate_는_date_를_받는다():
    import aggregate

    parser = build_parser("aggregate", aggregate.add_arguments)
    assert parser.parse_args(["--date", "2026-09-03"]).date == "2026-09-03"


def test_세_진입점의_JOB_이름이_checkpoint_경로가_된다():
    import aggregate
    import extract
    import ingest

    assert {ingest.JOB, extract.JOB, aggregate.JOB} == {"ingest", "extract", "aggregate"}
