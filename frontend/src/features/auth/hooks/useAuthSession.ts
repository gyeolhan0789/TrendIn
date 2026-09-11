import { useSyncExternalStore } from 'react';
import { getAuthSession, subscribeAuthSession } from '../api/authSessionStorage';

/** 로그인해 있으면 세션을, 아니면 undefined를 돌려줍니다. */
export function useAuthSession() {
  return useSyncExternalStore(subscribeAuthSession, getAuthSession);
}
