import { LAST_DAY, projectPoint, type Observation, type SpreadStory } from './world-data';

export const DAY_DURATION_MS = 550;
export const END_HOLD_DAYS = 2;
export function advanceFlightClock(position: number, elapsedMs: number, speed: number, startDay: number) {
  const next = position + Math.max(0, elapsedMs) / DAY_DURATION_MS * speed;
  return next >= LAST_DAY + END_HOLD_DAYS ? startDay : next;
}
export function flightAtTime(story: SpreadStory, position: number) {
  for (let index = 1; index < story.observations.length; index++) {
    const target = story.observations[index];
    const source = story.observations.find(o => o.country.id === target.parent)!;
    const departure = Math.max(source.firstDay, story.observations[index - 1].firstDay);
    if (position >= departure && position < target.firstDay) {
      const progress = (position - departure) / (target.firstDay - departure);
      return { source, target, progress, ...flightPoint(source, target, progress) };
    }
  }
  return null;
}
export function flightPoint(source: Observation, target: Observation, progress: number) {
  const a = projectPoint(source.country.lon, source.country.lat);
  const b = projectPoint(target.country.lon, target.country.lat);
  const control = { x: (a.x + b.x) / 2, y: Math.max(8, Math.min(a.y, b.y) - Math.min(115, Math.max(25, Math.abs(b.x - a.x) * .22))) };
  const t = Math.max(0, Math.min(1, progress));
  const x = (1-t)**2*a.x + 2*(1-t)*t*control.x + t*t*b.x;
  const y = (1-t)**2*a.y + 2*(1-t)*t*control.y + t*t*b.y;
  const dx = 2*(1-t)*(control.x-a.x) + 2*t*(b.x-control.x);
  const dy = 2*(1-t)*(control.y-a.y) + 2*t*(b.y-control.y);
  return { x, y, angle: Math.atan2(dy, dx) * 180 / Math.PI, path: `M ${a.x} ${a.y} Q ${control.x} ${control.y} ${b.x} ${b.y}` };
}
