import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { CONTINENTS, WORLD_COUNTRIES } from '../data/worldAtlas';
import {
  FLAT_ASPECT,
  flatPathOf,
  globeFrame,
  globePathOf,
  graticulePath,
  greatCircle,
  greatCirclePoint,
  projectFlat,
  projectGlobe,
  unprojectFlat,
} from '../geo/projection';
import type { GlobeFrame, LonLat } from '../geo/projection';
import type { CountryGeo } from '../data/countryGeo';
import { MAX_ZOOM, MIN_ZOOM } from '../hooks/useSpreadTour';
import type { MapView } from '../hooks/useSpreadTour';

/*
 * 세계 지도입니다. 지구본과 평면 지도 두 모양이 있고, 둘 다 같은 국경 자료를 씁니다.
 *
 * 평면 지도의 길은 배율이 달라져도 변하지 않으므로 기준 폭으로 한 번만 그려 두고, 확대·이동은
 * SVG 변환으로 처리합니다. 지구본은 돌릴 때마다 보이는 면이 달라져 매번 다시 그립니다.
 *
 * 휠로 배율을 바꾸고 끌어서 옮길 수 있습니다. 어느 쪽이든 바꾸는 것은 보는 자리(view) 하나뿐이라,
 * 지구본에서 돌려 놓은 자리가 평면 지도로 바꿔도 그대로 이어집니다.
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
  country: CountryGeo;
  /** 핀을 얼마나 진하게 칠할지 정하는 값. 클수록 진합니다. */
  weight: number;
  /** 핀에 적을 값. 무엇을 재는 값인지 아는 쪽에서 다듬어 넘깁니다. */
  label: string;
  /** 그 나라에서 처음 잡힌 날. */
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
  /** 비행기가 구간을 얼마나 지났는지(0~1). null 이면 띄우지 않습니다. */
  legProgress: number | null;
  /** 휠·끌기로 보는 자리를 손수 바꿀 때 부릅니다. 없으면 지도는 따라가기만 합니다. */
  onSteer?: (update: (view: MapView) => MapView) => void;
}

const DEGREES = 180 / Math.PI;

/*
 * 경로를 따라가는 비행기입니다. 기수 방향은 앞뒤로 조금 떨어진 두 자리를 이어 정합니다.
 * 한 자리만 보면 어느 쪽으로 가는지 알 수 없고, 도착 직전에 진행도가 1에 닿으면 앞의 자리가
 * 겹쳐 기수가 엉뚱한 데를 봅니다.
 */
const HEADING_GAP = 0.02;

interface Plane {
  x: number;
  y: number;
  /** 화면에서 기수가 향할 방향(도). 0이 오른쪽입니다. */
  angle: number;
}

function globePlane(frame: GlobeFrame, from: LonLat, to: LonLat, progress: number): Plane | null {
  const at = greatCirclePoint(from, to, progress);
  const screen = projectGlobe(frame, at.lon, at.lat);
  // 공의 뒤로 돌아간 구간은 선도 끊어 두므로 비행기도 감춥니다.
  if (!screen.front) return null;

  const back = greatCirclePoint(from, to, Math.max(0, progress - HEADING_GAP));
  const fore = greatCirclePoint(from, to, Math.min(1, progress + HEADING_GAP));
  const tail = projectGlobe(frame, back.lon, back.lat);
  const nose = projectGlobe(frame, fore.lon, fore.lat);
  return { x: screen.x, y: screen.y, angle: Math.atan2(nose.y - tail.y, nose.x - tail.x) * DEGREES };
}

/** 평면 지도의 경로는 위로 띄운 2차 곡선입니다. 그 위의 자리와 접선을 그대로 셈합니다. */
function curvePlane(sx: number, sy: number, mx: number, my: number, ex: number, ey: number, progress: number): Plane {
  const rest = 1 - progress;
  return {
    x: rest * rest * sx + 2 * rest * progress * mx + progress * progress * ex,
    y: rest * rest * sy + 2 * rest * progress * my + progress * progress * ey,
    angle: Math.atan2(
      2 * (rest * (my - sy) + progress * (ey - my)),
      2 * (rest * (mx - sx) + progress * (ex - mx)),
    ) * DEGREES,
  };
}

/*
 * 비행기 모양. 24×24 칸에 기수가 위(북)를 보게 그려져 있고 가운데가 (11.5, 12) 입니다.
 * 그래서 가는 방향에 90도를 더해 돌립니다.
 */
const PLANE_PATH = 'M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z';
/** 배율과 무관하게 화면에서 늘 같은 크기입니다. 확대했다고 비행기가 나라를 덮으면 안 됩니다. */
const PLANE_SCALE = 2.25;

/** 한 번 휠을 굴릴 때 바뀌는 배율. 값이 크면 한 칸에 훌쩍 넘어가 어디를 보고 있었는지 놓칩니다. */
const WHEEL_STEP = 0.0016;

/** 줄 단위·쪽 단위로 오는 휠도 있어, 모두 픽셀로 맞춰 읽습니다. */
function wheelPixels(event: WheelEvent, height: number) {
  if (event.deltaMode === 1) return event.deltaY * 16;
  if (event.deltaMode === 2) return event.deltaY * height;
  return event.deltaY;
}

function globeRadiusOf(zoom: number, width: number, height: number) {
  return Math.min(width, height) * 0.44 * zoom;
}

interface FlatLayout {
  /** 배율 1일 때의 지도 폭. 휠로 배율만 바꿔 다시 셈할 때 기준이 됩니다. */
  fitWidth: number;
  worldWidth: number;
  worldHeight: number;
  offsetX: number;
  offsetY: number;
  scale: number;
}

function flatLayoutOf(view: MapView, width: number, height: number): FlatLayout {
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
  return { fitWidth, worldWidth, worldHeight, offsetX, offsetY, scale: worldWidth / REFERENCE_WIDTH };
}

/*
 * 평면 지도에서 화면 가운데에 둘 자리를 경위도로 돌려 줍니다. 세로는 지도 밖이 나오지 않는
 * 만큼만 받습니다. 가두지 않으면 아래로 계속 끌 때 보이는 것은 그대로인데 값만 쌓여,
 * 되돌릴 때 한참을 헛끌게 됩니다.
 */
function flatCenterOf(layout: { worldWidth: number; worldHeight: number }, height: number, x: number, y: number) {
  const settledY = layout.worldHeight <= height
    ? layout.worldHeight / 2
    : Math.min(Math.max(y, height / 2), layout.worldHeight - height / 2);
  return unprojectFlat(x, settledY, layout.worldWidth);
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

export function WorldMap({ mode, view, stops, focusIndex, stopIndex, legProgress, onPickStop, onSteer }: WorldMapProps) {
  const [ref, size] = useElementSize();
  const { width, height } = size;
  const ready = width > 0 && height > 0;

  const globe = useMemo(() => {
    if (!ready || mode !== 'globe') return null;
    const radius = globeRadiusOf(view.zoom, width, height);
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

  const flat = useMemo(
    () => (ready && mode === 'flat' ? flatLayoutOf(view, width, height) : null),
    [ready, mode, width, height, view],
  );

  /*
   * 휠과 끌기를 받는 자리입니다. 화면 크기와 모드만 붙들어 두고 지도 배치는 그때의 view 로 다시
   * 셈합니다. 휠과 포인터는 한 칸에 여러 번 들어와 그리기보다 앞서므로, 지난 칸의 배치로 셈하면
   * 커서가 짚은 자리가 조금씩 밀립니다.
   */
  const sceneRef = useRef({ mode, width, height });
  sceneRef.current = { mode, width, height };

  const panBy = useCallback((dx: number, dy: number) => {
    if (!onSteer) return;
    onSteer((current) => {
      const scene = sceneRef.current;
      if (scene.mode === 'globe') {
        /* 공 한가운데에서 1px 은 반지름분의 1 라디안입니다. 이만큼 돌려야 짚은 땅이 손끝을 따라옵니다. */
        const perPixel = (180 / Math.PI) / Math.max(1, globeRadiusOf(current.zoom, scene.width, scene.height));
        return { ...current, lon: current.lon - dx * perPixel, lat: current.lat + dy * perPixel };
      }
      const layout = flatLayoutOf(current, scene.width, scene.height);
      const center = projectFlat(current.lon, current.lat, layout.worldWidth);
      const moved = flatCenterOf(layout, scene.height, center.x - dx, center.y - dy);
      return { ...current, lon: moved.lon, lat: moved.lat };
    });
  }, [onSteer]);

  /** 커서가 짚은 자리를 붙든 채 배율만 바꿉니다. 가운데만 보고 키우면 보려던 나라가 화면 밖으로 밀려납니다. */
  const zoomAt = useCallback((factor: number, px: number, py: number) => {
    if (!onSteer) return;
    onSteer((current) => {
      const scene = sceneRef.current;
      const zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, current.zoom * factor));
      // 지구본은 공을 가운데 둔 채 크기만 바꿉니다. 짚은 자리를 붙들면 공이 화면 밖으로 굴러 나갑니다.
      if (scene.mode === 'globe') return { ...current, zoom };

      const layout = flatLayoutOf(current, scene.width, scene.height);
      const under = unprojectFlat(
        px - layout.offsetX,
        Math.min(Math.max(py - layout.offsetY, 0), layout.worldHeight),
        layout.worldWidth,
      );
      const worldWidth = layout.fitWidth * zoom;
      const next = { worldWidth, worldHeight: worldWidth * FLAT_ASPECT };
      const point = projectFlat(under.lon, under.lat, worldWidth);
      /* 바뀐 배율에서도 그 자리가 커서 밑에 남으려면, 가운데는 커서에서 떨어진 만큼 옆으로 갑니다. */
      const center = flatCenterOf(next, scene.height, point.x + scene.width / 2 - px, point.y + scene.height / 2 - py);
      return { lon: center.lon, lat: center.lat, zoom };
    });
  }, [onSteer]);

  /*
   * 휠은 React 가 거는 자리가 passive 라 거기서는 페이지 스크롤을 막을 수 없습니다. 지도 위에서
   * 굴렸는데 뒤에서 페이지까지 같이 내려가지 않도록, 여기서 직접 겁니다.
   */
  useEffect(() => {
    const element = ref.current;
    if (!element || !onSteer) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      zoomAt(
        Math.exp(-wheelPixels(event, rect.height) * WHEEL_STEP),
        event.clientX - rect.left,
        event.clientY - rect.top,
      );
    };
    element.addEventListener('wheel', onWheel, { passive: false });
    return () => element.removeEventListener('wheel', onWheel);
  }, [ref, onSteer, zoomAt]);

  const dragRef = useRef<{ pointerId: number; x: number; y: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    // 핀은 눌러서 고르는 것이라 끌기로 가져가지 않습니다.
    if (!onSteer || event.button !== 0 || (event.target as HTMLElement).closest('button')) return;
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    /* 손이 지도 밖으로 나가도 끌기가 이어지게 포인터를 붙잡아 둡니다. */
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  };

  const moveDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (dx === 0 && dy === 0) return;
    drag.x = event.clientX;
    drag.y = event.clientY;
    panBy(dx, dy);
  };

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

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
    /* 비행기는 지금 건너고 있는 한 구간에만 띄웁니다. */
    let plane: Plane | null = null;
    const last = Math.min(focusIndex, stops.length - 1);
    for (let index = 1; index <= last; index += 1) {
      const from = stops[index - 1].country;
      const to = stops[index].country;
      const key = `${from.code}-${to.code}`;
      const active = index === focusIndex;
      /* 비행기를 태울 구간이면 진행도, 아니면 null 입니다. 진행도 0도 값이라 null 로만 가릅니다. */
      const riding = active ? legProgress : null;

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
        if (riding !== null) plane = globePlane(globe.frame, from, to, riding);
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
        const mx = (sx + ex) / 2;
        const my = (sy + ey) / 2 - lift;
        drawn.push({
          key,
          path: `M${sx.toFixed(1)} ${sy.toFixed(1)} Q${mx.toFixed(1)} ${my.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`,
          active,
        });
        if (riding !== null) plane = curvePlane(sx, sy, mx, my, ex, ey, riding);
      }
    }
    return { drawn, plane };
  }, [stops, focusIndex, mode, globe, flat, width, legProgress]);

  /*
   * 트렌드가 닿은 나라는 그 나라의 값만큼 진하게 칠합니다. 같은 색으로 모두 덮으면 어디가 더
   * 뜨거운지 지도에서 읽을 수 없습니다. 가장 높은 곳을 1로 두고 견줍니다.
   */
  const hottest = Math.max(...stops.map((stop) => Math.abs(stop.weight)), 1);

  const highlights = stops.map((stop, index) => ({
    index,
    id: stop.country.atlasId,
    passed: index <= focusIndex,
    here: index === stopIndex,
    depth: 0.32 + 0.53 * (Math.abs(stop.weight) / hottest),
  }));

  return (
    <div
      className={`worldmap worldmap--${mode}${onSteer ? ' is-steerable' : ''}${dragging ? ' is-dragging' : ''}`}
      ref={ref}
      onPointerDown={startDrag}
      onPointerMove={moveDrag}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
    >
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
            {legs.drawn.map((leg) => (
              <path key={leg.key} className={`worldmap-leg ${leg.active ? 'is-active' : ''}`} d={leg.path} />
            ))}
          </g>
        </svg>
      )}

      {/*
        * 비행기만 따로 한 겹 위에 올립니다. 핀은 지도 위에 얹는 HTML 단추라 지도를 그리는
        * 그림판보다 위에 있어서, 비행기를 그림판 안에 두면 지나가는 나라의 점 밑으로 들어갑니다.
        */}
      {ready && legs.plane && (
        <svg className="worldmap-plane-layer" width={width} height={height} aria-hidden="true">
          {/*
            * 테두리에 쓰는 로고 결입니다. 기수 쪽 하늘파랑에서 꼬리 쪽 연보라로 넘어갑니다.
            * 속을 채울 때보다 진하게 둡니다. 테두리는 가늘어서, 속을 칠할 때의 옅은 빛깔로는
            * 형체가 잡히지 않습니다. 자리를 비율(objectBoundingBox)로 잡아 두어, 기수가 돌면
            * 결도 같이 돕니다.
            */}
          <defs>
            <linearGradient id="worldmap-plane-edge" x1="0" y1="0" x2="0.35" y2="1">
              <stop offset="0%" stopColor="#5BA4E8" />
              <stop offset="50%" stopColor="#8E9FE8" />
              <stop offset="100%" stopColor="#9A66DE" />
            </linearGradient>
          </defs>
          <g
            className="worldmap-plane"
            transform={`translate(${legs.plane.x.toFixed(1)} ${legs.plane.y.toFixed(1)}) rotate(${(legs.plane.angle + 90).toFixed(1)}) scale(${PLANE_SCALE}) translate(-11.5 -12)`}
          >
            <path d={PLANE_PATH} />
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
              <span className="worldmap-pin-growth">{pin.stop.label}</span>
              <span className="worldmap-pin-date">{pin.stop.since}부터</span>
            </span>
          </span>
        </button>
      ) : null))}
    </div>
  );
}
