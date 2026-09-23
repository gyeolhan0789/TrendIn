/*
 * 스크롤 진행도를 뒤따라가는 값.
 *
 * 홈은 한 칸씩 멎는 화면(scroll snap)이라, 한 번 굴리면 스크롤이 300ms 안쪽에 다음 칸까지
 * 건너뜁니다. 그 진행도를 그대로 그림에 넘기면 별이 흩어지는 모습과 어둠이 걷히는 모습이
 * 한 순간에 끝나 버립니다. 스냅으로 얻는 것은 '멎는 자리'이고, 잃고 싶지 않은 것은 '변하는
 * 동안'이라, 둘을 갈라 놓습니다. 스크롤은 곧바로 멎고 그림은 이어서 따라갑니다.
 *
 * 배경과 파티클이 같은 상수를 써야 합니다. 따로 두면 둘이 다른 속도로 밝아져, 별은 아직
 * 어둠 속인데 배경만 먼저 흰 상태가 생깁니다.
 */

/** 1초에 남은 거리의 얼마를 따라잡는지. 2.6이면 90%까지 대략 0.9초입니다. */
export const SCROLL_FOLLOW_PER_SECOND = 2.6;

/** 목표에 닿았다고 볼 거리. 이보다 가까우면 목표값으로 붙이고 따라가기를 멈춥니다. */
export const SCROLL_FOLLOW_EPSILON = 0.001;

/**
 * 한 프레임만큼 목표로 다가갑니다.
 *
 * 프레임 간격을 지수에 넣습니다. `current + (target - current) * k` 처럼 간격을 무시하면
 * 60Hz 와 120Hz 화면에서 따라잡는 속도가 두 배 달라집니다.
 */
export function followStep(current: number, target: number, seconds: number) {
  return current + (target - current) * (1 - Math.exp(-SCROLL_FOLLOW_PER_SECOND * seconds));
}
