package com.forever102.global.response;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class BaseResponseTest {

    @Test
    @DisplayName("성공 응답은 success가 true이고 전달한 데이터를 담는다")
    void successResponseHoldsData() {
        // given
        String data = "데이터";

        // when
        BaseResponse<String> response = BaseResponse.success(data);

        // then
        assertThat(response).isEqualTo(new BaseResponse<>(true, "데이터", null));
    }

    @Test
    @DisplayName("성공 응답은 메시지를 담지 않는다")
    void successResponseHasNoMessage() {
        // given
        String data = "데이터";

        // when
        BaseResponse<String> response = BaseResponse.success(data);

        // then
        assertThat(response.message()).isNull();
    }

    @Test
    @DisplayName("반환할 데이터가 없어도 성공 응답을 만들 수 있다")
    void successResponseAllowsNullData() {
        // given & when
        BaseResponse<Void> response = BaseResponse.success(null);

        // then
        assertThat(response).isEqualTo(new BaseResponse<>(true, null, null));
    }

    @Test
    @DisplayName("성공 응답은 컬렉션 등 임의의 타입을 데이터로 담는다")
    void successResponseHoldsAnyDataType() {
        // given
        List<Integer> data = List.of(1, 2, 3);

        // when
        BaseResponse<List<Integer>> response = BaseResponse.success(data);

        // then
        assertThat(response.data()).containsExactly(1, 2, 3);
    }

    @Test
    @DisplayName("실패 응답은 success가 false이고 전달한 메시지를 담는다")
    void failResponseHoldsMessage() {
        // given
        String message = "실패 사유";

        // when
        BaseResponse<String> response = BaseResponse.fail(message);

        // then
        assertThat(response).isEqualTo(new BaseResponse<>(false, null, "실패 사유"));
    }

    @Test
    @DisplayName("실패 응답은 데이터를 담지 않는다")
    void failResponseHasNoData() {
        // given
        String message = "실패 사유";

        // when
        BaseResponse<String> response = BaseResponse.fail(message);

        // then
        assertThat(response.data()).isNull();
    }

    @Test
    @DisplayName("빌더로 성공 여부, 데이터, 메시지를 모두 직접 지정할 수 있다")
    void builderSetsEveryField() {
        // given & when
        BaseResponse<String> response = BaseResponse.<String>builder()
                .success(true)
                .data("데이터")
                .message("메시지")
                .build();

        // then
        assertThat(response).isEqualTo(new BaseResponse<>(true, "데이터", "메시지"));
    }

    @Test
    @DisplayName("성공 여부와 데이터가 같은 두 응답은 서로 같다")
    void responsesWithSameValuesAreEqual() {
        // given
        BaseResponse<String> response = BaseResponse.success("데이터");

        // when
        BaseResponse<String> other = BaseResponse.success("데이터");

        // then
        assertThat(response).isEqualTo(other);
    }

    @Test
    @DisplayName("성공 여부가 다른 두 응답은 서로 다르다")
    void responsesWithDifferentSuccessAreNotEqual() {
        // given
        BaseResponse<String> success = BaseResponse.success("데이터");

        // when
        BaseResponse<String> fail = BaseResponse.fail("데이터");

        // then
        assertThat(success).isNotEqualTo(fail);
    }
}
