import { apiClient } from '../../../api/client';
import { API_ENDPOINTS, hasEndpoint, requireEndpoint } from '../../../constants/apiEndpoints';
import type { RelatedKeyword, Trend, TrendAnalysis, TrendContent, TrendDetail, TrendFilterParams } from '../types/trend';
import { getMockRelatedContents, getMockRelatedKeywords, getMockTrendAnalysis, getMockTrendDetail, getMockTrends } from './trendMockData';

export async function getTopTrends(params?: TrendFilterParams): Promise<Trend[]> {
  if (!hasEndpoint(API_ENDPOINTS.trends.top)) return getMockTrends('top', params);
  const { data } = await apiClient.get<Trend[]>(requireEndpoint(API_ENDPOINTS.trends.top, 'getTopTrends'), { params });
  return data;
}

export async function getNewTrends(params?: TrendFilterParams): Promise<Trend[]> {
  if (!hasEndpoint(API_ENDPOINTS.trends.new)) return getMockTrends('new', params);
  const { data } = await apiClient.get<Trend[]>(requireEndpoint(API_ENDPOINTS.trends.new, 'getNewTrends'), { params });
  return data;
}

export async function getResurgingTrends(params?: TrendFilterParams): Promise<Trend[]> {
  if (!hasEndpoint(API_ENDPOINTS.trends.resurging)) return getMockTrends('rising', params);
  const { data } = await apiClient.get<Trend[]>(requireEndpoint(API_ENDPOINTS.trends.resurging, 'getResurgingTrends'), { params });
  return data;
}

export async function getRelatedTrends(params?: TrendFilterParams): Promise<Trend[]> {
  if (!hasEndpoint(API_ENDPOINTS.trends.related)) return getMockTrends('top', params);
  const { data } = await apiClient.get<Trend[]>(requireEndpoint(API_ENDPOINTS.trends.related, 'getRelatedTrends'), { params });
  return data;
}

export async function getTrendDetail(trendId: string): Promise<TrendDetail> {
  if (!hasEndpoint(API_ENDPOINTS.trends.detail)) {
    const data = getMockTrendDetail(trendId);
    if (!data) throw new Error('Trend not found.');
    return data;
  }
  const { data } = await apiClient.get<TrendDetail>(`${requireEndpoint(API_ENDPOINTS.trends.detail, 'getTrendDetail')}/${trendId}`);
  return data;
}

export async function getTrendAnalysis(trendId: string): Promise<TrendAnalysis> {
  if (!hasEndpoint(API_ENDPOINTS.trends.analysis)) return getMockTrendAnalysis(trendId);
  const { data } = await apiClient.get<TrendAnalysis>(`${requireEndpoint(API_ENDPOINTS.trends.analysis, 'getTrendAnalysis')}/${trendId}`);
  return data;
}

export async function getRelatedKeywords(trendId: string): Promise<RelatedKeyword[]> {
  if (!hasEndpoint(API_ENDPOINTS.trends.relatedKeywords)) return getMockRelatedKeywords(trendId);
  const { data } = await apiClient.get<RelatedKeyword[]>(`${requireEndpoint(API_ENDPOINTS.trends.relatedKeywords, 'getRelatedKeywords')}/${trendId}`);
  return data;
}

export async function getRelatedContents(trendId: string): Promise<TrendContent[]> {
  if (!hasEndpoint(API_ENDPOINTS.trends.relatedContents)) return getMockRelatedContents(trendId);
  const { data } = await apiClient.get<TrendContent[]>(`${requireEndpoint(API_ENDPOINTS.trends.relatedContents, 'getRelatedContents')}/${trendId}`);
  return data;
}
