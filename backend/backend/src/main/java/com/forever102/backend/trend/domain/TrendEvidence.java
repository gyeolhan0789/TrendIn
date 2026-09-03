package com.forever102.backend.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import java.math.BigDecimal;
import java.util.Map;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Embeddable
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TrendEvidence {

    @Column(name = "rule_version")
    private String ruleVersion;

    @Column(name = "rule_description", columnDefinition = "text")
    private String ruleDescription;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "applied_thresholds")
    private Map<String, BigDecimal> appliedThresholds;

    @Column(name = "data_coverage")
    private String dataCoverage;

    public TrendEvidence(String ruleVersion, String ruleDescription,
            Map<String, BigDecimal> appliedThresholds, String dataCoverage) {
        this.ruleVersion = ruleVersion;
        this.ruleDescription = ruleDescription;
        this.appliedThresholds = appliedThresholds == null ? null : Map.copyOf(appliedThresholds);
        this.dataCoverage = dataCoverage;
    }
}
