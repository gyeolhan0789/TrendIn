export const NOTIFICATION_PAGE_SIZE = 5;
export const MAX_NOTIFICATION_COUNT = 15;

export function getNextNotificationPage(lastPage: { page: number; hasNext: boolean }) {
  const loadedCount = (lastPage.page + 1) * NOTIFICATION_PAGE_SIZE;
  return lastPage.hasNext && loadedCount < MAX_NOTIFICATION_COUNT ? lastPage.page + 1 : undefined;
}
