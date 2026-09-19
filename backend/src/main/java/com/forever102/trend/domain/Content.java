package com.forever102.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinTable;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.Set;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "contents")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Content {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // 255 is the JPA default and it is not enough: news titles and newsletter
    // URLs run past it, and the ingest job merges a whole batch in one
    // statement, so one long row rolls back every article collected with it.
    // See V9__widen_content_text_columns.sql.
    @Column(nullable = false, length = 2048)
    private String title;

    @Column(nullable = false, length = 2048)
    private String source;

    @Column(nullable = false, unique = true, length = 2048)
    private String url;

    @Column(name = "body_object_key", columnDefinition = "text")
    private String bodyObjectKey;

    @Column(name = "published_at", nullable = false)
    private OffsetDateTime publishedAt;

    @Column(name = "collected_at", nullable = false)
    private OffsetDateTime collectedAt;

    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(
            name = "keyword_contents",
            joinColumns = @JoinColumn(name = "content_id"),
            inverseJoinColumns = @JoinColumn(name = "keyword_id")
    )
    private Set<Keyword> keywords = new LinkedHashSet<>();

    public Content(String title, String source, String url, String bodyObjectKey,
            OffsetDateTime publishedAt, OffsetDateTime collectedAt) {
        this.title = Objects.requireNonNull(title);
        this.source = Objects.requireNonNull(source);
        this.url = Objects.requireNonNull(url);
        this.bodyObjectKey = bodyObjectKey;
        this.publishedAt = Objects.requireNonNull(publishedAt);
        this.collectedAt = Objects.requireNonNull(collectedAt);
    }

    public void addKeyword(Keyword keyword) {
        keywords.add(Objects.requireNonNull(keyword));
    }
}
