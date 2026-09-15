"""설정 3단 병합 — base.yaml ← {profile}.yaml ← 환경변수 (09 §3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from trendin.spark.common.config import (
    DEFAULT_CONF_DIR,
    ENV_BINDINGS,
    Config,
    ConfigError,
    load_config,
    resolve_profile,
)

REPO_CONF = DEFAULT_CONF_DIR


@pytest.fixture
def conf_dir(tmp_path: Path):
    """`write("base", "a: 1")` 로 임시 conf 디렉터리를 채우는 도우미."""

    def write(name: str, body: str) -> Path:
        path = tmp_path / f"{name}.yaml"
        path.write_text(body, encoding="utf-8")
        return path

    write("base", "")
    return tmp_path, write


# --- 3단 병합 -------------------------------------------------------------


def test_프로파일이_base_를_덮는다(conf_dir):
    directory, write = conf_dir
    write("base", "minio:\n  endpoint: http://base:9000\n  region: us-east-1\n")
    write("local", "minio:\n  endpoint: http://127.0.0.1:9000\n")

    config = load_config("local", conf_dir=directory, env={})

    assert config.get("minio.endpoint") == "http://127.0.0.1:9000"
    # 프로파일이 안 적은 키는 base 에서 살아남는다. 이게 안 되면 프로파일마다
    # 전체를 복사해야 하고, 그 복사본은 반드시 나뉜다.
    assert config.get("minio.region") == "us-east-1"


def test_환경변수가_프로파일을_덮는다(conf_dir):
    directory, write = conf_dir
    write("base", "minio:\n  endpoint: http://base:9000\n")
    write("local", "minio:\n  endpoint: http://127.0.0.1:9000\n")

    config = load_config("local", conf_dir=directory, env={"MINIO_ENDPOINT": "http://env:9000"})

    assert config.get("minio.endpoint") == "http://env:9000"


def test_세_층이_한_번에_섞인다(conf_dir):
    """각 층이 서로 다른 키를 이겨야 한다. 한 키만 보면 순서가 뒤집혀도 통과한다."""
    directory, write = conf_dir
    write(
        "base",
        "jdbc:\n  url: jdbc:postgresql://base:5432/d\n  user: base\n"
        "minio:\n  endpoint: http://base:9000\n  region: us-east-1\n",
    )
    write("local", "minio:\n  endpoint: http://127.0.0.1:9000\n")

    config = load_config(
        "local",
        conf_dir=directory,
        env={"APP_DB_URL": "jdbc:postgresql://env:5432/d"},
    )

    assert config.get("jdbc.user") == "base"  # base 만 적었다
    assert config.get("minio.endpoint") == "http://127.0.0.1:9000"  # 프로파일이 이겼다
    assert config.get("jdbc.url") == "jdbc:postgresql://env:5432/d"  # 환경변수가 이겼다
    assert config.get("minio.region") == "us-east-1"  # 아무도 안 덮었다


def test_중첩_사전은_통째로_갈아끼우지_않는다(conf_dir):
    directory, write = conf_dir
    write("base", "spark:\n  conf:\n    a: 1\n    b: 2\n")
    write("local", "spark:\n  conf:\n    b: 20\n")

    config = load_config("local", conf_dir=directory, env={})

    assert config.section("spark.conf") == {"a": 1, "b": 20}


def test_목록은_이어붙이지_않고_바꾼다(conf_dir):
    """이어붙이면 "기본 목록에서 하나를 뺀다" 를 표현할 방법이 없어진다."""
    directory, write = conf_dir
    write("base", 'aggregate:\n  periods: ["24H", "7D", "30D"]\n')
    write("local", 'aggregate:\n  periods: ["24H"]\n')

    config = load_config("local", conf_dir=directory, env={})

    assert config.get("aggregate.periods") == ["24H"]


# --- 환경변수의 경계 -------------------------------------------------------


def test_빈_환경변수는_설정_안_함으로_본다(conf_dir):
    """컴포즈의 ${VAR:-} 가 빈 값을 넘긴다. 그것 때문에 기본값이 지워지면 진단이 어렵다."""
    directory, write = conf_dir
    write("base", "minio:\n  endpoint: http://base:9000\n")
    write("local", "")

    config = load_config("local", conf_dir=directory, env={"MINIO_ENDPOINT": "   "})

    assert config.get("minio.endpoint") == "http://base:9000"


def test_목록에_없는_환경변수는_무시한다(conf_dir):
    """일반 규칙(TRENDIN__X__Y)을 열지 않는다. ENV_BINDINGS 에 적힌 것만 받는다."""
    directory, write = conf_dir
    write("base", "extract:\n  thresholds:\n    min_score: 0.3\n")
    write("local", "")

    config = load_config("local", conf_dir=directory, env={"EXTRACT_THRESHOLDS_MIN_SCORE": "0.9"})

    assert config.get("extract.thresholds.min_score") == 0.3


def test_없던_경로도_환경변수가_만든다(conf_dir):
    directory, write = conf_dir
    write("base", "")
    write("local", "")

    config = load_config("local", conf_dir=directory, env={"MINIO_ENDPOINT": "http://ci:9000"})

    assert config.get("minio.endpoint") == "http://ci:9000"


def test_환경변수_이름이_설정_경로와_일대일이다():
    """같은 경로를 두 변수가 덮으면 어느 쪽이 이기는지 읽는 사람이 알 수 없다."""
    paths = [binding.path for binding in ENV_BINDINGS]
    names = [binding.env for binding in ENV_BINDINGS]
    assert len(set(paths)) == len(paths)
    assert len(set(names)) == len(names)


# --- 프로파일 선택 ---------------------------------------------------------


def test_프로파일은_인자_환경변수_기본값_순서다():
    assert resolve_profile("dev", {"SPARK_JOB_PROFILE": "local"}) == "dev"
    assert resolve_profile(None, {"SPARK_JOB_PROFILE": "dev"}) == "dev"
    assert resolve_profile(None, {}) == "local"
    assert resolve_profile("", {"SPARK_JOB_PROFILE": "dev"}) == "dev"


def test_없는_프로파일은_죽는다(conf_dir):
    """조용히 base 로 떨어뜨리면 어느 값으로 돌았는지 나중에 알 수 없다."""
    directory, _ = conf_dir

    with pytest.raises(ConfigError, match="설정 파일이 없다"):
        load_config("오타난프로파일", conf_dir=directory, env={})


def test_base_가_없으면_죽는다(tmp_path: Path):
    (tmp_path / "local.yaml").write_text("", encoding="utf-8")

    with pytest.raises(ConfigError, match="base.yaml"):
        load_config("local", conf_dir=tmp_path, env={})


# --- 읽기 도구 -------------------------------------------------------------


def test_require_는_빈_값도_거부하고_환경변수_이름을_알려준다(conf_dir):
    directory, write = conf_dir
    write("base", "jdbc:\n  url: ''\n")
    write("local", "")

    config = load_config("local", conf_dir=directory, env={})

    with pytest.raises(ConfigError, match="APP_DB_URL"):
        config.require("jdbc.url")


def test_section_은_구역이_아니면_죽는다(conf_dir):
    directory, write = conf_dir
    write("base", "spark:\n  conf: 8\n")
    write("local", "")

    config = load_config("local", conf_dir=directory, env={})

    with pytest.raises(ConfigError):
        config.section("spark.conf")


def test_비밀은_로그용_사본에서_가려진다(conf_dir):
    directory, write = conf_dir
    write("base", "jdbc:\n  user: trendin\n  password: hunter2\n")
    write("local", "minio:\n  secret_key: s3cr3t\n  access_key: spark\n")

    config = load_config("local", conf_dir=directory, env={})
    masked = config.redacted()

    assert masked["jdbc"]["password"] == "***"
    assert masked["minio"]["secret_key"] == "***"
    assert masked["jdbc"]["user"] == "trendin"  # 비밀이 아니다
    assert masked["minio"]["access_key"] == "spark"  # 계정 이름이지 비밀이 아니다
    assert config.get("jdbc.password") == "hunter2"  # 원본은 그대로다
    assert "hunter2" not in repr(config)


def test_원본은_사본을_고쳐도_안_바뀐다(conf_dir):
    directory, write = conf_dir
    write("base", "spark:\n  conf:\n    a: 1\n")
    write("local", "")

    config = load_config("local", conf_dir=directory, env={})
    config.as_dict()["spark"]["conf"]["a"] = 99

    assert config.get("spark.conf.a") == 1


# --- 저장소에 실제로 있는 파일 ---------------------------------------------


@pytest.mark.parametrize("profile", ["local", "dev"])
def test_저장소_프로파일이_그대로_읽힌다(profile: str):
    """conf/*.yaml 이 깨지면 spark-submit 이 뜨기도 전에 죽는다. 여기서 먼저 잡는다."""
    config = load_config(profile, conf_dir=REPO_CONF, env={})

    assert isinstance(config, Config)
    assert config.profile == profile
    assert config.get("spark.master") == "local[*]"
    assert config.get("ingest.ledger.lookback_hours") == 168
    assert config.get("logging.level") in {"DEBUG", "INFO", "WARNING", "ERROR"}


def test_비밀은_저장소_설정_파일에_없다():
    """비밀번호·시크릿 키가 파일에 적히면 그대로 커밋된다."""
    for profile in ("local", "dev"):
        config = load_config(profile, conf_dir=REPO_CONF, env={})
        assert config.get("jdbc.password", "") == ""
        assert config.get("minio.secret_key", "") == ""
