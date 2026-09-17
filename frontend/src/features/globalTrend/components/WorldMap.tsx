import { useEffect, useMemo, useRef, useState } from 'react';
import { CONTINENTS, WORLD_COUNTRIES } from '../data/worldAtlas';
import {
  FLAT_ASPECT,
  flatPathOf,
  globeFrame,
  globePathOf,
  graticulePath,
  greatCircle,
  projectFlat,
  projectGlobe,
} from '../geo/projection';
import type { Country } from '../globalTrendSample';
import type { MapView } from '../hooks/useSpreadTour';

/*
 * 세계 지도입니다. 지구본과 평면 지도 두 모양이 있고, 둘 다 같은 국경 자료를 씁니다.
 *
 * 평면 지도의 길은 배율이 달라져도 변하지 않으므로 기준 폭으로 한 번만 그려 두고, 확대·이동은
 * SVG 변환으로 처리합니다. 지구본은 돌릴 때마다 보이는 면이 달라져 매번 다시 그립니다.
 */

export type MapMode = 'globe' | 'flat';

const REFERENCE_WIDTH = 1000;

/*
 * 땅은 대륙별로 나눠 칠합니다. 나라마다 path 를 따로 두면 지구본을 돌릴 때 175개를 매번 다시
 * 그려야 해서, 같은 색으로 칠할 것끼리 path 하나에 이어 붙입니다.
 */
const BY_CONTINENT = CONTINENTS.map((continent) => ({
  continent,
  countries: WORLD_COUNTRIES.filter((country) => country.continent === continent),
})).filter((group) => group.countries.length > 0);

/*
 * 평면 지도에서는 남극을 뺍니다. 메르카토르는 극으로 갈수록 끝없이 늘어나 남위 57도에서 자르는데,
 * 남극은 그보다 아래라 잘린 자리에 띠 하나로 눌려 붙습니다. 대륙 모양도 아니고 트렌드도 없는 띠입니다.
 */
const FLAT_LAND = BY_CONTINENT.filter((group) => group.continent !== 'AN').map((group) => ({
  continent: group.continent,
  path: group.countries.map((country) => flatPathOf(country.rings, REFERENCE_WIDTH)).join(''),
}));

/*
 * 이어 붙일 지도는 늘 두 장으로 둡니다. 기준 자리가 화면 왼쪽 바로 바깥(-worldWidth ~ 0)이고
 * 지도 폭은 화면보다 넓으니, 두 장이면 어떤 자리에서도 화면을 덮습니다. 필요한 만큼만 그리려고
 * 장수를 바꾸면 배율이 바뀌는 순간 큰 path 가 붙었다 떨어져 그 한 칸에서 움직임이 걸립니다.
 */
const FLAT_COPIES = [0, 1];

const FLAT_BY_ID = new Map(WORLD_COUNTRIES.map((country) => [country.id, flatPathOf(country.rings, REFERENCE_WIDTH)]));

const SHAPE_BY_ID = new Map(WORLD_COUNTRIES.map((country) => [country.id, country]));

export interface MapStop {
  country: Country;
  growth: number;
  since: string;
}

interface WorldMapProps {
  mode: MapMode;
  view: MapView;
  stops: MapStop[];
  /** 지금 향하고 있는 자리. 여기까지의 경로만 선으로 잇습니다. */
  focusIndex: number;
  /** 이미 닿아서 머무르고 있는 자리. 이름표를 펼쳐 보여 줍니다. */
  stopIndex: number;
  onPickStop: (index: number) => void;
}

function useElementSize() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return [ref, size] as const;
}

interface Placed {
  index: number;
  stop: MapStop;
  x: number;
  y: number;
  visible: boolean;
}

/* 같은 자리가 이어 붙인 지도마다 나오므로, 화면 가운데에 가장 가까운 것 하나만 골라 표시를 답니다. */
function nearestX(x: number, worldWidth: number, viewportWidth: number) {
  let best = x;
  for (let copy = -1; copy <= 2; copy += 1) {
    const candidate = x + copy * worldWidth;
    if (Math.abs(candidate - viewportWidth / 2) < Math.abs(best - viewportWidth / 2)) best = candidate;
  }
  return best;
}

function markerClass(index: number, focusIndex: number, stopIndex: number) {
  if (index === stopIndex) return 'worldmap-pin is-here';
  if (index <= focusIndex) return 'worldmap-pin is-passed';
  return 'worldmap-pin';
}

export function WorldMap({ mode, view, stops, focusIndex, stopIndex, onPickStop }: WorldMapProps) {
  const [ref, size] = useElementSize();
  const { width, height } = size;
  const ready = width > 0 && height > 0;

  const globe = useMemo(() => {
    if (!ready || mode !== 'globe') return null;
    const radius = Math.min(width, height) * 0.44 * view.zoom;
    const frame = globeFrame({ lon: view.lon, lat: view.lat }, radius, width / 2, height / 2);
    return {
      radius,
      frame,
      land: BY_CONTINENT.map((group) => ({
        continent: group.continent,
        path: group.countries.map((country) => globePathOf(country.rings, frame)).join(''),
      })),
      graticule: graticulePath(frame),
    };
  }, [ready, mode, width, height, view.lon, view.lat, view.zoom]);

  const flat = useMemo(() => {
    if (!ready || mode !== 'flat') return null;
    /* 지도가 칸을 가득 덮게 맞춥니다. 세로로 맞추면 위아래에 빈 띠가 남아 지도가 떠 보입니다. */
    const fitWidth = Math.max(width, height / FLAT_ASPECT);
    const worldWidth = fitWidth * view.zoom;
    const worldHeight = worldWidth * FLAT_ASPECT;
    const center = projectFlat(view.lon, view.lat, worldWidth);
    /*
     * 가로로는 지도를 붙들지 않고 옆에 같은 지도를 이어 붙입니다. 웹 지도가 그렇듯 날짜변경선에서
     * 끊기지 않아야, 서울에서 상파울루로 갈 때 태평양을 건너는 동안 화면이 멈추지 않습니다.
     * 기준 자리는 화면 왼쪽 바로 바깥에 두고, 화면을 덮을 만큼만 오른쪽으로 더 깝니다.
     */
    const raw = width / 2 - center.x;
    const offsetX = ((raw % worldWidth) + worldWidth) % worldWidth - worldWidth;
    /* 세로는 위아래가 끝이라 그대로 붙들어, 바다 밖으로 넘어가지 않게 합니다. */
    const offsetY = worldHeight <= height
      ? (height - worldHeight) / 2
      : Math.min(0, Math.max(height - worldHeight, height / 2 - center.y));
    return { worldWidth, worldHeight, offsetX, offsetY, scale: worldWidth / REFERENCE_WIDTH };
  }, [ready, mode, width, height, view.lon, view.lat, view.zoom]);


  const placed: Placed[] = useMemo(() => {
    if (!ready) return [];
    return stops.map((stop, index) => {
      if (mode === 'globe' && globe) {
        const point = projectGlobe(globe.frame, stop.country.lon, stop.country.lat);
        return { index, stop, x: point.x, y: point.y, visible: point.front };
      }
      if (flat) {
        const point = projectFlat(stop.country.lon, stop.country.lat, flat.worldWidth);
        const x = nearestX(flat.offsetX + point.x, flat.worldWidth, width);
        const y = flat.offsetY + point.y;
        return { index, stop, x, y, visible: x > -40 && x < width + 40 && y > -40 && y < height + 40 };
      }
      return { index, stop, x: 0, y: 0, visible: false };
    });
  }, [ready, stops, mode, globe, flat, width, height]);

  /* 지나온 길입니다. 아직 닿지 않은 구간은 그리지 않아, 선이 늘어나며 따라오는 것처럼 보입니다. */
  const legs = useMemo(() => {
    const drawn: { key: string; path: string; active: boolean }[] = [];
    const last = Math.min(focusIndex, stops.length - 1);
    for (let index = 1; index <= last; index += 1) {
      const from = stops[index - 1].country;
      const to = stops[index].country;
      const key = `${from.code}-${to.code}`;
      const active = index === focusIndex;

      if (mode === 'globe' && globe) {
        let path = '';
        let open = false;
        for (const point of greatCircle(from, to)) {
          const screen = projectGlobe(globe.frame, point.lon, point.lat);
          if (!screen.front) {
            open = false;
            continue;
          }
          path += `${open ? 'L' : 'M'}${screen.x.toFixed(1)} ${screen.y.toFixed(1)}`;
          open = true;
        }
        if (path) drawn.push({ key, path, active });
        continue;
      }

      if (flat) {
        const start = projectFlat(from.lon, from.lat, flat.worldWidth);
        const end = projectFlat(to.lon, to.lat, flat.worldWidth);
        const sx = nearestX(flat.offsetX + start.x, flat.worldWidth, width);
        const sy = flat.offsetY + start.y;
        /* 도착 자리도 여러 번 나오므로, 출발 자리에서 가장 가까운 것으로 이어 태평양을 건너게 합니다. */
        let ex = flat.offsetX + end.x;
        while (ex - sx > flat.worldWidth / 2) ex -= flat.worldWidth;
        while (sx - ex > flat.worldWidth / 2) ex += flat.worldWidth;
        const ey = flat.offsetY + end.y;
        // 두 점 사이를 곧게 이으면 지도에 눌러 붙어 보여, 위로 살짝 띄운 곡선으로 잇습니다.
        const lift = Math.hypot(ex - sx, ey - sy) * 0.22;
        drawn.push({
          key,
          path: `M${sx.toFixed(1)} ${sy.toFixed(1)} Q${((sx + ex) / 2).toFixed(1)} ${((sy + ey) / 2 - lift).toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`,
          active,
        });
      }
    }
    return drawn;
  }, [stops, focusIndex, mode, globe, flat, width]);

  /*
   * 트렌드가 닿은 나라는 그 나라의 증가율만큼 진하게 칠합니다. 같은 색으로 모두 덮으면
   * 어디가 더 뜨거운지 지도에서 읽을 수 없습니다. 가장 높은 곳을 1로 두고 견줍니다.
   */
  const hottest = Math.max(...stops.map((stop) => Math.abs(stop.growth)), 1);

  const highlights = stops.map((stop, index) => ({
    index,
    id: stop.country.atlasId,
    passed: index <= focusIndex,
    here: index === stopIndex,
    depth: 0.32 + 0.53 * (Math.abs(stop.growth) / hottest),
  }));

  return (
    <div className={`worldmap worldmap--${mode}`} ref={ref}>
      {ready && (
        <svg className="worldmap-canvas" width={width} height={height} role="img" aria-label="국가별 관심도 지도">
          <defs>
            <radialGradient id="worldmap-ocean" cx="35%" cy="32%" r="78%">
              <stop offset="0%" stopColor="#c3dcf7" />
              <stop offset="50%" stopColor="#7ba6da" />
              <stop offset="100%" stopColor="#2f4a7d" />
            </radialGradient>
            {/* 지금 머무르는 나라를 채우는 빛깔. 한 가지 색으로 덮는 것보다 부드럽게 도드라집니다. */}
            <linearGradient id="worldmap-here" x1="0" y1="0" x2="0.4" y2="1">
              <stop offset="0%" stopColor="#6366F1" />
              <stop offset="100%" stopColor="#A855F7" />
            </linearGradient>
            {/* 공 둘레의 빛무리. 흐림 효과(blur)는 돌릴 때마다 다시 계산해 화면이 걸리므로, 가장자리만 옅어지는 그러데이션으로 냅니다. */}
            <radialGradient id="worldmap-glow">
              <stop offset="72%" stopColor="rgba(99,102,241,0)" />
              <stop offset="88%" stopColor="rgba(99,102,241,0.22)" />
              <stop offset="100%" stopColor="rgba(99,102,241,0)" />
            </radialGradient>
            <radialGradient id="worldmap-shade" cx="35%" cy="32%" r="80%">
              <stop offset="55%" stopColor="rgba(0,0,0,0)" />
              <stop offset="100%" stopColor="rgba(12,24,58,0.42)" />
            </radialGradient>
          </defs>

          {mode === 'globe' && globe && (
            <g>
              {/* 공 가장자리가 화면 안에 있을 때만 빛무리를 냅니다. 바싹 다가가면 어차피 화면 밖입니다. */}
              {globe.radius < Math.max(width, height) && (
                <circle cx={width / 2} cy={height / 2} r={globe.radius * 1.16} fill="url(#worldmap-glow)" />
              )}
              <circle cx={width / 2} cy={height / 2} r={globe.radius} fill="url(#worldmap-ocean)" />
              <path className="worldmap-graticule" d={globe.graticule} />
              {globe.land.map((group) => (
                <path key={group.continent} className={`worldmap-land worldmap-land--${group.continent}`} d={group.path} />
              ))}
              {highlights.map((highlight) => {
                const shape = SHAPE_BY_ID.get(highlight.id);
                if (!shape || !highlight.passed) return null;
                return (
                  <path
                    key={highlight.id}
                    className={`worldmap-hit ${highlight.here ? 'is-here' : ''}`}
                    fillOpacity={highlight.here ? 1 : highlight.depth}
                    d={globePathOf(shape.rings, globe.frame)}
                  />
                );
              })}
              <circle cx={width / 2} cy={height / 2} r={globe.radius} fill="url(#worldmap-shade)" pointerEvents="none" />
            </g>
          )}

          {mode === 'flat' && flat && (
            <g>
              <rect className="worldmap-sea" x="0" y="0" width={width} height={height} />
              {/* 화면을 덮을 만큼 같은 지도를 옆으로 이어 붙입니다. 날짜변경선에서 땅이 잘리지 않습니다. */}
              {FLAT_COPIES.map((copy) => (
                <g
                  key={copy}
                  strokeWidth={1 / flat.scale}
                  transform={`translate(${(flat.offsetX + copy * flat.worldWidth).toFixed(2)} ${flat.offsetY.toFixed(2)}) scale(${flat.scale.toFixed(5)})`}
                >
                  {FLAT_LAND.map((group) => (
                    <path key={group.continent} className={`worldmap-land worldmap-land--${group.continent}`} d={group.path} />
                  ))}
                  {highlights.map((highlight) => {
                    const path = FLAT_BY_ID.get(highlight.id);
                    if (!path || !highlight.passed) return null;
                    return (
                      <path
                        key={highlight.id}
                        className={`worldmap-hit ${highlight.here ? 'is-here' : ''}`}
                        fillOpacity={highlight.here ? 1 : highlight.depth}
                        d={path}
                      />
                    );
                  })}
                </g>
              ))}
            </g>
          )}

          <g className="worldmap-legs">
            {legs.map((leg) => (
              <path key={leg.key} className={`worldmap-leg ${leg.active ? 'is-active' : ''}`} d={leg.path} />
            ))}
          </g>
        </svg>
      )}

      {placed.map((pin) => (pin.visible ? (
        <button
          type="button"
          key={pin.stop.country.code}
          className={markerClass(pin.index, focusIndex, stopIndex)}
          style={{ left: `${pin.x}px`, top: `${pin.y}px` }}
          onClick={() => onPickStop(pin.index)}
        >
          <span className="worldmap-pin-dot" aria-hidden="true" />
          <span className="worldmap-pin-label">
            <span className="worldmap-pin-name">{pin.stop.country.flag} {pin.stop.country.name}</span>
            <span className="worldmap-pin-figures">
              <span className="worldmap-pin-growth">{pin.stop.growth > 0 ? '+' : ''}{pin.stop.growth}%</span>
              <span className="worldmap-pin-date">{pin.stop.since}부터</span>
            </span>
          </span>
        </button>
      ) : null))}
    </div>
  );
}
