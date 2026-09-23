import { useEffect } from 'react';

/*
 * 홈의 칸 넘김. 한 번 굴리면 다음 칸까지 스르르 내려갑니다.
 *
 * CSS scroll-snap 을 쓰지 않는 이유는 하나입니다 — 넘어가는 데 걸리는 시간을 정할 수
 * 없습니다. `scroll-behavior: smooth` 의 길이는 브라우저가 쥐고 있어(크롬은 300ms 안팎)
 * CSS 로 늘릴 수단이 없고, 그 속도로는 별이 흩어지는 장면이 한 순간에 지나갑니다.
 * 그래서 굴림을 받아 스크롤을 직접 옮깁니다.
 *
 * particleLanding.css 의 같은 미디어 쿼리와 짝입니다. 거기서 칸 높이를 한 화면으로 맞추고
 * 여기서 그 칸 사이를 옮깁니다. 한쪽만 고치면 멎는 자리와 칸의 경계가 어긋납니다.
 */

/** 칸 넘김을 켜는 창 크기. particleLanding.css 의 같은 값과 맞춰야 합니다. */
export const GLIDE_AT = '(min-width: 901px) and (min-height: 700px)';

/** 붙박이 머리글이 덮는 높이. 칸의 머리가 그 아래에서 시작합니다. */
const HEADER_HEIGHT = 64;

/** 한 칸을 넘어가는 데 걸리는 시간. '스르르 내려가는' 느낌을 정하는 값입니다. */
const GLIDE_MS = 1100;

/** 넘어간 뒤 굴림을 흘려보내는 시간. 트랙패드의 여운이 다음 칸까지 밀고 가지 않게 합니다. */
const COOLDOWN_MS = 260;

/** 이보다 약한 굴림은 넘김으로 치지 않습니다. 손이 스친 정도로 화면이 바뀌면 안 됩니다. */
const WHEEL_THRESHOLD = 8;

/** 사람이 직접 굴린 뒤(스크롤막대 끌기 등) 멎는 자리로 붙잡기까지 기다리는 시간. */
const SETTLE_MS = 140;

/** 멎는 자리에 닿았다고 볼 거리(px). 소수점 반올림과 배율 때문에 정확히 0 이 되지 않습니다. */
const ARRIVED = 2;

const easeInOutCubic = (t: number) => (t < .5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

/**
 * 굴림이 페이지가 아니라 제 안쪽을 굴려야 하는 칸인지 봅니다.
 *
 * 히어로의 검색 결과 목록처럼 스스로 스크롤을 가진 칸이 있습니다. 그 안에서 굴렸는데 페이지가
 * 넘어가면 목록을 끝까지 볼 수 없습니다. 다만 그 칸이 이미 끝에 닿았으면 페이지 차례입니다.
 */
function scrollableUnder(node: EventTarget | null, deltaY: number) {
  let element = node instanceof Element ? node : null;
  while (element && element !== document.body) {
    const { overflowY } = getComputedStyle(element);
    if ((overflowY === 'auto' || overflowY === 'scroll') && element.scrollHeight > element.clientHeight) {
      const atTop = element.scrollTop <= 0;
      const atBottom = element.scrollTop + element.clientHeight >= element.scrollHeight - 1;
      if (deltaY > 0 ? !atBottom : !atTop) return true;
    }
    element = element.parentElement;
  }
  return false;
}

export function useSectionGlide() {
  useEffect(() => {
    const media = window.matchMedia(GLIDE_AT);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let release: (() => void) | null = null;

    const attach = () => {
      let stops: number[] = [];
      let animating = false;
      let frame = 0;
      let idle = 0;
      let settledAt = 0;
      let from = 0;
      let to = 0;
      let startTime = 0;

      /*
       * 멎을 자리를 그때그때 잽니다. 미리 재 두면 트렌드 판이 늦게 도착해 칸 높이가 달라졌을
       * 때 옛 자리로 옮기게 됩니다. 칸이 셋뿐이라 재는 값은 싸게 얻습니다.
       */
      const readStops = () => {
        const page = document.querySelector('.particle-landing');
        if (!page) return [];
        const sections = page.querySelectorAll<HTMLElement>('.hero, .trends-section, .featured-section');
        const max = Math.max(0, Math.round(document.documentElement.scrollHeight - window.innerHeight));
        const tops = [...sections].map((section) => {
          const top = Math.round(section.getBoundingClientRect().top + window.scrollY - HEADER_HEIGHT);
          return Math.max(0, Math.min(max, top));
        });
        /*
         * 푸터는 한 칸을 채우지 않지만 멎는 자리는 하나 있어야 합니다. 없으면 마지막 칸이
         * 끝이 되어 푸터까지 내려갈 길이 없습니다.
         */
        if (tops.length && max - tops[tops.length - 1] > 8) tops.push(max);
        return tops;
      };

      const nearest = () => {
        stops = readStops();
        const y = window.scrollY;
        let best = 0;
        stops.forEach((stop, index) => {
          if (Math.abs(stop - y) < Math.abs(stops[best] - y)) best = index;
        });
        return best;
      };

      const step = (time: number) => {
        const ratio = Math.min(1, (time - startTime) / GLIDE_MS);
        /*
         * behavior: 'instant' 여야 합니다. 전역 `scroll-behavior: smooth` 가 걸려 있어서
         * 그냥 옮기면 브라우저가 제 속도로 또 부드럽게 옮기려 들고, 두 움직임이 서로를
         * 밀어 화면이 덜컹거립니다.
         */
        window.scrollTo({ top: from + (to - from) * easeInOutCubic(ratio), behavior: 'instant' });
        if (ratio < 1) {
          frame = requestAnimationFrame(step);
          return;
        }
        frame = 0;
        animating = false;
        settledAt = performance.now();
      };

      const glideTo = (index: number) => {
        if (!stops.length) return;
        const target = stops[Math.max(0, Math.min(stops.length - 1, index))];
        if (Math.abs(target - window.scrollY) < ARRIVED) return;
        if (frame) cancelAnimationFrame(frame);
        frame = 0;
        /* 덜 움직이기를 원하는 사람에게 1초짜리 미끄러짐을 강요하지 않습니다. 자리는 그대로 지킵니다. */
        if (reducedMotion.matches) {
          animating = false;
          window.scrollTo({ top: target, behavior: 'instant' });
          settledAt = performance.now();
          return;
        }
        from = window.scrollY;
        to = target;
        animating = true;
        frame = requestAnimationFrame((time) => { startTime = time; step(time); });
      };

      const onWheel = (event: WheelEvent) => {
        /* ctrl+휠은 확대·축소입니다. 안쪽에 제 스크롤을 가진 칸도 그대로 둡니다. */
        if (event.ctrlKey || event.defaultPrevented) return;
        /* 가로로 쓸어 넘긴 것은 세로 스크롤이 아닙니다. 캐러셀이 쓸 수 있게 그대로 둡니다. */
        if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
        if (scrollableUnder(event.target, event.deltaY)) return;
        event.preventDefault();
        if (animating || performance.now() - settledAt < COOLDOWN_MS) return;
        if (Math.abs(event.deltaY) < WHEEL_THRESHOLD) return;
        glideTo(nearest() + (event.deltaY > 0 ? 1 : -1));
      };

      const onKeyDown = (event: KeyboardEvent) => {
        const target = event.target as HTMLElement | null;
        /* 검색창에 글을 쓰는 중이면 키는 그 칸의 것입니다. */
        if (target?.isContentEditable || (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        const index = nearest();
        let next: number | null = null;
        if (event.key === 'PageDown') next = index + 1;
        else if (event.key === 'PageUp') next = index - 1;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = stops.length - 1;
        if (next === null) return;
        event.preventDefault();
        glideTo(next);
      };

      /*
       * 우리가 옮기지 않은 스크롤(스크롤막대 끌기, 화살표 키, 손가락 밀기)이 멎으면 가장
       * 가까운 자리로 붙잡습니다. 굴림만 받으면 그 길들이 칸 사이 어중간한 자리에 섭니다.
       */
      const onScroll = () => {
        if (animating) return;
        window.clearTimeout(idle);
        idle = window.setTimeout(() => {
          if (animating) return;
          glideTo(nearest());
        }, SETTLE_MS);
      };

      window.addEventListener('wheel', onWheel, { passive: false });
      window.addEventListener('keydown', onKeyDown);
      window.addEventListener('scroll', onScroll, { passive: true });

      return () => {
        if (frame) cancelAnimationFrame(frame);
        window.clearTimeout(idle);
        window.removeEventListener('wheel', onWheel);
        window.removeEventListener('keydown', onKeyDown);
        window.removeEventListener('scroll', onScroll);
      };
    };

    /* 창 크기가 켜는 조건을 오갈 때만 붙이고 뗍니다. 좁은 창에서는 평소 스크롤 그대로입니다. */
    const sync = () => {
      if (media.matches && !release) release = attach();
      else if (!media.matches && release) { release(); release = null; }
    };

    sync();
    media.addEventListener('change', sync);
    return () => {
      media.removeEventListener('change', sync);
      release?.();
    };
  }, []);
}
