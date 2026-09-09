package com.forever102.trend.repository;

import com.forever102.trend.domain.KeywordRelation;
import com.forever102.member.domain.Domain;
import java.math.BigDecimal;
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

    @Query("""
            select targetKeyword.id as keywordId,
                   targetKeyword.name as keyword,
                   targetKeyword.domain as domain,
                   max(relation.relationScore) as relationScore
            from KeywordRelation relation
            join relation.targetKeyword targetKeyword
            where exists (
                select interestKeyword.id
                from MemberInterestKeyword interestKeyword
                where interestKeyword.member.id = :memberId
                  and interestKeyword.keyword = relation.sourceKeyword
            )
              and not exists (
                select interestKeyword.id
                from MemberInterestKeyword interestKeyword
                where interestKeyword.member.id = :memberId
                  and interestKeyword.keyword = targetKeyword
            )
            group by targetKeyword.id, targetKeyword.name, targetKeyword.domain
            order by max(relation.relationScore) desc, targetKeyword.id asc
            """)
    List<RecommendedKeywordProjection> findRecommendedKeywords(@Param("memberId") Long memberId);

    interface RecommendedKeywordProjection {
        Long getKeywordId();

        String getKeyword();

        Domain getDomain();

        BigDecimal getRelationScore();
    }
}
