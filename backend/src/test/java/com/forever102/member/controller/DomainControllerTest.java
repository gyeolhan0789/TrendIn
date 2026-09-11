package com.forever102.member.controller;

import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessResponse;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.prettyPrint;
import static org.springframework.restdocs.payload.PayloadDocumentation.fieldWithPath;
import static org.springframework.restdocs.payload.PayloadDocumentation.responseFields;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.auth.jwt.JwtTokenProvider;
import com.forever102.global.config.SecurityTestConfig;
import com.forever102.member.domain.Domain;
import org.hamcrest.Matchers;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.restdocs.test.autoconfigure.AutoConfigureRestDocs;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(DomainController.class)
@Import(SecurityTestConfig.class)
@AutoConfigureRestDocs
class DomainControllerTest {

    private static final String URL = "/domains";
    private static final Long MEMBER_ID = 1L;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    @Test
    @DisplayName("서비스가 제공하는 분야 목록을 200으로 반환하고 문서화한다")
    void returnsDomains() throws Exception {
        mockMvc.perform(get(URL))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data[0].domain").value("DEVELOP"))
                .andExpect(jsonPath("$.data[0].name").value("개발"))
                .andExpect(jsonPath("$.data[1].domain").value("FASHION"))
                .andExpect(jsonPath("$.data[1].name").value("패션"))
                .andExpect(jsonPath("$.message").value(Matchers.nullValue()))
                .andDo(document("domains-list",
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data[].domain").type(JsonFieldType.STRING)
                                        .description("분야 코드. 다른 API의 domain 파라미터에 그대로 사용한다."),
                                fieldWithPath("data[].name").type(JsonFieldType.STRING)
                                        .description("화면에 표시할 분야 이름"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
    }

    @Test
    @DisplayName("정의된 모든 분야를 선언 순서대로 반환한다")
    void returnsAllDomainsInDeclarationOrder() throws Exception {
        mockMvc.perform(get(URL))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(Domain.values().length))
                .andExpect(jsonPath("$.data[*].domain")
                        .value(Matchers.contains("DEVELOP", "FASHION")));
    }

    @Test
    @DisplayName("토큰 없이 조회할 수 있다")
    void isPublic() throws Exception {
        mockMvc.perform(get(URL))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("토큰을 함께 보내도 같은 목록을 반환한다")
    void returnsSameListForAuthenticatedRequest() throws Exception {
        mockMvc.perform(get(URL)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtTokenProvider.issue(MEMBER_ID).accessToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(Domain.values().length));
    }
}
