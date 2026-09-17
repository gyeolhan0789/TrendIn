"""진입점 인자 파싱. spark-submit 없이 검사한다."""

from __future__ import annotations

import pytest

from trendin.spark.common import exit_codes
from trendin.spark.common.cli import build_parser, run_job


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
# conftest.py 가 spark/jobs 를 경로에 덧붙인다. import 가 깨지면 spark-submit 도 깨진다.


def test_ingest_는_source_와_재처리_범위를_받는다():
    import ingest

    parser = build_parser("ingest", ingest.add_arguments)
    assert parser.parse_args([]).source == "ledger"
    assert parser.parse_args(["--source", "objects"]).source == "objects"
    with pytest.raises(SystemExit):
        parser.parse_args(["--source", "없는소스"])


def test_ingest_재처리_범위는_발행일이고_기본은_비어_있다():
    """`--from`·`--to` 는 예약어라 dest 를 따로 준다. 이름이 어긋나면 조용히 None 이 된다."""
    import ingest

    parser = build_parser("ingest", ingest.add_arguments)

    empty = parser.parse_args([])
    assert (empty.domain, empty.date_from, empty.date_to, empty.force) == (
        None,
        None,
        None,
        False,
    )

    args = parser.parse_args(
        [
            "--source",
            "objects",
            "--domain",
            "fashion",
            "--from",
            "2026-09-01",
            "--to",
            "2026-09-03",
            "--force",
        ]
    )
    assert (args.domain, args.date_from, args.date_to, args.force) == (
        "fashion",
        "2026-09-01",
        "2026-09-03",
        True,
    )


def test_extract_는_실행_목록과_발행일_구간을_받는다():
    import extract

    parser = build_parser("extract", extract.add_arguments)
    args = parser.parse_args([])
    assert args.ingest_run_ids is None and args.date_from is None and args.force is False

    args = parser.parse_args(
        ["--domain", "fashion", "--from", "2026-09-01", "--to", "2026-09-07", "--force"]
    )
    assert (args.domain, args.date_from, args.date_to, args.force) == (
        "fashion",
        "2026-09-01",
        "2026-09-07",
        True,
    )


def test_aggregate_는_date_를_받는다():
    import aggregate

    parser = build_parser("aggregate", aggregate.add_arguments)
    assert parser.parse_args(["--date", "2026-09-03"]).date == "2026-09-03"


def test_analyze_는_전체_기간을_기본으로_단일_기간도_받는다():
    import analyze

    parser = build_parser("analyze", analyze.add_arguments)
    assert parser.parse_args([]).period is None
    assert parser.parse_args(["--period", "24H"]).period == "24H"
    with pytest.raises(SystemExit):
        parser.parse_args(["--period", "14D"])


def test_네_진입점의_JOB_이름이_정해져_있다():
    import aggregate
    import analyze
    import extract
    import ingest

    assert {ingest.JOB, extract.JOB, aggregate.JOB, analyze.JOB} == {
        "ingest",
        "extract",
        "aggregate",
        "analyze",
    }


def test_ingest_는_contents_부재_허용_플래그를_받고_기본은_꺼져_있다():
    """기본은 설정(`ingest.contents.required`)이 정하고, 플래그는 그 값을 푸는 쪽으로만 덮는다."""
    import ingest

    parser = build_parser("ingest", ingest.add_arguments)
    assert parser.parse_args([]).allow_missing_contents is False
    assert parser.parse_args(["--allow-missing-contents"]).allow_missing_contents is True
    with pytest.raises(SystemExit):
        parser.parse_args(["--require-contents"])


# --- 종료 코드 (S15P21A102-247) ---------------------------------------------
#
# Airflow 가 이 숫자를 읽는다. `handler` 가 준 값이 프로세스 종료 코드까지 그대로 가지
# 않으면 `BashOperator` 가 "새로 쓴 것 없음" 을 성공으로 읽고 뒤 단계를 헛되이 깨운다.


def run_with(monkeypatch, handler) -> int:
    """세션과 설정을 대역으로 끼우고 `run_job` 만 돌린다."""

    class Session:
        def stop(self) -> None:
            self.stopped = True

    session = Session()
    monkeypatch.setattr("trendin.spark.common.cli.build_session", lambda *a, **k: session)
    code = run_job("ingest", handler, argv=["--profile", "local"])
    assert getattr(session, "stopped", False), "세션을 안 닫으면 프로세스가 안 내려간다"
    return code


def test_아무것도_안_주면_0_이다(monkeypatch):
    assert run_with(monkeypatch, lambda *a: None) == exit_codes.OK


def test_handler_가_준_종료_코드가_그대로_나간다(monkeypatch):
    """`ingest` 가 "새로 쓴 것이 없다" 를 이 길로 알린다."""
    got = run_with(monkeypatch, lambda *a: exit_codes.NOTHING_NEW)

    assert got == exit_codes.NOTHING_NEW


def test_새_것_없음은_BashOperator_의_skip_코드와_같다():
    """`skip_on_exit_code` 의 기본값이다. 바꾸면 `spark/dag_factory.py` 가 같이 바뀌어야 한다."""
    assert exit_codes.NOTHING_NEW == 99
    assert exit_codes.OK == 0 and exit_codes.CONFIG == 2
