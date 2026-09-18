"""소스 프로필 로더 (`source-discovery.md` #3, S15P21A102-284).

소스 하나가 TOML 파일 하나다. 여기서 읽어 `SourceDef` 로 바꾼다.

**하나라도 깨지면 전부 실패한다**(확정 8). 깨진 파일만 건너뛰면 그 소스가 조용히 빠진 채
DAG 이 돌고, 아무도 모른다. 대신 CI 가 모든 프로필을 읽어 머지 전에 막는다. 깨진 파일이
여럿이면 첫 번째에서 멈추지 않고 전부 모아 한 번에 알린다.

규칙 칸은 열거형이다(#3.2). 정규식을 받지 않는 이유는 리뷰어가 "이 사이트가 진짜 그
규칙인가"를 프로브 표본으로 볼 수 있어야 해서다. 문서가 이름만 정해 두고 아직 코드가 없는
규칙(`url_path_segment` 등)은 여기서 거부한다 — 읽히기만 하고 어댑터가 모르는 규칙이 있으면
실행해 봐야 알게 된다.
"""

from __future__ import annotations

import datetime as dt
import re
import tomllib
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from trendin.common.collect.contracts import License, Rule, SourceDef

# route 별로 프로필에 적을 수 있는 규칙. 값은 파라미터의 모양이다 — None 이면 파라미터가 없고,
# "str" 이면 비지 않은 문자열, "int" 면 정수, "zone" 이면 IANA 시간대 이름이 반드시 있어야 한다.
# 목록·API 소스는 아직 프로필로 적지 않는다(확정 5).
RULES: dict[str, dict[str, dict[str, str | None]]] = {
    "rss": {
        "article_id": {
            "guid_query_param": "str",
            "link_query_param": "str",
            "guid_hash": None,
            "url_path_segment": "int",
        },
        "published_at": {
            "rss_pubdate": None,
            "rss_pubdate_local": "zone",
            "dc_date": None,
            "atom_published": None,
            "atom_updated": None,
        },
    },
}

REQUIRED = (
    "key",
    "domain",
    "route",
    "country",
    "discover_url",
    "allowed_url_prefixes",
    "article_id",
    "published_at",
)
OPTIONAL = ("page_param", "license")
LICENSE_KEYS = ("name", "url", "reviewed_on")

COUNTRY = re.compile(r"[A-Z]{2}")  # ISO 3166-1 alpha-2, 판정 불가는 XX


class ProfileError(ValueError):
    """프로필이 하나 이상 깨졌다. 메시지에 파일마다 이유가 있다."""


def load_profiles(directory: Path, *, domain: str) -> tuple[SourceDef, ...]:
    """`directory` 의 `*.toml` 을 파일 이름 순으로 읽는다."""
    sources: list[SourceDef] = []
    errors: list[str] = []
    for path in sorted(directory.glob("*.toml")):
        try:
            sources.append(parse_profile(path, domain=domain))
        except (ValueError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")
    if errors:
        raise ProfileError("프로필이 깨졌다 —\n" + "\n".join(errors))
    return tuple(sources)


def parse_profile(path: Path, *, domain: str) -> SourceDef:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return _to_source(data, key=path.stem, domain=domain)


def _to_source(data: dict[str, Any], *, key: str, domain: str) -> SourceDef:
    unknown = sorted(set(data) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise ValueError(f"모르는 키다: {', '.join(unknown)}")
    missing = [name for name in REQUIRED if name not in data]
    if missing:
        raise ValueError(f"필수 칸이 없다: {', '.join(missing)}")

    if data["key"] != key:
        raise ValueError(f"key 가 파일 이름과 다르다: {data['key']!r}")
    if data["domain"] != domain:
        raise ValueError(f"domain 이 {domain!r} 이어야 한다: {data['domain']!r}")
    route = data["route"]
    if route not in RULES:
        raise ValueError(f"프로필로 적을 수 없는 route 다: {route!r}")

    country = _text(data, "country")
    if not COUNTRY.fullmatch(country):
        raise ValueError(f"country 는 대문자 두 글자(판정 불가는 XX)여야 한다: {country!r}")

    prefixes = data["allowed_url_prefixes"]
    if (
        not isinstance(prefixes, list)
        or not prefixes
        or not all(isinstance(p, str) and p.startswith("https://") for p in prefixes)
    ):
        raise ValueError("allowed_url_prefixes 는 https:// 로 시작하는 문자열 목록이어야 한다")
    discover_url = _text(data, "discover_url")
    if not discover_url.startswith(tuple(prefixes)):
        raise ValueError(f"discover_url 이 허용 범위 밖이다: {discover_url!r}")

    return SourceDef(
        key=key,
        domain=domain,
        route=route,
        discover_url=discover_url,
        allowed_url_prefixes=tuple(prefixes),
        country=country,
        article_id=_rule(data, "article_id", route),
        published_at=_rule(data, "published_at", route),
        page_param=_text(data, "page_param") if "page_param" in data else None,
        license=_license(data["license"]) if "license" in data else None,
    )


def _text(data: dict[str, Any], name: str) -> str:
    value = data[name]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} 은 비지 않은 문자열이어야 한다: {value!r}")
    return value


def _rule(data: dict[str, Any], field: str, route: str) -> Rule:
    table = data[field]
    if not isinstance(table, dict):
        raise ValueError(f"{field} 는 {{ rule = ... }} 표여야 한다: {table!r}")
    extra = sorted(set(table) - {"rule", "param"})
    if extra:
        raise ValueError(f"{field} 에 모르는 키다: {', '.join(extra)}")
    allowed = RULES[route][field]
    name = table.get("rule")
    if name not in allowed:
        raise ValueError(
            f"{field} 규칙이 {route} 소스에 없다: {name!r} (있는 것: {', '.join(allowed)})"
        )
    param = table.get("param")
    shape = allowed[name]
    if shape == "str":
        if not isinstance(param, str) or not param:
            raise ValueError(f"{field} 규칙 {name} 은 param 이 있어야 한다 (문자열)")
    elif shape == "int":
        # TOML 의 true 도 파이썬에선 int 다. 위치로 읽히면 조용히 1 이 된다.
        if not isinstance(param, int) or isinstance(param, bool):
            raise ValueError(f"{field} 규칙 {name} 은 param 이 있어야 한다 (정수)")
    elif shape == "zone":
        try:
            ZoneInfo(param)
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            raise ValueError(
                f"{field} 규칙 {name} 은 param 이 있어야 한다 (시간대 이름, 예: Asia/Seoul)"
            ) from None
    elif param is not None:
        raise ValueError(f"{field} 규칙 {name} 은 param 을 받지 않는다")
    return Rule(name, param)


def _license(table: Any) -> License:
    if not isinstance(table, dict) or set(table) != set(LICENSE_KEYS):
        raise ValueError(f"license 는 {', '.join(LICENSE_KEYS)} 셋을 다 적는 표여야 한다")
    if not isinstance(table["reviewed_on"], dt.date) or isinstance(
        table["reviewed_on"], dt.datetime
    ):
        raise ValueError("license.reviewed_on 은 날짜(YYYY-MM-DD)여야 한다")
    if not all(isinstance(table[k], str) and table[k] for k in ("name", "url")):
        raise ValueError("license.name·url 은 비지 않은 문자열이어야 한다")
    return License(table["name"], table["url"], table["reviewed_on"])
