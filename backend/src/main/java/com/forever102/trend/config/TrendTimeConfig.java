package com.forever102.trend.config;

import com.forever102.trend.domain.AnalysisWindow;
import java.time.Clock;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class TrendTimeConfig {

    @Bean
    public Clock trendClock() {
        return Clock.system(AnalysisWindow.ANALYSIS_ZONE);
    }
}
