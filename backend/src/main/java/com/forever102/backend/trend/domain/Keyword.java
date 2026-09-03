package com.forever102.backend.trend.domain;

import com.forever102.backend.member.domain.Domain;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "keywords")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Keyword {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Domain domain;

    public Keyword(String name, Domain domain) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("키워드는 비어 있을 수 없습니다.");
        }
        this.name = name;
        this.domain = Objects.requireNonNull(domain);
    }
}
