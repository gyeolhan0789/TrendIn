import packed from './worldAtlas.json';
import continents from './worldContinents.json';

/*
 * 세계 지도의 실제 국경선입니다. Natural Earth 1:110m 자료(world-atlas)를 그대로 옮겼고,
 * 대륙과 나라 모양이 지도에서 보던 것과 같아야 해서 손으로 그린 도형은 쓰지 않습니다.
 *
 * 다만 원본 GeoJSON 은 400KB가 넘어 화면에 싣기 무겁습니다. 그래서 좌표를 0.1도(약 11km)로
 * 줄여 정수로 만들고, 앞 점과의 차이만 5비트씩 끊어 글자로 적어 24KB로 담았습니다.
 * 0.1도는 1440px 너비 지도에서 0.4px이라 눈으로는 차이가 나지 않습니다.
 */

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-';

const CODE_OF = new Map<string, number>(Array.from(ALPHABET, (char, index) => [char, index]));

/** 한 나라의 테두리 하나. 경도·위도를 번갈아 담은 납작한 배열입니다. */
export type Ring = Float64Array;

/** 지도를 돌릴 때마다 삼각함수를 다시 부르지 않도록, 점마다 단위 구면 위 위치를 미리 구해 둡니다. */
export interface RingGeometry {
  /** 경도·위도(도 단위)를 번갈아 담습니다. 평면 지도가 씁니다. */
  lonLat: Float64Array;
  /** 같은 순서의 [x, y, z] 단위벡터. 지구본이 씁니다. */
  unit: Float64Array;
  /*
   * 이 테두리를 덮는 가장 작은 원뿔. 지구본을 돌릴 때 뒤로 넘어간 나라를 점 하나로 먼저 걸러내어,
   * 보이지도 않을 테두리의 좌표 수천 개를 매 칸마다 다시 셈하지 않게 합니다.
   */
  capX: number;
  capY: number;
  capZ: number;
  /** 원뿔의 반각의 사인. 앞면에 조금이라도 걸치는지 이 값 하나로 가립니다. */
  capSin: number;
  /** 원뿔의 반각(라디안). 화면에서 몇 px 로 보일지 어림하는 데 씁니다. */
  capAngle: number;
}

/*
 * 대륙 일곱 갈래. 지도에 칠할 색을 이 갈래로 나누므로, 자료에도 같은 순서로 적어 둡니다.
 * 나라마다 어느 대륙인지는 Natural Earth 의 CONTINENT 값을 그대로 옮겼습니다.
 */
export const CONTINENTS = ['AS', 'EU', 'AF', 'NA', 'SA', 'OC', 'AN'] as const;

export type Continent = (typeof CONTINENTS)[number];

export interface CountryShape {
  /** ISO 3166-1 숫자 코드. world-atlas 가 나라를 가리키는 값입니다. */
  id: string;
  continent: Continent;
  rings: RingGeometry[];
}

function decodeRing(text: string): Float64Array {
  const deltas: number[] = [];
  let cursor = 0;
  while (cursor < text.length) {
    let shift = 0;
    let result = 0;
    let chunk = 0;
    do {
      chunk = CODE_OF.get(text[cursor]) ?? 0;
      cursor += 1;
      result |= (chunk & 31) << shift;
      shift += 5;
    } while (chunk & 32);
    // 부호는 지그재그로 담겨 있습니다. 홀수면 음수입니다.
    deltas.push(result & 1 ? ~(result >>> 1) : result >>> 1);
  }

  // 경도·위도 각각 앞 점과의 차이라, 번갈아 더해 원래 값으로 되돌립니다.
  const lonLat = new Float64Array(deltas.length);
  let lon = 0;
  let lat = 0;
  for (let index = 0; index < deltas.length; index += 2) {
    lon += deltas[index];
    lat += deltas[index + 1];
    lonLat[index] = lon / 10;
    lonLat[index + 1] = lat / 10;
  }
  return lonLat;
}

function toUnitVectors(lonLat: Float64Array): Float64Array {
  const unit = new Float64Array((lonLat.length / 2) * 3);
  for (let index = 0, at = 0; index < lonLat.length; index += 2, at += 3) {
    const lon = (lonLat[index] * Math.PI) / 180;
    const lat = (lonLat[index + 1] * Math.PI) / 180;
    const cosLat = Math.cos(lat);
    unit[at] = cosLat * Math.cos(lon);
    unit[at + 1] = cosLat * Math.sin(lon);
    unit[at + 2] = Math.sin(lat);
  }
  return unit;
}

/** 테두리를 덮는 원뿔을 구합니다. 점들의 평균 방향을 축으로 삼고, 가장 먼 점까지를 반각으로 둡니다. */
function capOf(unit: Float64Array) {
  let x = 0;
  let y = 0;
  let z = 0;
  for (let at = 0; at < unit.length; at += 3) {
    x += unit[at];
    y += unit[at + 1];
    z += unit[at + 2];
  }
  const length = Math.hypot(x, y, z) || 1;
  x /= length;
  y /= length;
  z /= length;

  let smallest = 1;
  for (let at = 0; at < unit.length; at += 3) {
    const dot = x * unit[at] + y * unit[at + 1] + z * unit[at + 2];
    if (dot < smallest) smallest = dot;
  }
  const angle = Math.acos(Math.max(-1, Math.min(1, smallest)));
  return { capX: x, capY: y, capZ: z, capSin: Math.sin(angle), capAngle: angle };
}

function buildCountries(): CountryShape[] {
  const where = continents as Record<string, Continent>;
  return Object.entries(packed as Record<string, string>).map(([id, body]) => ({
    id,
    // 대륙을 모르는 땅은 남극 쪽 무채색으로 둡니다. 색이 없어 빠지는 것보다 낫습니다.
    continent: where[id] ?? 'AN',
    rings: body.split('|').map((text) => {
      const lonLat = decodeRing(text);
      const unit = toUnitVectors(lonLat);
      return { lonLat, unit, ...capOf(unit) };
    }),
  }));
}

/* 자료를 푸는 일은 한 번이면 됩니다. 화면이 다시 그려질 때마다 되풀이하지 않도록 모듈에 담아 둡니다. */
export const WORLD_COUNTRIES: CountryShape[] = buildCountries();
