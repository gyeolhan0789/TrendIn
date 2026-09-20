import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, MouseEvent as ReactMouseEvent, PointerEvent as ReactPointerEvent, ReactNode } from 'react';

export interface CarouselSlide {
  key: string;
  /** 점·화살표가 읽어 줄 이름입니다. 낱장 안에 제목이 또 있어도 안내는 이 이름으로 합니다. */
  label: string;
  node: ReactNode;
}

interface CylinderCarouselProps {
  slides: CarouselSlide[];
  /** 지금 가운데 있는 낱장. 바깥이 들고 있어서 주소창 같은 곳과 맞출 수 있습니다. */
  index: number;
  onIndexChange: (next: number) => void;
  ariaLabel: string;
}

/** 이웃한 낱장이 원통 위에서 벌어지는 각. 크면 옆장이 더 많이 돌아눕습니다. */
const ARC = 34;
/*
 * 원통 반지름을 낱장 너비의 몇 배로 볼지.
 *
 * 아무 값이나 쓸 수 없습니다. 밖에서 보는 원통이라 옆장은 안쪽 모서리가 앞으로 나오는데,
 * 반지름이 너무 짧으면 그 모서리가 가운데 장 앞으로 튀어나와 두 장이 서로를 뚫고 지나갑니다.
 * 모서리가 딱 맞물리는 값은 cot(ARC/2)/2 이고, 아래 값이 ARC=34°일 때의 그 값입니다.
 * ARC 를 바꾸면 이 값도 같이 다시 구해야 합니다.
 */
const RADIUS_RATIO = 1.64;
/** 손을 뗐을 때 다음 장까지 넘길 최소 속도(장/초). 살짝 튕겨도 넘어가도록 낮게 둡니다. */
const FLICK_SPEED = 0.6;
/** 이만큼 넘게 끌면 누른 것이 아니라 끈 것으로 봅니다. 낱장 안의 링크를 지키는 값입니다. */
const DRAG_SLOP = 6;

const norm = (value: number, size: number) => ((value % size) + size) % size;

/** i번 낱장이 지금 자리(pos)에서 몇 장 떨어져 있는지. 원통이라 한 바퀴 돌아 더 가까운 쪽을 씁니다. */
function shortestOffset(index: number, pos: number, size: number) {
  return norm(index - pos + size / 2, size) - size / 2;
}

/**
 * 낱장을 커다란 원통 겉면에 붙여 돌리는 캐러셀입니다.
 *
 * 보는 사람은 원통 밖에 서 있습니다. 그래서 가장 가까운 가운데 장이 정면으로 서고,
 * 옆장은 통이 휘어 나가는 대로 바깥쪽을 향해 돌아누우며 뒤로 물러납니다. 낱장의 바깥 모서리가
 * 안쪽 모서리보다 멀어지는 쪽이라, 통을 껴안은 것이 아니라 통을 바라보는 그림이 됩니다.
 *
 * 자리(pos)는 정수가 아니라 실수여서, 끄는 동안에도 각도와 투명도가 손끝을 그대로 따라갑니다.
 * 손을 떼면 가장 가까운 장으로 붙고, 그 마무리만 CSS 전환에 맡깁니다.
 */
export function CylinderCarousel({ slides, index, onIndexChange, ariaLabel }: CylinderCarouselProps) {
  const size = slides.length;
  const viewport = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLUListElement>(null);
  const [pos, setPos] = useState(index);
  const [dragging, setDragging] = useState(false);
  /* 낱장 너비를 재야 원통 반지름을 정할 수 있습니다. 창을 줄이면 반지름도 같이 줄어듭니다. */
  const [slideWidth, setSlideWidth] = useState(0);
  const drag = useRef<{ id: number; x: number; pos: number; lastX: number; lastAt: number; speed: number; moved: boolean } | null>(null);
  /* 끈 직후에 따라오는 click 한 번만 막습니다. 카드 안 링크가 끌기 끝에 열리면 안 됩니다. */
  const swallowClick = useRef(false);

  useLayoutEffect(() => {
    const first = stage.current?.firstElementChild;
    if (!first) return;
    const observer = new ResizeObserver(([entry]) => setSlideWidth(entry.contentRect.width));
    observer.observe(first);
    return () => observer.disconnect();
  }, []);

  /* 바깥에서 자리를 옮기면(점·화살표·주소창) 지금 자리에서 가장 가까운 같은 장으로 돌립니다. */
  useEffect(() => {
    setPos((prev) => {
      const settled = Math.round(prev);
      const delta = shortestOffset(index, norm(settled, size), size);
      return delta === 0 ? prev : settled + delta;
    });
  }, [index, size]);

  const settle = useCallback((next: number) => {
    setPos(next);
    onIndexChange(norm(Math.round(next), size));
  }, [onIndexChange, size]);

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || slideWidth === 0) return;
    /* 앞선 끌기가 click 없이 끝났으면 그 표시가 남습니다. 새 손짓을 그것 때문에 잃지 않게 지웁니다. */
    swallowClick.current = false;
    drag.current = { id: event.pointerId, x: event.clientX, pos, lastX: event.clientX, lastAt: event.timeStamp, speed: 0, moved: false };
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const state = drag.current;
    if (!state || state.id !== event.pointerId) return;
    const moved = event.clientX - state.x;
    if (!state.moved && Math.abs(moved) < DRAG_SLOP) return;
    if (!state.moved) {
      /*
       * 포인터를 붙잡는 것은 정말 끌기 시작한 뒤입니다. 누르자마자 붙잡으면 뗄 때의 click 이
       * 카드가 아니라 이 틀에서 일어난 것이 되어, 카드 안 링크가 열리지 않습니다.
       */
      state.moved = true;
      setDragging(true);
      viewport.current?.setPointerCapture(event.pointerId);
    }
    /*
     * 손을 뗄 때 쓸 속도입니다. 끌기 전체 평균으로 두면 천천히 끌다 마지막에 튕긴 손짓을 놓치고,
     * 직전 한 조각만 보면 값이 튑니다. 그래서 최근 움직임에 무게를 두고 직전 값과 섞습니다.
     */
    const seconds = (event.timeStamp - state.lastAt) / 1000;
    if (seconds > 0) {
      const sample = -((event.clientX - state.lastX) / slideWidth) / seconds;
      state.speed = state.speed * 0.3 + sample * 0.7;
      state.lastX = event.clientX;
      state.lastAt = event.timeStamp;
    }
    setPos(state.pos - moved / slideWidth);
  };

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const state = drag.current;
    if (!state || state.id !== event.pointerId) return;
    drag.current = null;
    setDragging(false);
    if (viewport.current?.hasPointerCapture(event.pointerId)) viewport.current.releasePointerCapture(event.pointerId);
    if (!state.moved) return;
    swallowClick.current = true;
    /* 빠르게 튕겼으면 가까운 장에 붙는 대신 그 방향으로 한 장 더 보냅니다. */
    const landing = Math.abs(state.speed) > FLICK_SPEED
      ? (state.speed > 0 ? Math.ceil(pos) : Math.floor(pos))
      : Math.round(pos);
    settle(landing);
  };

  const handleClickCapture = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!swallowClick.current) return;
    swallowClick.current = false;
    event.preventDefault();
    event.stopPropagation();
  };

  const step = (direction: 1 | -1) => onIndexChange(norm(index + direction, size));

  const radius = slideWidth * RADIUS_RATIO;

  /**
   * 옆장을 누르면 그 장으로 옵니다.
   *
   * 낱장에 처리를 걸 수 없습니다. 세 장이 모두 같은 격자 칸에 겹쳐 있고 자리는 transform 으로만
   * 내는데, 적중 판정은 그 이동을 따라오지 않습니다. 눈에는 옆으로 밀려 보여도 눌리는 자리는
   * 가운데 그대로라, 옆 카드를 누르면 아무 낱장에도 닿지 않고 이 틀까지 내려옵니다.
   *
   * 그래서 여기서 받아, 누른 가로 자리가 어느 장의 자리에 가장 가까운지로 가립니다. 자리는
   * 그릴 때 쓰는 식을 그대로 다시 풀어 구하므로 화면에 보이는 위치와 어긋나지 않습니다.
   */
  const handleSlideClick = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (slideWidth === 0) return;
    const rect = viewport.current?.getBoundingClientRect();
    if (!rect) return;

    const dx = event.clientX - (rect.left + rect.width / 2);
    /*
     * 가운데 카드 위라면 그 카드가 이 클릭의 주인입니다. 옆장 자리가 카드 폭보다 가까이
     * 붙어 있어, 가장 가까운 장만 따지면 카드 바깥쪽 가장자리를 옆장으로 잘못 셉니다.
     */
    if (Math.abs(dx) <= slideWidth / 2) return;

    let nearest = 0;
    let smallest = Infinity;
    for (let candidate = 0; candidate < size; candidate += 1) {
      const angle = (shortestOffset(candidate, pos, size) * ARC * Math.PI) / 180;
      const gap = Math.abs(dx - radius * Math.sin(angle));
      if (gap < smallest) {
        smallest = gap;
        nearest = candidate;
      }
    }

    /* 가운데 장은 건드리지 않습니다. 카드 안의 링크가 이 클릭의 주인입니다. */
    if (nearest === norm(Math.round(pos), size)) return;
    onIndexChange(nearest);
  };

  return (
    <div className="cylinder" role="group" aria-roledescription="캐러셀" aria-label={ariaLabel}>
      {/* 화살표가 카드 높이 한가운데에 서야 해서, 낱장 무대만 감싸는 틀을 하나 둡니다. */}
      <div className="cylinder-frame">
      <div
          /* 너비를 재기 전에는 반지름이 0이라 낱장이 한자리에 겹칩니다. 그 첫 칸은 전환 없이 지나갑니다. */
          className={`cylinder-viewport${dragging ? ' is-dragging' : ''}${slideWidth === 0 ? ' is-measuring' : ''}`}
          ref={viewport}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onClickCapture={handleClickCapture}
          onClick={handleSlideClick}
          /* 카드 안이 링크라 그냥 끌면 브라우저의 링크 끌어 놓기가 먼저 시작됩니다. */
          onDragStart={(event) => event.preventDefault()}
        >
          <ul className="cylinder-stage" ref={stage}>
            {slides.map((slide, slideIndex) => {
              const offset = shortestOffset(slideIndex, pos, size);
              const angle = offset * ARC;
              const radians = (angle * Math.PI) / 180;
              /* 두 장 넘게 떨어져도 계속 흐려지면 뒤가 텅 비어 보여, 물러나는 정도는 두 장에서 멈춥니다. */
              const distance = Math.min(Math.abs(offset), 2);
              const active = norm(Math.round(pos), size) === slideIndex;
              const x = radius * Math.sin(radians);
              const z = radius * Math.cos(radians) - radius;
              const style: CSSProperties = {
                /* 낱장의 법선이 원통 바깥(반지름 방향)을 보게 같은 부호로 돌립니다. 부호를 뒤집으면 통 안쪽 벽이 됩니다. */
                transform: `translate3d(${x.toFixed(2)}px, 0, ${z.toFixed(2)}px) rotateY(${angle.toFixed(2)}deg) scale(${(1 - distance * 0.1).toFixed(3)})`,
                opacity: Math.max(0.2, 1 - distance * 0.52),
                filter: distance > 0.02 ? `blur(${(Math.min(distance, 1) * 1.2).toFixed(2)}px)` : undefined,
                zIndex: 100 - Math.round(distance * 10),
              };
              return (
                <li
                  className={`cylinder-slide${active ? ' is-active' : ''}`}
                  key={slide.key}
                  style={style}
                  aria-hidden={!active}
                >
                  {/* 옆으로 밀려난 장은 화면에 남아 있지만 눌리거나 초점이 가면 안 됩니다. */}
                  <div className="cylinder-slide-body" inert={!active}>{slide.node}</div>
                </li>
              );
            })}
          </ul>
        </div>

        <button type="button" className="cylinder-step cylinder-step--prev" aria-label="이전" onClick={() => step(-1)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <button type="button" className="cylinder-step cylinder-step--next" aria-label="다음" onClick={() => step(1)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M9 18l6-6-6-6" /></svg>
        </button>
      </div>

      {/* 글자를 뺀 점이라 눈으로는 자리만 보입니다. 어느 판인지는 읽어 줄 이름으로만 남깁니다. */}
      <div className="cylinder-dots">
        {slides.map((slide, slideIndex) => (
          <button
            type="button"
            key={slide.key}
            className={slideIndex === index ? 'is-current' : ''}
            aria-label={slide.label}
            aria-pressed={slideIndex === index}
            onClick={() => onIndexChange(slideIndex)}
          />
        ))}
      </div>
    </div>
  );
}
