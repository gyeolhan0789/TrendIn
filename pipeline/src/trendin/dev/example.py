"""dev_example DAG 의 태스크 함수. 팀원 설계서 v0.1 의 collect_documents 모양을 더미로 옮긴 것."""

SOURCES = ("hacker_news", "example_blog")


def load_active_sources() -> list[str]:
    """활성 소스 목록. 실제 부품은 data_sources 테이블에서 읽는다.

    동적 매핑(expand) 입력이라 list 여야 한다.
    """
    return list(SOURCES)


def collect_source(source: str) -> int:
    """소스 하나를 수집하고 건수를 돌려준다. 더미: 소스 이름 길이."""
    if source not in SOURCES:
        raise ValueError(f"알 수 없는 소스: {source!r}")
    return len(source)


def sum_counts(counts) -> int:
    """매핑 태스크의 건수를 합친다. 실패한 인스턴스는 XCom 이 없으므로(None) 건너뛴다."""
    return sum(c for c in counts if c)


def save_collection_metrics(counts) -> int:
    """건수 합계를 앱 DB 에 기록하는 자리. 스켈레톤에선 접속 확인(SELECT 1)만 한다."""
    from airflow.providers.postgres.hooks.postgres import PostgresHook  # 태스크 안에서만 import

    total = sum_counts(counts)
    PostgresHook(postgres_conn_id="app_db").get_first("SELECT 1")
    return total
