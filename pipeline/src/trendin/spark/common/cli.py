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
from trendin.spark.common.logging import configure_logging, get_logger
from trendin.spark.common.session import build_session

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

log = get_logger(__name__)

JobHandler = Callable[["SparkSession", Config, argparse.Namespace], None]
ArgumentHook = Callable[[argparse.ArgumentParser], None]

EXIT_OK = 0
EXIT_CONFIG = 2


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
    """설정을 읽고 세션을 만들어 `handler` 를 부른다. 끝나면 세션을 닫는다."""
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
        handler(session, config, args)
    finally:
        # Trigger.AvailableNow 는 스스로 끝난다. 세션을 닫아야 프로세스가 내려간다 ([01 §1]).
        session.stop()
    log.info("job=%s 끝", job)
    return EXIT_OK


def main(
    job: str,
    handler: JobHandler,
    *,
    add_arguments: ArgumentHook | None = None,
) -> None:
    """`if __name__ == "__main__":` 에서 부르는 형태. 종료 코드를 그대로 넘긴다."""
    sys.exit(run_job(job, handler, add_arguments=add_arguments))
