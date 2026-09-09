package com.forever102.trend.repository;

import com.forever102.trend.domain.Content;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ContentRepository extends JpaRepository<Content, Long> {

    @Query("""
            select content
            from Content content
            join content.keywords keyword
            where keyword.id = :keywordId
            order by content.publishedAt desc, content.id desc
            """)
    Page<Content> findByKeywordId(@Param("keywordId") Long keywordId, Pageable pageable);
}
