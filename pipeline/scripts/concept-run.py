#!/usr/bin/env python
"""개념 Job 을 Spark 없이 돌린다 — DB 만 닿으면 노트북에서도 된다.

```sh
# 터널로 팀 DB 를 끌어온 뒤 (deploy 문서의 SSH 터널, 5432 → 15432)
APP_DB_URL=jdbc:postgresql://127.0.0.1:15432/forever102 APP_DB_USER=ssafy APP_DB_PASSWORD=… \
  .venv/Scripts/python scripts/concept-run.py --profile local --domain fashion --dry-run
```

`spark/jobs/concept.py` 의 `run()` 을 세션 없이 부른다. 그 Job 은 세션을 받기만 하고 쓰지
않는다 — 조회는 PostgreSQL, 붙이기는 순수 파이썬이다. 그래서 `submit.sh` 가 있는 데이터
EC2 에 안 들어가고도 DB 가 있는 기계로 터널만 열면 표를 만들고 실제로 붙여 볼 수 있다.

인자는 Job 과 같다 (`--domain` · `--window-days` · `--dry-run` · `--auto-link`). `--profile` 은 설정
뼈대를 어디서 가져올지이고, 접속 주소는 환경변수 `APP_DB_URL` 등이 덮는다.

**운영 경로는 여전히 `submit.sh concept` 이다.** 이 스크립트는 접근 수단이 DB 뿐일 때의 시험용이다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.common.cli import build_parser  # noqa: E402
from trendin.spark.common.config import ConfigError, load_config  # noqa: E402
from trendin.spark.common.exit_codes import CONFIG as EXIT_CONFIG  # noqa: E402
from trendin.spark.common.exit_codes import OK as EXIT_OK  # noqa: E402
from trendin.spark.common.logging import configure_logging  # noqa: E402


def _load_job():
    # `spark/jobs/` 는 패키지가 아니라 파일로 읽는다 (스냅숏 테스트와 같은 방식).
    path = ROOT / "spark" / "jobs" / "concept.py"
    spec = importlib.util.spec_from_file_location("concept_job", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    job = _load_job()
    args = build_parser(job.JOB, job.add_arguments).parse_args(argv)
    configure_logging(args.log_level or "INFO")
    try:
        config = load_config(args.profile, conf_dir=args.conf_dir)
    except ConfigError as error:
        print(f"설정을 읽지 못했다: {error}", file=sys.stderr)
        return EXIT_CONFIG
    try:
        code = job.run(None, config, args)
    except ConfigError as error:
        print(f"{error}", file=sys.stderr)
        return EXIT_CONFIG
    return EXIT_OK if code is None else int(code)


if __name__ == "__main__":
    raise SystemExit(main())
