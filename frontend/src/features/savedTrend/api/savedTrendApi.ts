import { apiClient } from '../../../api/client';
import { API_ENDPOINTS, hasEndpoint, requireEndpoint } from '../../../constants/apiEndpoints';
import type { SavedTrend } from '../types/savedTrend';
import { getMockAllTrends, getMockTrendDetail } from '../../trend/api/trendMockData';

const mockPreferenceKey = 'ahead-demo-preferences-v1';

function readMockSavedIds(): string[] {
  try {
    const raw = window.localStorage.getItem(mockPreferenceKey);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || !('saved' in parsed) || !Array.isArray(parsed.saved)) return [];
    return parsed.saved.filter((id): id is string => typeof id === 'string');
  } catch {
    return [];
  }
}

function writeMockSavedIds(saved: string[]) {
  try {
    const raw = window.localStorage.getItem(mockPreferenceKey);
    const current: Record<string, unknown> = raw ? JSON.parse(raw) : {};
    window.localStorage.setItem(mockPreferenceKey, JSON.stringify({ ...current, saved }));
  } catch {
    // Device-local storage may be unavailable in private browsing.
  }
}

function getMockSavedTrends(): SavedTrend[] {
  const trends = getMockAllTrends();
  return readMockSavedIds().map((id) => trends.find((trend) => trend.trendId === id)).filter((trend): trend is SavedTrend => Boolean(trend));
}

export async function saveTrend(trendId: string): Promise<SavedTrend> {
  if (!hasEndpoint(API_ENDPOINTS.savedTrends.save)) {
    const trend = getMockTrendDetail(trendId);
    if (!trend) throw new Error('Trend not found.');
    const saved = [...new Set([...readMockSavedIds(), trendId])];
    writeMockSavedIds(saved);
    return { ...trend, savedAt: new Date().toISOString() };
  }
  const { data } = await apiClient.post<SavedTrend>(requireEndpoint(API_ENDPOINTS.savedTrends.save, 'saveTrend'), { trendId });
  return data;
}

export async function getSavedTrends(): Promise<SavedTrend[]> {
  if (!hasEndpoint(API_ENDPOINTS.savedTrends.list)) return getMockSavedTrends();
  const { data } = await apiClient.get<SavedTrend[]>(requireEndpoint(API_ENDPOINTS.savedTrends.list, 'getSavedTrends'));
  return data;
}

export async function deleteSavedTrend(trendId: string): Promise<void> {
  if (!hasEndpoint(API_ENDPOINTS.savedTrends.delete)) {
    writeMockSavedIds(readMockSavedIds().filter((id) => id !== trendId));
    return;
  }
  await apiClient.delete(`${requireEndpoint(API_ENDPOINTS.savedTrends.delete, 'deleteSavedTrend')}/${trendId}`);
}
