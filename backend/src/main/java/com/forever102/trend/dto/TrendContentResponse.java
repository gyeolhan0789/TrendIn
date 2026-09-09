package com.forever102.trend.dto;

import com.forever102.trend.domain.Content;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.data.domain.Page;

public record TrendContentResponse(
        List<ContentItemResponse> content,
        int page,
        int size,
        boolean hasNext
) {
    public static TrendContentResponse from(Page<Content> contents) {
        return new TrendContentResponse(contents.getContent().stream()
                .map(ContentItemResponse::from)
                .toList(), contents.getNumber(), contents.getSize(), contents.hasNext());
    }

    public record ContentItemResponse(
            Long contentId,
            String title,
            String source,
            String url,
            OffsetDateTime publishedAt
    ) {
        private static ContentItemResponse from(Content content) {
            return new ContentItemResponse(content.getId(), content.getTitle(), content.getSource(),
                    content.getUrl(), content.getPublishedAt());
        }
    }
}
