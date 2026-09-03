package com.forever102.backend.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "trends")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Trend {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "keyword_id", nullable = false)
    private Keyword keyword;

    @Column(length = 500)
    private String description;

    @Column(name = "first_detected_at", nullable = false)
    private OffsetDateTime firstDetectedAt;

    public Trend(Keyword keyword, String description, OffsetDateTime firstDetectedAt) {
        this.keyword = Objects.requireNonNull(keyword);
        this.description = description;
        this.firstDetectedAt = Objects.requireNonNull(firstDetectedAt);
    }
}
