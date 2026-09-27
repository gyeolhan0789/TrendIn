import { useCallback, useEffect, useRef, useState } from 'react';

/*
 * 고른 키워드가 어느 나라에서 시작해 어디로 이어졌는지, 지도를 그 나라로 끌어당기며 보여 줍니다.
 *
 * 한 나라에 머물렀다가(hold) 다음 나라로 미끄러지고(move), 옮겨 가는 동안에는 잠깐 물러섰다가
 * 다시 다가갑니다. 바로 옆 나라로 가는데도 화면 밖까지 물러서면 멀미가 나므로, 물러서는 정도는
 * 두 나라 사이의 거리에 맞춥니다.
 *
 * 지구본과 평면 지도가 같은 값을 나눠 씁니다. 지구본은 lon·lat 을 돌리는 각도로, 평면 지도는
 * 화면 가운데에 둘 지점으로 읽습니다. 그래서 모드를 바꿔도 보던 자리를 그대로 이어받습니다.
 */

export interface MapView {
  lon: number;
  lat: number;
  /** 1이면 세계 전체, 클수록 가까이 */
  zoom: number;
}

export interface TourStop {
  lon: number;
  lat: number;
}

/** 나라 하나를 들여다볼 때의 배율. 나라 모양이 또렷하게 보이는 정도입니다. */
const FOCUS_ZOOM = 3.6;
/** 나라를 고를 때 다가가는 정도. 고른 나라가 커지되 이웃 나라가 함께 보이는 만큼입니다. */
export const PICK_ZOOM = 2;
const WORLD_ZOOM = 1;
/*
 * 나라와 나라 사이를 건널 때 물러설 수 있는 가장 먼 배율입니다. 세계 전체(1)까지 물러서면
 * 평면 지도가 창 높이에 딱 맞아 위아래로 움직일 틈이 없어지고, 그 대목에서 화면이 멎습니다.
 */
const TRAVEL_ZOOM = 1.9;
/*
 * 손으로 움직일 때 오갈 수 있는 배율입니다. 아래쪽은 따라가기가 물러서는 만큼까지만 열어 두어,
 * 손으로 끝까지 줄인 뒤 따라가기를 눌러도 배율이 튀지 않습니다. 위쪽은 나라 하나가 화면을 가득
 * 채우고도 국경이 남아 보이는 정도입니다.
 */
export const MIN_ZOOM = WORLD_ZOOM * 0.9;
export const MAX_ZOOM = 14;
/*
 * 한 구간을 건너는 데 드는 밑바탕 시간과, 닿은 나라에 머무는 시간입니다. 비행기는 카메라와
 * 같은 진행도를 타므로 이 값이 곧 비행기 속도입니다. 여섯 나라짜리 경로를 끝까지 보는 데
 * 예전에는 스무 초가 넘게 걸려, 다 보기 전에 눈이 먼저 떠났습니다.
 */
const MOVE_MS = 1400;
const HOLD_MS = 1200;

interface Motion {
  from: MapView;
  to: MapView;
  /** 옮겨 가는 동안 잠시 물러설 배율. 0이면 물러서지 않습니다. */
  via: number;
  startedAt: number;
  duration: number;
}

const LOG = Math.log;

function easeInOut(ratio: number) {
  return ratio < 0.5 ? 4 * ratio * ratio * ratio : 1 - (-2 * ratio + 2) ** 3 / 2;
}

/** 경도는 ±180에서 되돌아옵니다. 서울에서 뉴욕으로 갈 때 지구를 한 바퀴 돌지 않도록 가까운 쪽으로 갑니다. */
function shortestLonDelta(from: number, to: number) {
  return ((((to - from) % 360) + 540) % 360) - 180;
}

/** 두 지점 사이의 각거리(도). 얼마나 물러설지, 얼마나 오래 갈지를 여기서 정합니다. */
function angularDistance(from: TourStop, to: TourStop) {
  const lonGap = Math.abs(shortestLonDelta(from.lon, to.lon));
  return Math.hypot(lonGap, to.lat - from.lat);
}

export interface SpreadTour {
  view: MapView;
  /** 지금 머무르고 있는 자리. 아직 첫 자리에 닿기 전이거나 전체 보기면 -1 입니다. */
  stopIndex: number;
  /** 지금 가고 있는(또는 머무르는) 자리. 지나온 경로를 어디까지 그릴지 정합니다. */
  focusIndex: number;
  /*
   * 지금 보고 있는 구간을 비행기가 얼마나 지났는지(0~1). 태울 구간이 없으면 null 입니다.
   *
   * 닿아도 1 로 그대로 남습니다. 비행기는 닿은 나라에 서 있다가 다음 구간이 시작되면 그
   * 자리에서 그대로 떠납니다. 앞 구간의 끝과 다음 구간의 처음이 같은 나라라 이어 붙습니다.
   */
  legProgress: number | null;
  playing: boolean;
  play: () => void;
  pause: () => void;
  /** 자리 하나로 다가갑니다. zoom 을 주면 그만큼만 다가가, 나라 하나만 남기지 않을 수 있습니다. */
  goTo: (index: number, zoom?: number) => void;
  /**
   * 누른 나라로 카메라를 옮깁니다. `goTo` 와 달리 평면 지도에서도 움직입니다 — 따라가기를 끈
   * 것은 흐름보기에서 비행기만 건너게 하려던 것이고, 사람이 나라를 콕 집은 때는 그리 가는 게 맞습니다.
   */
  flyTo: (index: number, zoom?: number) => void;
  showWorld: () => void;
  /** 손으로 지도를 움직일 때. 따라가던 움직임을 멈추고 조작을 넘겨받습니다. */
  steer: (update: (view: MapView) => MapView) => void;
}

/**
 * autoPlayKey 가 바뀌면 그 경로를 처음부터 따라갑니다. null 이면 따라가지 않고 자리만 되돌립니다.
 * 전체보기처럼 경로가 없는 화면에서도 지도를 손으로 옮기고 나라로 다가가는 데는 이 훅을 씁니다.
 *
 * follow 를 끄면 카메라가 가만히 있고 비행기만 건넙니다. 평면 지도는 세계가 통째로 들어와
 * 있어서, 나라마다 확 당겼다 놓으면 어디서 어디로 가는 길인지가 오히려 안 보입니다. 지구본은
 * 반대로 뒤쪽이 가려져 있어 따라 돌아야 길이 이어집니다.
 */
export function useSpreadTour(stops: TourStop[], autoPlayKey: string | null, follow = true): SpreadTour {
  const [view, setView] = useState<MapView>({ lon: 20, lat: 18, zoom: WORLD_ZOOM });
  const [stopIndex, setStopIndex] = useState(-1);
  const [focusIndex, setFocusIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [legProgress, setLegProgress] = useState<number | null>(null);
  /* 그리기 고리를 다시 돌려야 할 때 올리는 값입니다. 값 자체는 쓰지 않고 신호로만 씁니다. */
  const [awake, setAwake] = useState(0);

  const viewRef = useRef(view);
  const motionRef = useRef<Motion | null>(null);
  const holdUntilRef = useRef(0);
  const stopsRef = useRef(stops);
  const playingRef = useRef(false);
  const targetRef = useRef(-1);

  stopsRef.current = stops;

  /* steady 는 카메라를 붙들어 둔 채 시간만 흘려보낼 때입니다. 물러섰다 다가오는 일도 없습니다. */
  const followRef = useRef(follow);
  followRef.current = follow;

  const startMotion = useCallback((to: MapView, distance: number, steady = false) => {
    const from = viewRef.current;
    // 멈춰 있는 동안에는 그리기 고리를 접어 둡니다. 움직일 일이 생겼으니 여기서 다시 깨웁니다.
    setAwake((count) => count + 1);
    motionRef.current = {
      from,
      to,
      // 멀리 갈수록 많이 물러섭니다. 이웃 나라로 갈 때는 거의 그대로 미끄러집니다.
      via: steady || distance <= 12 ? 0 : Math.max(TRAVEL_ZOOM, FOCUS_ZOOM - distance / 26),
      startedAt: performance.now(),
      duration: Math.min(2000, MOVE_MS * (0.55 + Math.min(1, distance / 120))),
    };
  }, []);

  const moveToStop = useCallback((index: number, zoom = FOCUS_ZOOM) => {
    const stop = stopsRef.current[index];
    if (!stop) return;
    const current = viewRef.current;
    targetRef.current = index;
    setFocusIndex(index);

    /*
     * 따라가지 않을 때는 보던 자리를 그대로 둡니다. 건너는 데 걸리는 시간만 앞 나라와의 거리로
     * 재어, 태평양을 건널 때는 오래 날고 이웃 나라로는 금방 닿습니다.
     */
    if (!followRef.current) {
      const previous = stopsRef.current[index - 1] ?? stop;
      if (index >= 1) setLegProgress(0);
      startMotion(current, angularDistance(previous, stop), true);
      return;
    }

    const distance = angularDistance(current, stop);
    /*
     * 첫 자리로 갈 때는 건널 구간이 없어 비행기를 태우지 않으므로 치웁니다. 이어지는 구간이면
     * 그대로 둡니다. 서 있던 나라가 곧 새 구간의 출발지라, 손대지 않아도 제자리에서 떠납니다.
     */
    if (index < 1) setLegProgress(null);
    startMotion({ lon: stop.lon, lat: stop.lat, zoom }, distance);
  }, [startMotion]);

  const goTo = useCallback((index: number, zoom?: number) => {
    setPlaying(false);
    playingRef.current = false;
    setStopIndex(-1);
    moveToStop(index, zoom);
  }, [moveToStop]);

  const flyTo = useCallback((index: number, zoom = FOCUS_ZOOM) => {
    const stop = stopsRef.current[index];
    if (!stop) return;
    setPlaying(false);
    playingRef.current = false;
    setStopIndex(-1);
    targetRef.current = index;
    setFocusIndex(index);
    // 경로를 타는 것이 아니라 한 나라로 가는 것이라 비행기는 태우지 않습니다.
    setLegProgress(null);
    startMotion({ lon: stop.lon, lat: stop.lat, zoom }, angularDistance(viewRef.current, stop));
  }, [startMotion]);

  const showWorld = useCallback(() => {
    setPlaying(false);
    playingRef.current = false;
    setStopIndex(-1);
    targetRef.current = -1;
    setFocusIndex(-1);
    // 전체 보기는 경로를 통째로 걷어내는 자리라, 그 위에 서 있던 비행기도 함께 내려놓습니다.
    setLegProgress(null);
    startMotion({ lon: 20, lat: 18, zoom: WORLD_ZOOM }, 40);
  }, [startMotion]);

  const play = useCallback(() => {
    if (stopsRef.current.length === 0) return;
    setPlaying(true);
    playingRef.current = true;
    // 마지막 자리까지 본 뒤 다시 누르면 처음부터 돕니다.
    const next = targetRef.current + 1 >= stopsRef.current.length ? 0 : targetRef.current + 1;
    setStopIndex(-1);
    moveToStop(next);
  }, [moveToStop]);

  /*
   * 휠과 끌기가 들어오는 자리입니다. 따라가는 중이었다면 그 자리에서 멈춥니다. 손으로 움직이는
   * 동안 뒤에서 계속 끌어당기면 지도가 손을 벗어나기 때문입니다. 가던 자리는 그대로 두어,
   * 멈춘 나라의 이름표와 지나온 경로는 남습니다.
   */
  const steer = useCallback((update: (view: MapView) => MapView) => {
    motionRef.current = null;
    playingRef.current = false;
    setPlaying(false);
    /* 비행기는 건드리지 않습니다. 가던 자리에 그대로 서서, 손으로 옮긴 지도를 따라다닙니다. */
    if (targetRef.current >= 0) setStopIndex(targetRef.current);

    const next = update(viewRef.current);
    const settled = {
      // 경도는 한 바퀴 돌면 제자리입니다. 한쪽으로 계속 끌어도 값이 끝없이 커지지 않게 접어 둡니다.
      lon: ((((next.lon + 180) % 360) + 360) % 360) - 180,
      lat: Math.max(-90, Math.min(90, next.lat)),
      zoom: Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, next.zoom)),
    };
    viewRef.current = settled;
    setView(settled);
  }, []);

  const pause = useCallback(() => {
    setPlaying(false);
    playingRef.current = false;
  }, []);

  /* 키워드를 새로 고르면 그 키워드의 첫 나라부터 다시 따라갑니다. */
  useEffect(() => {
    targetRef.current = -1;
    setFocusIndex(-1);
    setStopIndex(-1);
    setLegProgress(null);
    if (autoPlayKey === null || stops.length === 0) return;
    setPlaying(true);
    playingRef.current = true;
    holdUntilRef.current = 0;
    moveToStop(0);
    // 키워드가 바뀔 때만 다시 시작합니다. stops 배열은 같은 키워드에서도 새로 만들어질 수 있습니다.
  }, [autoPlayKey]);

  useEffect(() => {
    let frame = 0;

    const tick = () => {
      const now = performance.now();
      const motion = motionRef.current;

      /* 움직이지도 않고 다음 자리로 넘어갈 일도 없으면 고리를 접습니다. 깨우기는 startMotion 이 합니다. */
      if (!motion && !playingRef.current) return;
      frame = requestAnimationFrame(tick);

      if (motion) {
        const ratio = Math.min(1, (now - motion.startedAt) / motion.duration);
        const eased = easeInOut(ratio);
        /*
         * 배율은 '몇 배'로 읽히므로 로그 자리에서 잇습니다. 3.6에서 1.55로 숫자를 곧게 줄이면
         * 낮은 쪽에서 몇 배씩 확 바뀌어, 같은 속도로 미끄러지지 않고 걸리는 것처럼 보입니다.
         */
        const straight = LOG(motion.from.zoom) + (LOG(motion.to.zoom) - LOG(motion.from.zoom)) * eased;
        /* 가는 동안 가운데에서 가장 많이 물러섰다가 다시 다가옵니다. 양 끝에서는 0이라 이음매가 없습니다. */
        const dip = motion.via === 0
          ? 0
          : Math.max(0, Math.min(LOG(motion.from.zoom), LOG(motion.to.zoom)) - LOG(motion.via));
        const zoom = Math.exp(straight - dip * Math.sin(Math.PI * eased));

        const next = {
          lon: motion.from.lon + shortestLonDelta(motion.from.lon, motion.to.lon) * eased,
          lat: motion.from.lat + (motion.to.lat - motion.from.lat) * eased,
          zoom: Math.max(WORLD_ZOOM * 0.9, zoom),
        };
        viewRef.current = next;
        setView(next);
        /* 비행기는 카메라와 같은 진행도를 탑니다. 태울 구간이 있을 때만 자리를 옮깁니다. */
        if (targetRef.current >= 1) setLegProgress(eased);

        if (ratio >= 1) {
          motionRef.current = null;
          holdUntilRef.current = now + HOLD_MS;
          /* 닿은 비행기는 그대로 둡니다. 치우지 않아야 다음 구간을 그 자리에서 이어 갑니다. */
          if (targetRef.current >= 0) setStopIndex(targetRef.current);
        }
        return;
      }

      if (!playingRef.current || now < holdUntilRef.current) return;

      const next = targetRef.current + 1;
      if (next >= stopsRef.current.length) {
        playingRef.current = false;
        setPlaying(false);
        return;
      }
      setStopIndex(-1);
      moveToStop(next);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [moveToStop, awake]);

  return { view, stopIndex, focusIndex, legProgress, playing, play, pause, goTo, flyTo, showWorld, steer };
}
