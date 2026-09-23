package com.forever102.trend.repository;

import jakarta.persistence.EntityManager;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Repository;

/**
 * 키워드가 붙은 개념의 대표 이름을 읽습니다. 대표 이름은 개념 사전의 영어 표기입니다.
 *
 * 개념 표(pl_concept · pl_concept_expression)는 파이프라인이 만들고 채웁니다. 서비스 마이그레이션에
 * 없는 표라 엔티티로 두지 않고 읽기만 합니다. 키워드를 개념에 잇는 규칙은 파이프라인이 순위를 접을 때
 * 쓰는 것과 같습니다. 정규화 이름이 표현과 같으면 그 개념에 붙고, 한 표기가 두 개념에 걸리면
 * (디자이너이자 브랜드인 이름) 어느 쪽 이름도 붙이지 않습니다.
 *
 * 원문이 영어 표현이면 이름을 붙이지 않습니다. 원문 옆에 적을 이름이라, 영어 원문에 붙이면
 * accessories (accessory) · SS27 (season) 처럼 같은 말을 대표 이름으로 한 번 더 적게 됩니다.
 * 이탈리아어·프랑스어도 알파벳을 써서 글자 모양으로는 가를 수 없으므로 표현의 언어(lang)를 봅니다.
 * 여러 언어의 표현에 걸린 키워드는 그중 하나라도 영어면 영어 원문으로 봅니다.
 */
@Slf4j
@Repository
@RequiredArgsConstructor
public class KeywordConceptRepository {

    /** 표 이름을 소문자로 견줍니다. H2 는 따옴표 없는 이름을 대문자로 적어 둡니다. */
    private static final String TABLES_SQL = """
            select count(distinct lower(table_name))
            from information_schema.tables
            where lower(table_name) in ('pl_concept', 'pl_concept_expression')
            """;

    private static final String NAMES_SQL = """
            select keyword.id, min(concept.canonical_name)
            from keywords keyword
            join pl_concept_expression concept_expression
              on concept_expression.normalized = keyword.normalized_name
             and concept_expression.status = 'ACTIVE'
            join pl_concept concept
              on concept.id = concept_expression.concept_id
             and concept.status = 'ACTIVE'
            where keyword.id in (:keywordIds)
            group by keyword.id
            having count(distinct concept.id) = 1
               and sum(case when concept_expression.lang = 'en' then 1 else 0 end) = 0
            """;

    private final EntityManager entityManager;

    /** 한 번 보이면 다시 묻지 않습니다. 파이프라인이 만든 표가 도로 사라지지는 않습니다. */
    private volatile boolean tablesPresent;
    private volatile boolean absenceLogged;

    /** keywordId → 개념 대표 이름. 개념이 없거나, 두 개념에 걸리거나, 영어 원문인 키워드는 담지 않습니다. */
    public Map<Long, String> findConceptNames(Collection<Long> keywordIds) {
        if (keywordIds.isEmpty() || !tablesPresent()) {
            return Map.of();
        }
        List<?> rows = entityManager.createNativeQuery(NAMES_SQL)
                .setParameter("keywordIds", keywordIds)
                .getResultList();
        Map<Long, String> names = new HashMap<>();
        for (Object row : rows) {
            Object[] columns = (Object[]) row;
            names.put(((Number) columns[0]).longValue(), (String) columns[1]);
        }
        return Map.copyOf(names);
    }

    /*
     * 표가 없는 곳(로컬 H2)에서 조회를 그대로 던지면 그 나라 화면이 통째로 실패합니다. 영어 이름은
     * 덧붙이는 것이라, 없으면 원문만 내보냅니다. PostgreSQL 은 실패한 문장 하나로 트랜잭션 전체가
     * 멈추므로, 던지고 잡는 대신 먼저 묻습니다.
     */
    private boolean tablesPresent() {
        if (tablesPresent) {
            return true;
        }
        Number count = (Number) entityManager.createNativeQuery(TABLES_SQL).getSingleResult();
        tablesPresent = count.intValue() == 2;
        if (!tablesPresent && !absenceLogged) {
            absenceLogged = true;
            log.warn("개념 표(pl_concept · pl_concept_expression)가 없어 키워드에 영어 이름을 붙이지 않는다.");
        }
        return tablesPresent;
    }
}
