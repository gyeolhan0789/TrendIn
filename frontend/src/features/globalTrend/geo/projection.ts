import type { RingGeometry } from '../data/worldAtlas';

/*
 * 지도를 그리는 두 가지 투영입니다. 둘 다 실제 경위도를 화면 좌표로 옮기기만 하고,
 * 모양을 보기 좋게 고치지 않습니다. 대륙 윤곽이 지도에서 보던 것과 같아야 하기 때문입니다.
 *
 * - 평면 지도는 웹 지도(구글 지도 등)와 같은 메르카토르입니다.
 * - 지구본은 정사투영(orthographic)입니다. 우주에서 공을 바라본 모습과 같습니다.
 */

const DEG = Math.PI / 180;

/*
 * 메르카토르는 극으로 갈수록 세로로 끝없이 늘어나 그대로 쓰면 지도가 세로로 깁니다.
 * 사람이 사는 땅이 모두 들어오는 만큼만 남겨, 가로로 넓은 화면에 맞춥니다.
 */
export const FLAT_NORTH = 79;
export const FLAT_SOUTH = -57;

function mercatorY(lat: number) {
  return Math.log(Math.tan(Math.PI / 4 + (lat * DEG) / 2));
}

const TOP_Y = mercatorY(FLAT_NORTH);
const BOTTOM_Y = mercatorY(FLAT_SOUTH);

/** 가로 폭이 정해지면 세로 높이는 투영이 정합니다. 이 비율을 어기면 나라 모양이 찌그러집니다. */
export const FLAT_ASPECT = (TOP_Y - BOTTOM_Y) / (2 * Math.PI);

export interface Point {
  x: number;
  y: number;
}

/** 경위도를 평면 지도 좌표로 옮깁니다. 지도 왼쪽 위가 (0, 0)이고 가로 폭이 width 입니다. */
export function projectFlat(lon: number, lat: number, width: number): Point {
  const clamped = Math.max(FLAT_SOUTH, Math.min(FLAT_NORTH, lat));
  return {
    x: ((lon + 180) / 360) * width,
    y: ((TOP_Y - mercatorY(clamped)) / (2 * Math.PI)) * width,
  };
}

export function flatPathOf(rings: RingGeometry[], width: number): string {
  let path = '';
  for (const ring of rings) {
    const { lonLat } = ring;
    if (lonLat.length === 0) continue;

    /*
     * 러시아와 피지처럼 날짜변경선을 넘는 나라는 경도가 +180에서 -180으로 튑니다. 거기서 선을
     * 끊으면 나라가 두 조각으로 갈라지므로, 끊는 대신 경도를 계속 이어 붙여(180을 넘어 190, 200…)
     * 한 덩어리로 그립니다. 지도는 옆으로 같은 것을 이어 붙여 그리니, 넘어간 부분은 옆 지도에서
     * 제자리에 나타납니다.
     */
    let previous = lonLat[0];
    let unwrapped = lonLat[0];
    for (let index = 0; index < lonLat.length; index += 2) {
      const lon = lonLat[index];
      if (index > 0) {
        let step = lon - previous;
        if (step > 180) step -= 360;
        else if (step < -180) step += 360;
        unwrapped += step;
        previous = lon;
      }
      const point = projectFlat(unwrapped, lonLat[index + 1], width);
      path += `${index === 0 ? 'M' : 'L'}${point.x.toFixed(1)} ${point.y.toFixed(1)}`;
    }
    path += 'Z';
  }
  return path;
}

/** 지구본을 어느 쪽에서 보는지. 경도·위도(도 단위)로 적고, 그 지점이 공의 한가운데로 옵니다. */
export interface Rotation {
  lon: number;
  lat: number;
}

export interface GlobeFrame {
  cosLon: number;
  sinLon: number;
  cosLat: number;
  sinLat: number;
  radius: number;
  cx: number;
  cy: number;
}

export function globeFrame(rotation: Rotation, radius: number, cx: number, cy: number): GlobeFrame {
  return {
    cosLon: Math.cos(rotation.lon * DEG),
    sinLon: Math.sin(rotation.lon * DEG),
    cosLat: Math.cos(rotation.lat * DEG),
    sinLat: Math.sin(rotation.lat * DEG),
    radius,
    cx,
    cy,
  };
}

export interface GlobePoint extends Point {
  /** 공의 앞면에 있는지. 뒷면 점은 테두리에 붙여 그리므로 자리는 있어도 보이지는 않습니다. */
  front: boolean;
}

/*
 * 단위벡터를 보는 방향으로 돌린 뒤 화면에 옮깁니다. 돌린 좌표의 x가 앞뒤,
 * y가 좌우, z가 위아래입니다.
 */
function projectUnit(frame: GlobeFrame, ux: number, uy: number, uz: number): GlobePoint {
  const { cosLon, sinLon, cosLat, sinLat, radius, cx, cy } = frame;
  const x1 = ux * cosLon + uy * sinLon;
  const y1 = uy * cosLon - ux * sinLon;
  const depth = x1 * cosLat + uz * sinLat;
  const up = uz * cosLat - x1 * sinLat;

  if (depth >= 0) {
    return { x: cx + radius * y1, y: cy - radius * up, front: true };
  }
  /*
   * 뒷면 점은 그대로 옮기면 앞면 안쪽으로 접혀 나라 모양이 뒤집힙니다.
   * 방향은 그대로 두고 길이만 테두리까지 늘려, 가려진 부분이 공의 가장자리를 따라가게 합니다.
   */
  const length = Math.hypot(y1, up) || 1;
  return { x: cx + (radius * y1) / length, y: cy - (radius * up) / length, front: false };
}

export function projectGlobe(frame: GlobeFrame, lon: number, lat: number): GlobePoint {
  const lonRad = lon * DEG;
  const latRad = lat * DEG;
  const cosLat = Math.cos(latRad);
  return projectUnit(frame, cosLat * Math.cos(lonRad), cosLat * Math.sin(lonRad), Math.sin(latRad));
}

/*
 * 공의 앞면에 조금이라도 걸치는 테두리만 그립니다.
 *
 * 돌릴 때마다 모든 나라의 좌표를 다시 셈하면 한 칸에 만 점이 넘어 화면이 걸립니다. 그래서 먼저
 * 테두리를 덮는 원뿔 하나로 가립니다. 뒤로 넘어갔거나 화면에서 1px도 안 되는 섬은 좌표를 아예
 * 건드리지 않습니다. 이것만으로 한 칸에 다루는 점이 절반 아래로 줄어듭니다.
 */
export function globePathOf(rings: RingGeometry[], frame: GlobeFrame): string {
  const { cosLon, sinLon, cosLat, sinLat, radius } = frame;
  let path = '';

  for (const ring of rings) {
    const { unit, capX, capY, capZ, capSin, capAngle } = ring;

    const capRotated = capX * cosLon + capY * sinLon;
    const capDepth = capRotated * cosLat + capZ * sinLat;
    if (capDepth <= -capSin) continue;
    // 한 점으로 뭉개질 섬은 그려도 보이지 않습니다.
    if (radius * capAngle < 0.6) continue;

    let visible = false;
    let body = '';
    for (let at = 0; at < unit.length; at += 3) {
      const point = projectUnit(frame, unit[at], unit[at + 1], unit[at + 2]);
      if (point.front) visible = true;
      body += `${at === 0 ? 'M' : 'L'}${Math.round(point.x)} ${Math.round(point.y)}`;
    }
    if (visible) path += `${body}Z`;
  }
  return path;
}

/** 지구본에 두르는 경선·위선입니다. 공이 돌아가는 것이 눈에 보이게 합니다. */
export function graticulePath(frame: GlobeFrame, step = 30): string {
  let path = '';

  const trace = (points: { lon: number; lat: number }[]) => {
    let open = false;
    for (const { lon, lat } of points) {
      const point = projectGlobe(frame, lon, lat);
      // 뒤로 넘어간 자리에서는 선을 끊습니다. 이어 두면 테두리를 따라 도는 줄이 남습니다.
      if (!point.front) {
        open = false;
        continue;
      }
      path += `${open ? 'L' : 'M'}${Math.round(point.x)} ${Math.round(point.y)}`;
      open = true;
    }
  };

  for (let lon = -180; lon < 180; lon += step) {
    const meridian = [];
    for (let lat = -90; lat <= 90; lat += 3) meridian.push({ lon, lat });
    trace(meridian);
  }
  for (let lat = -60; lat <= 60; lat += step) {
    const parallel = [];
    for (let lon = -180; lon <= 180; lon += 3) parallel.push({ lon, lat });
    trace(parallel);
  }
  return path;
}

export interface LonLat {
  lon: number;
  lat: number;
}

/** 두 지점을 잇는 큰 원(비행기 항로처럼 휘는 선)입니다. 확산 경로를 그릴 때 씁니다. */
export function greatCircle(from: LonLat, to: LonLat, steps = 48): LonLat[] {
  const fromLon = from.lon * DEG;
  const fromLat = from.lat * DEG;
  const toLon = to.lon * DEG;
  const toLat = to.lat * DEG;
  const cosDelta = Math.sin(fromLat) * Math.sin(toLat) + Math.cos(fromLat) * Math.cos(toLat) * Math.cos(toLon - fromLon);
  const delta = Math.acos(Math.max(-1, Math.min(1, cosDelta)));
  if (delta < 1e-6) return [from, to];

  const points: LonLat[] = [];
  for (let step = 0; step <= steps; step += 1) {
    const ratio = step / steps;
    const a = Math.sin((1 - ratio) * delta) / Math.sin(delta);
    const b = Math.sin(ratio * delta) / Math.sin(delta);
    const x = a * Math.cos(fromLat) * Math.cos(fromLon) + b * Math.cos(toLat) * Math.cos(toLon);
    const y = a * Math.cos(fromLat) * Math.sin(fromLon) + b * Math.cos(toLat) * Math.sin(toLon);
    const z = a * Math.sin(fromLat) + b * Math.sin(toLat);
    points.push({ lon: Math.atan2(y, x) / DEG, lat: Math.atan2(z, Math.hypot(x, y)) / DEG });
  }
  return points;
}
