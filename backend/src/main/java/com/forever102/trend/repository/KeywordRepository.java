package com.forever102.trend.repository;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.Keyword;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface KeywordRepository extends JpaRepository<Keyword, Long> {

    @Query("""
            select keyword
            from Keyword keyword
            where locate(:query, keyword.normalizedName) > 0
              and (:domain is null or keyword.domain = :domain)
            order by case when keyword.normalizedName = :query then 0 else 1 end,
                     keyword.id asc
            """)
    Page<Keyword> searchByName(
            @Param("query") String query,
            @Param("domain") Domain domain,
            Pageable pageable);
}
