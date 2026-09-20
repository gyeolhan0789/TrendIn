const LANDING_EXPERIENCE_KEY = 'trendin:landing-experience-seen';

export function claimFirstLandingExperience(storage: Pick<Storage, 'getItem' | 'setItem'>): boolean {
  if (storage.getItem(LANDING_EXPERIENCE_KEY) === 'true') return false;
  storage.setItem(LANDING_EXPERIENCE_KEY, 'true');
  return true;
}

export function claimFirstLandingExperienceSafely(): boolean {
  try {
    return claimFirstLandingExperience(window.sessionStorage);
  } catch {
    return true;
  }
}
