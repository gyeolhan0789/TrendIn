"""설정 3단 병합 — `conf/base.yaml` ← `conf/{profile}.yaml` ← 환경변수.

규칙은 [09 §3](../../../../spark/docs/09-dev-and-test.md) 그대로다.

| 무엇 | 어디 |
| --- | --- |
| 알고리즘 임계값 | `conf/*.yaml`. 튜닝 대상이라 코드 밖 |
| 비밀 (비밀번호·시크릿 키) | 환경변수만 (`pipeline/README.md` 규약 10번) |
| 주소 | 프로파일 파일에 기본값, 환경변수가 덮는다 |

주소를 파일에 두는 것은 09 §3 의 "접속 정보는 환경변수만" 을 한 칸 좁힌 것이다. 비밀이
아닌 데다, 기본값이 없으면 `--profile local` 하나로는 아무것도 못 띄운다. 비밀은 여전히
파일에 적지 않는다 — 적으면 그대로 커밋된다.

**환경변수로 덮을 수 있는 경로를 무제한으로 열지 않는다.** `TRENDIN__EXTRACT__MIN_SCORE`
같은 일반 규칙을 두면 오타 난 이름이 조용히 무시되고, "왜 값이 안 바뀌지" 를 며칠 뒤에
발견한다. 아래 `ENV_BINDINGS` 에 적힌 이름만 받고 나머지는 파일로만 바꾼다.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, NamedTuple

import yaml

DEFAULT_PROFILE = "local"
PROFILE_ENV = "SPARK_JOB_PROFILE"

# 저장소 안 기본 위치. `--conf-dir` 로 덮을 수 있다.
DEFAULT_CONF_DIR = Path(__file__).resolve().parents[4] / "spark" / "conf"

# 비밀이 로그·예외 메시지에 섞이지 않게 가리는 키 이름. 부분 일치로 본다.
_SECRET_HINTS = ("password", "secret", "token", "credential")
_REDACTED = "***"


class EnvBinding(NamedTuple):
    """환경변수 하나와 그것이 덮는 설정 경로."""

    env: str
    path: str


# 환경변수 → 설정 경로. [01 §7](../../../../spark/docs/01-architecture.md) 의 표와 같은 목록이다.
ENV_BINDINGS: tuple[EnvBinding, ...] = (
    EnvBinding("KAFKA_BOOTSTRAP_SERVERS", "kafka.bootstrap_servers"),
    EnvBinding("KAFKA_TOPIC_RAW_FILE_READY", "kafka.topics.raw_file_ready"),
    EnvBinding("KAFKA_GROUP_ID_PREFIX", "kafka.group_id_prefix"),
    EnvBinding("MINIO_ENDPOINT", "minio.endpoint"),
    EnvBinding("MINIO_ACCESS_KEY", "minio.access_key"),
    EnvBinding("MINIO_SECRET_KEY", "minio.secret_key"),
    EnvBinding("MINIO_RAW_BUCKET", "minio.buckets.raw"),
    EnvBinding("MINIO_CURATED_BUCKET", "minio.buckets.curated"),
    EnvBinding("APP_DB_URL", "jdbc.url"),
    EnvBinding("APP_DB_USER", "jdbc.user"),
    EnvBinding("APP_DB_PASSWORD", "jdbc.password"),
    EnvBinding("CHECKPOINT_ROOT", "checkpoint.root"),
    EnvBinding("SPARK_MASTER", "spark.master"),
)


class ConfigError(RuntimeError):
    """설정 파일이 없거나, 필수 값이 비어 있거나, 모양이 다르다."""


class Config(Mapping[str, Any]):
    """병합이 끝난 설정. 점 표기로 읽는다 — `config.require("minio.endpoint")`."""

    def __init__(self, data: Mapping[str, Any], *, profile: str) -> None:
        self._data: dict[str, Any] = dict(data)
        self.profile = profile

    # --- Mapping ---------------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    # --- 점 표기 ---------------------------------------------------------
    def get(self, path: str, default: Any = None) -> Any:
        """`"a.b.c"` 를 따라 내려간다. 중간이 없으면 `default`."""
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, Mapping) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, path: str) -> Any:
        """없거나 비어 있으면 죽는다. 접속 정보처럼 없으면 못 도는 값에 쓴다."""
        sentinel = object()
        value = self.get(path, sentinel)
        if value is sentinel or value is None or value == "":
            source = _env_for(path)
            hint = f" (환경변수 {source} 또는 conf/*.yaml 의 {path})" if source else f" ({path})"
            raise ConfigError(f"설정값이 비어 있다{hint}")
        return value

    def section(self, path: str) -> dict[str, Any]:
        """하위 트리를 사전으로. 없으면 빈 사전 — 선택 구역에 쓴다."""
        value = self.get(path, {})
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ConfigError(f"{path} 는 구역이어야 하는데 {type(value).__name__} 이다")
        return dict(value)

    def as_dict(self) -> dict[str, Any]:
        return _deep_copy(self._data)

    def redacted(self) -> dict[str, Any]:
        """비밀을 가린 사본. 로그에는 이것만 찍는다."""
        return _redact(self._data)

    def __repr__(self) -> str:  # 실수로 print 해도 비밀이 새지 않게
        return f"Config(profile={self.profile!r}, data={self.redacted()!r})"


def resolve_profile(cli_value: str | None = None, env: Mapping[str, str] | None = None) -> str:
    """`--profile` → `SPARK_JOB_PROFILE` → `local` 순서로 정한다."""
    environ = os.environ if env is None else env
    for candidate in (cli_value, environ.get(PROFILE_ENV)):
        if candidate:
            return candidate.strip()
    return DEFAULT_PROFILE


def load_config(
    profile: str | None = None,
    *,
    conf_dir: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    """`base.yaml` 위에 프로파일을, 그 위에 환경변수를 얹는다."""
    environ = os.environ if env is None else env
    resolved = resolve_profile(profile, environ)
    directory = Path(conf_dir) if conf_dir is not None else DEFAULT_CONF_DIR

    merged = _read_yaml(directory / "base.yaml", required=True)
    # 프로파일 파일이 없으면 죽는다. 오타를 조용히 base 로 떨어뜨리면 어느 값으로
    # 돌았는지 나중에 알 수 없다.
    merged = _deep_merge(merged, _read_yaml(directory / f"{resolved}.yaml", required=True))
    merged = _apply_env(merged, environ)
    return Config(merged, profile=resolved)


# --- 내부 ----------------------------------------------------------------


def _read_yaml(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ConfigError(f"설정 파일이 없다: {path}")
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ConfigError(f"{path} 의 최상위는 사전이어야 한다")
    return dict(loaded)


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """사전은 재귀로 합치고, 나머지 타입은 통째로 갈아끼운다.

    목록을 이어붙이지 않는 이유는 "기본 목록에서 하나를 빼는" 표현이 불가능해지기
    때문이다. 프로파일이 목록을 적었으면 그 목록이 전부다.
    """
    result = dict(base)
    for key, value in overlay.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(current, value)
        else:
            result[key] = _deep_copy(value)
    return result


def _apply_env(data: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    result = _deep_copy(data)
    for binding in ENV_BINDINGS:
        raw = env.get(binding.env)
        # 빈 문자열은 "설정 안 함" 으로 본다. 컴포즈의 `${VAR:-}` 가 빈 값을 넘기는데,
        # 그것 때문에 파일의 기본값이 지워지면 진단이 어렵다.
        if raw is None or raw.strip() == "":
            continue
        _set_path(result, binding.path, raw)
    return result


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _env_for(path: str) -> str | None:
    for binding in ENV_BINDINGS:
        if binding.path == path:
            return binding.env
    return None


def _deep_copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _deep_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value


def _redact(value: Any, *, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {name: _redact(item, key=name) for name, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, key=key) for item in value]
    lowered = key.lower()
    if value not in (None, "") and any(hint in lowered for hint in _SECRET_HINTS):
        return _REDACTED
    return value
