package com.forever102.trend.repository;

import com.forever102.trend.domain.KeywordRelation;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface KeywordRelationRepository
        extends JpaRepository<KeywordRelation, KeywordRelation.Key> {

    @Query("""
            select relation
            from KeywordRelation relation
            join fetch relation.targetKeyword targetKeyword
            where relation.sourceKeyword.id = :sourceKeywordId
              and targetKeyword.id <> :sourceKeywordId
            order by relation.relationScore desc, targetKeyword.id asc
            """)
    List<KeywordRelation> findBySourceKeywordIdOrderByScore(
            @Param("sourceKeywordId") Long sourceKeywordId);
}
