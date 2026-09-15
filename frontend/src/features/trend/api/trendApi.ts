import { apiClient } from '../../../api/client';
import type { ApiResponse, Page } from '../../../api/apiResponse';
import { unwrap } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type { PeriodCode } from '../../../constants/filterCodes';
import type {
  Trend,
  TrendAnalysisWindow,
  TrendContent,
  TrendDetail,
  TrendHistory,
  TrendList,
  TrendListParams,
  TrendRelatedKeyword,
} from '../types/trend';

/** 목록 응답의 분야는 코드 키가 domain 입니다. 다른 응답(code)과 달라 화면에 그대로 넘기지 않습니다. */
interface TrendListItemResponse extends Omit<Trend, 'domain'> {
  domain: { domain: string; name: string };
}

interface TrendListResponse extends Page<TrendListItemResponse> {
  analysisWindow: TrendAnalysisWindow | null;
}

interface TrendRelatedKeywordResponse {
  trendId: number;
  relatedKeywords: TrendRelatedKeyword[];
}

function toTrend({ domain, ...rest }: TrendListItemResponse): Trend {
  return { ...rest, domain: { code: domain.domain, name: domain.name } };
}

/**
 * 한 분야의 트렌드를 갈래별로 가져옵니다. 분야·갈래·기간이 모두 필수라 한 번에 한 갈래만 받습니다.
 *
 * 집계가 끝난 구간만 잡히므로, 아직 그 구간 지표가 쌓이지 않았으면 목록이 비어서 옵니다.
 * 빈 목록과 오류는 다른 상황이라 화면에서 갈라 보여 줍니다.
 */
export async function getTrends({ domain, type, period, page = 0, size = 20 }: TrendListParams): Promise<TrendList> {
  const data = await unwrap(apiClient.get<ApiResponse<TrendListResponse>>(API_ENDPOINTS.trends.list, {
    params: { domain, type, period, page, size },
  }));
  return {
    trends: data.content.map(toTrend),
    page: data.page,
    size: data.size,
    hasNext: data.hasNext,
    analysisWindow: data.analysisWindow,
  };
}

/**
 * 트렌드 하나의 지표와 설명을 가져옵니다.
 * 기간마다 지표가 달라 period 가 필수이고, 그 기간 지표가 없으면 지표 자리가 비어서 옵니다.
 */
export async function getTrendDetail(trendId: number, period: PeriodCode): Promise<TrendDetail> {
  return unwrap(apiClient.get<ApiResponse<TrendDetail>>(API_ENDPOINTS.trends.detail(trendId), {
    params: { period },
  }));
}

/** 기간을 일정한 칸으로 나눈 언급량입니다. 그래프를 그리는 데 씁니다. */
export async function getTrendHistory(trendId: number, period: PeriodCode): Promise<TrendHistory> {
  return unwrap(apiClient.get<ApiResponse<TrendHistory>>(API_ENDPOINTS.trends.history(trendId), {
    params: { period },
  }));
}

/** 키워드가 언급된 원본 글입니다. 최신 순이며 페이지로 나눠 옵니다. */
export async function getTrendContents(trendId: number, page = 0, size = 10): Promise<Page<TrendContent>> {
  return unwrap(apiClient.get<ApiResponse<Page<TrendContent>>>(API_ENDPOINTS.trends.contents(trendId), {
    params: { page, size },
  }));
}

/** 함께 언급된 키워드를 연관도가 높은 순서로 가져옵니다. */
export async function getTrendRelatedKeywords(trendId: number): Promise<TrendRelatedKeyword[]> {
  const data = await unwrap(
    apiClient.get<ApiResponse<TrendRelatedKeywordResponse>>(API_ENDPOINTS.trends.relatedKeywords(trendId)),
  );
  return data.relatedKeywords;
}
