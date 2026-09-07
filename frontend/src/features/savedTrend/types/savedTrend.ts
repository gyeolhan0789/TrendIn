import type { Trend } from '../../trend/types/trend';

export interface SavedTrend extends Trend {
  savedAt?: string;
}

