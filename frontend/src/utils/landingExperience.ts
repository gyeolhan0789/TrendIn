export const LANDING_ANIMATION_SEEN_KEY = 'trendin:landing-animation-seen';
export const LANDING_GUIDE_SEEN_KEY = 'trendin:landing-guide-seen';

function claimOnce(storage: Pick<Storage, 'getItem' | 'setItem'>, key: string): boolean {
  if (storage.getItem(key) === 'true') return false;
  storage.setItem(key, 'true');
  return true;
}

export function claimFirstLandingAnimation(storage: Pick<Storage, 'getItem' | 'setItem'>): boolean {
  return claimOnce(storage, LANDING_ANIMATION_SEEN_KEY);
}

export function claimFirstLandingGuide(storage: Pick<Storage, 'getItem' | 'setItem'>): boolean {
  return claimOnce(storage, LANDING_GUIDE_SEEN_KEY);
}

export function resetLandingGuide(storage: Pick<Storage, 'removeItem'>): void {
  storage.removeItem(LANDING_GUIDE_SEEN_KEY);
}

export function claimFirstLandingAnimationSafely(): boolean {
  try {
    return claimFirstLandingAnimation(window.sessionStorage);
  } catch {
    return true;
  }
}

export function claimFirstLandingGuideSafely(): boolean {
  try {
    return claimFirstLandingGuide(window.sessionStorage);
  } catch {
    return true;
  }
}
