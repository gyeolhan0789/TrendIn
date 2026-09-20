package com.forever102.trend.dto;

import com.forever102.trend.domain.Content;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.data.domain.Page;

/**
 * 트렌드에 걸린 콘텐츠 한 쪽.
 *
 * <p>totalElements 를 함께 내린다. 저장소가 Slice 가 아니라 Page 를 돌려주므로 count 쿼리는
 * 어차피 매번 돈다. 세어 둔 값을 버리면 화면은 마지막 쪽이 어디인지 끝까지 넘겨 보기 전에는
 * 알 수 없고, 쪽 표시가 '6 / 6+' 처럼 아무것도 말하지 못하는 숫자가 된다.
 */
public record TrendContentResponse(
        List<ContentItemResponse> content,
        int page,
        int size,
        boolean hasNext,
        long totalElements
) {
    public static TrendContentResponse from(Page<Content> contents) {
        return new TrendContentResponse(contents.getContent().stream()
                .map(ContentItemResponse::from)
                .toList(), contents.getNumber(), contents.getSize(), contents.hasNext(),
                contents.getTotalElements());
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
