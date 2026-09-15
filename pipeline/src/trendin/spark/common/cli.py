"""`spark-submit` 진입점이 공유하는 인자 파싱과 실행 뼈대.

`jobs/*.py` 는 인자 파싱·세션 생성·종료 처리를 여기에 맡기고 단계 호출만 남긴다
([09 §1](../../../../spark/docs/09-dev-and-test.md)).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

from trendin.spark.common.config import Config, ConfigError, load_config
from trendin.spark.common.exit_codes import CONFIG as EXIT_CONFIG
from trendin.spark.common.exit_codes import OK as EXIT_OK
from trendin.spark.common.logging import configure_logging, get_logger
from trendin.spark.common.session import build_session

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

log = get_logger(__name__)

# `None` 을 주면 0 이다. 숫자를 주면 그 값이 프로세스의 종료 코드가 된다 —
# `ingest` 가 "새로 쓴 것이 없다" 를 알릴 때 `exit_codes.NOTHING_NEW` 를 그대로 준다.
# 그 이름을 여기서 다시 내보내지 않는다 — 쓰는 쪽이 `exit_codes` 를 직접 읽으면 값이
# 어디서 오는지 한 번에 보인다 (S15P21A102-247 코드리뷰).
JobHandler = Callable[["SparkSession", Config, argparse.Namespace], "int | None"]
ArgumentHook = Callable[[argparse.ArgumentParser], None]


def build_parser(job: str, add_arguments: ArgumentHook | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"{job}.py", description=f"TrendIn Spark job — {job}")
    parser.add_argument(
        "--profile",
        default=None,
        help="설정 프로파일. 없으면 SPARK_JOB_PROFILE, 그것도 없으면 local",
    )
    parser.add_argument(
        "--conf-dir",
        default=None,
        help="conf 디렉터리. 없으면 저장소의 spark/conf",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="파이썬 로그 수준. 없으면 설정의 logging.level",
    )
    if add_arguments is not None:
        add_arguments(parser)
    return parser


def run_job(
    job: str,
    handler: JobHandler,
    *,
    argv: list[str] | None = None,
    add_arguments: ArgumentHook | None = None,
) -> int:
    """설정을 읽고 세션을 만들어 `handler` 를 부른다. 끝나면 세션을 닫는다.

    `handler` 가 숫자를 주면 그것이 종료 코드다. Airflow 가 그 값을 읽으므로
    (`spark/dag_factory.SubmitOperator`) 아무 숫자나 쓰지 않고 `exit_codes` 에 적힌 것만 쓴다.
    """
    args = build_parser(job, add_arguments).parse_args(argv)
    configure_logging(args.log_level or "INFO")

    try:
        config = load_config(args.profile, conf_dir=args.conf_dir)
    except ConfigError as error:
        log.error("설정을 읽지 못했다: %s", error)
        return EXIT_CONFIG
    if args.log_level is None:
        configure_logging(config.get("logging.level", "INFO"))

    log.info("job=%s profile=%s 로 시작한다", job, config.profile)
    session = build_session(job, config)
    try:
        exit_code = handler(session, config, args)
    finally:
        # 스트림이 없으므로 스스로 끝난다. 세션을 닫아야 프로세스가 내려간다 ([01 §1]).
        session.stop()
    log.info("job=%s 끝 (종료 코드 %d)", job, exit_code or EXIT_OK)
    return exit_code or EXIT_OK


def main(
    job: str,
    handler: JobHandler,
    *,
    add_arguments: ArgumentHook | None = None,
) -> None:
    """`if __name__ == "__main__":` 에서 부르는 형태. 종료 코드를 그대로 넘긴다."""
    sys.exit(run_job(job, handler, add_arguments=add_arguments))
