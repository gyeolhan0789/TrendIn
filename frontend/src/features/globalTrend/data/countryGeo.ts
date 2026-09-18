import { WORLD_COUNTRIES } from './worldAtlas';
import type { CountryShape } from './worldAtlas';

/*
 * 나라 코드를 지도 위의 자리로 바꿉니다.
 *
 * 서버는 나라를 ISO 3166-1 alpha-2(KR)로 알려 주는데 지도 자료는 숫자 코드(410)로 나라를
 * 가리킵니다. 둘을 잇는 표가 없으면 응답에 온 나라를 지도에서 찾을 수 없습니다.
 *
 * 국기는 코드에서 그대로 유도되고 자리는 국경선에서 계산하므로, 손으로 적어 두는 것은
 * 코드 짝과 몇몇 예외뿐입니다. 손으로 적은 값이 적을수록 틀릴 자리도 적습니다.
 */

/** alpha-2 → 지도가 쓰는 ISO 3166-1 숫자 코드. 지도에 도형이 있는 나라만 담습니다. */
const ATLAS_ID_BY_CODE: Record<string, string> = {
  // 유럽
  AL: '008', AT: '040', BA: '070', BE: '056', BG: '100', BY: '112', CH: '756', CZ: '203',
  DE: '276', DK: '208', EE: '233', ES: '724', FI: '246', FR: '250', GB: '826', GR: '300',
  HR: '191', HU: '348', IE: '372', IS: '352', IT: '380', LT: '440', LU: '442', LV: '428',
  MD: '498', ME: '499', MK: '807', NL: '528', NO: '578', PL: '616', PT: '620', RO: '642',
  RS: '688', RU: '643', SE: '752', SI: '705', SK: '703', UA: '804',
  // 아시아
  AE: '784', AF: '004', AM: '051', AZ: '031', BD: '050', BN: '096', BT: '064', CN: '156',
  CY: '196', GE: '268', ID: '360', IL: '376', IN: '356', IQ: '368', IR: '364', JO: '400',
  JP: '392', KG: '417', KH: '116', KP: '408', KR: '410', KW: '414', KZ: '398', LA: '418',
  LB: '422', LK: '144', MM: '104', MN: '496', MY: '458', NP: '524', OM: '512', PH: '608',
  PK: '586', PS: '275', QA: '634', SA: '682', SY: '760', TH: '764', TJ: '762', TL: '626',
  TM: '795', TR: '792', TW: '158', UZ: '860', VN: '704', YE: '887',
  // 아프리카
  AO: '024', BF: '854', BI: '108', BJ: '204', BW: '072', CD: '180', CF: '140', CG: '178',
  CI: '384', CM: '120', DJ: '262', DZ: '012', EG: '818', EH: '732', ER: '232', ET: '231',
  GA: '266', GH: '288', GM: '270', GN: '324', GQ: '226', GW: '624', KE: '404', LR: '430',
  LS: '426', LY: '434', MA: '504', MG: '450', ML: '466', MR: '478', MW: '454', MZ: '508',
  NA: '516', NE: '562', NG: '566', RW: '646', SD: '729', SL: '694', SN: '686', SO: '706',
  SS: '728', SZ: '748', TD: '148', TG: '768', TN: '788', TZ: '834', UG: '800', ZA: '710',
  ZM: '894', ZW: '716',
  // 북아메리카
  BS: '044', BZ: '084', CA: '124', CR: '188', CU: '192', DO: '214', GL: '304', GT: '320',
  HN: '340', HT: '332', JM: '388', MX: '484', NI: '558', PA: '591', PR: '630', SV: '222',
  TT: '780', US: '840',
  // 남아메리카
  AR: '032', BO: '068', BR: '076', CL: '152', CO: '170', EC: '218', FK: '238', GY: '328',
  PE: '604', PY: '600', SR: '740', UY: '858', VE: '862',
  // 오세아니아 · 남극
  AQ: '010', AU: '036', FJ: '242', NC: '540', NZ: '554', PG: '598', SB: '090', TF: '260',
  VU: '548',
};

/**
 * 손으로 정한 자리와 이름.
 *
 * 계산한 중심점은 대체로 맞지만, 흔히 부르는 이름이 Intl 이 주는 이름과 다른 나라가 있습니다
 * (오스트레일리아/호주). 화면에 이미 나가던 말을 바꾸지 않으려고 여기 적어 둡니다.
 */
const PINNED: Record<string, { lon: number; lat: number; name: string }> = {
  KR: { lon: 127.8, lat: 36.5, name: '대한민국' },
  JP: { lon: 138.0, lat: 37.0, name: '일본' },
  CN: { lon: 104.0, lat: 35.0, name: '중국' },
  VN: { lon: 106.0, lat: 16.0, name: '베트남' },
  TH: { lon: 101.0, lat: 15.5, name: '태국' },
  ID: { lon: 117.0, lat: -2.0, name: '인도네시아' },
  IN: { lon: 79.0, lat: 22.0, name: '인도' },
  AU: { lon: 134.0, lat: -25.0, name: '호주' },
  GB: { lon: -2.0, lat: 54.0, name: '영국' },
  FR: { lon: 2.5, lat: 46.5, name: '프랑스' },
  DE: { lon: 10.5, lat: 51.2, name: '독일' },
  IT: { lon: 12.5, lat: 42.5, name: '이탈리아' },
  ES: { lon: -3.7, lat: 40.3, name: '스페인' },
  US: { lon: -98.0, lat: 39.5, name: '미국' },
  CA: { lon: -106.0, lat: 56.0, name: '캐나다' },
  MX: { lon: -102.0, lat: 23.5, name: '멕시코' },
  BR: { lon: -51.0, lat: -12.0, name: '브라질' },
  AE: { lon: 54.0, lat: 24.0, name: '아랍에미리트' },
};

/**
 * 나라가 아닌 코드. XX 는 파이프라인이 출처 국가를 가리지 못했을 때 넣는 값이라 실제로 들어옵니다.
 * 이런 코드로 국기를 만들면 글자 두 개가 네모로 나올 뿐이라 아예 만들지 않습니다.
 */
function isPlaceholderCode(code: string): boolean {
  return code.startsWith('X') || code === 'ZZ' || /^Q[M-Z]$/.test(code);
}

const REGIONAL_INDICATOR_A = 0x1f1e6;
const LETTER_A = 65;

/** 국기는 코드 두 글자에서 그대로 만들어집니다. 나라마다 적어 둘 필요가 없습니다. */
export function flagOf(code: string): string {
  if (!/^[A-Z]{2}$/.test(code) || isPlaceholderCode(code)) return '';
  return String.fromCodePoint(
    ...Array.from(code, (letter) => REGIONAL_INDICATOR_A + letter.charCodeAt(0) - LETTER_A),
  );
}

/**
 * 날짜변경선을 넘는 테두리의 경도를 이어 붙입니다.
 *
 * 러시아나 피지처럼 180도를 걸친 나라는 한 점이 179도, 다음 점이 -179도로 적혀 있습니다.
 * 그대로 셈하면 두 점이 지구 반 바퀴 떨어진 것으로 읽혀 무게중심이 엉뚱한 바다로 갑니다.
 * 앞 점에서 180도 넘게 튀는 자리마다 360도를 더하거나 빼서 한 줄로 폅니다.
 */
function unwrapLongitudes(points: Float64Array, count: number): Float64Array {
  const lons = new Float64Array(count);
  let previous = points[0];
  lons[0] = previous;

  for (let index = 1; index < count; index++) {
    let lon = points[index * 2];
    while (lon - previous > 180) lon -= 360;
    while (lon - previous < -180) lon += 360;
    lons[index] = lon;
    previous = lon;
  }

  return lons;
}

/** 펴 놓았던 경도를 다시 -180~180 안으로 되돌립니다. */
function wrapLongitude(lon: number): number {
  return ((((lon + 180) % 360) + 360) % 360) - 180;
}

/**
 * 가장 넓은 테두리의 무게중심을 나라의 자리로 씁니다.
 *
 * 테두리를 모두 합쳐 평균을 내면 알래스카나 해외 영토 같은 외딴 조각이 핀을 끌고 가, 나라
 * 한복판이 아닌 바다를 가리키게 됩니다. 본토 하나만 보면 그런 일이 없습니다.
 */
function centroidOf(country: CountryShape): { lon: number; lat: number } | undefined {
  let best: { lon: number; lat: number; size: number } | undefined;

  for (const ring of country.rings) {
    const points = ring.lonLat;
    const count = points.length / 2;
    const lons = unwrapLongitudes(points, count);
    let doubleArea = 0;
    let lonSum = 0;
    let latSum = 0;

    for (let index = 0; index < count; index++) {
      const next = (index + 1) % count;
      const lon = lons[index];
      const lat = points[index * 2 + 1];
      const nextLon = lons[next];
      const nextLat = points[next * 2 + 1];
      const cross = lon * nextLat - nextLon * lat;
      doubleArea += cross;
      lonSum += (lon + nextLon) * cross;
      latSum += (lat + nextLat) * cross;
    }

    const area = doubleArea / 2;
    // 선 하나로 눌린 테두리는 넓이가 0이라 중심을 낼 수 없습니다.
    if (Math.abs(area) < 1e-9) continue;
    const size = Math.abs(area);
    if (best && size <= best.size) continue;
    best = { lon: lonSum / (6 * area), lat: latSum / (6 * area), size };
  }

  return best && { lon: wrapLongitude(best.lon), lat: best.lat };
}

const SHAPE_BY_ATLAS_ID = new Map(WORLD_COUNTRIES.map((country) => [country.id, country]));
/** 중심점은 나라마다 한 번만 셈하면 됩니다. 테두리 점이 수천 개인 나라가 있습니다. */
const centerCache = new Map<string, { lon: number; lat: number } | undefined>();

function centerOf(atlasId: string) {
  if (!centerCache.has(atlasId)) {
    const shape = SHAPE_BY_ATLAS_ID.get(atlasId);
    centerCache.set(atlasId, shape && centroidOf(shape));
  }
  return centerCache.get(atlasId);
}

let displayNames: Intl.DisplayNames | undefined;

/** 서버가 이름을 함께 주지만, 코드만 들고 있는 자리에서도 이름이 필요합니다. */
function nameOf(code: string): string {
  displayNames ??= new Intl.DisplayNames(['ko'], { type: 'region' });
  try {
    return displayNames.of(code) ?? code;
  } catch {
    return code;
  }
}

export interface CountryGeo {
  code: string;
  /** 지도에서 그 나라를 찾는 열쇠. */
  atlasId: string;
  name: string;
  flag: string;
  lon: number;
  lat: number;
}

/**
 * 나라 코드를 지도에 찍을 수 있는 자리로 바꿉니다.
 *
 * 지도에 도형이 없는 나라(싱가포르처럼 작은 나라)와 나라가 아닌 코드(XX)는 자리를 알 수 없어
 * undefined 입니다. 부르는 쪽은 그런 나라를 지도에서만 빼고 목록에서는 빼지 말아야 합니다.
 * 언급량은 실제로 잡힌 값이라, 지도에 못 찍는다고 없던 일이 되지 않습니다.
 */
export function countryGeoOf(code: string): CountryGeo | undefined {
  const normalized = code?.trim().toUpperCase() ?? '';
  const atlasId = ATLAS_ID_BY_CODE[normalized];
  if (!atlasId) return undefined;

  const pinned = PINNED[normalized];
  const center = pinned ?? centerOf(atlasId);
  if (!center) return undefined;

  return {
    code: normalized,
    atlasId,
    name: pinned?.name ?? nameOf(normalized),
    flag: flagOf(normalized),
    lon: center.lon,
    lat: center.lat,
  };
}
