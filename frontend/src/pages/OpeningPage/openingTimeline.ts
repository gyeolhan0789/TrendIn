/*
 * PPT 첫 장에 쓸 오프닝의 시간표입니다.
 *
 * 화면에 그릴 값은 모두 이 함수 하나가 "지금 몇 초인가" 만으로 정합니다. 누적 상태가 없어야
 * 실시간 재생과 프레임 단위 캡처가 같은 그림을 내고, 녹화한 영상이 매번 똑같이 나옵니다.
 */
/*
 * 아래 함수의 숫자들은 "연출 초"입니다. 실제 영상은 그보다 PACE 배 빠르게 흐릅니다. 연출을
 * 짜고 고치는 단위와, 다 만든 뒤 전체 속도를 조절하는 손잡이를 갈라 둔 것입니다. 빠르기만
 * 바꾸고 싶으면 PACE 하나만 건드리면 됩니다 — 1.0 이 원래 속도, 클수록 빨라집니다.
 */
const PACE = 1.6;
/** 마지막 연출(글자 등장)이 끝나는 연출 시각. */
const CHOREOGRAPHY_END = 9.9;
/** 다 선 로고를 그대로 두는 시간. 여기는 빠르기와 무관한 실제 초입니다. */
const FINAL_HOLD = 3;

export const OPENING_DURATION = CHOREOGRAPHY_END / PACE + FINAL_HOLD;

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const ease = (value: number) => { const t = clamp(value); return t * t * (3 - 2 * t); };

export type OpeningFrame = {
  time: number;
  /** 1이면 파티클이 화면 곳곳에 흩어진 상태, 0이면 물결이 완성된 상태입니다. */
  scatter: number;
  /** 0이면 어두운 우주, 1이면 흰 화면입니다. */
  light: number;
  /** 중앙 카피의 불투명도. */
  caption: number;
  /** 1이면 신호 무리가 흩어지지 않고 물결 위 제자리를 지킵니다. */
  hold: number;
  /** 신호 셋을 잇는 선이 왼쪽에서 오른쪽으로 그려진 정도. */
  link: number;
  /** 이어진 선이 남아 있는 정도. */
  linkFade: number;
  /** 0이면 신호 무리가 물결 위에, 1이면 로고 모양에 정확히 올라앉습니다. */
  gather: number;
  /** 0이면 신호가 금색, 1이면 로고의 보랏빛입니다. */
  logoTint: number;
  /** 모였던 입자가 사라지는 정도. 1이면 그대로, 0이면 다 빠진 상태입니다. */
  signal: number;
  /** 로고 그림의 불투명도. */
  mark: number;
  /** 0이면 로고가 가운데 크게, 1이면 작아져 왼쪽에 선 상태입니다. */
  lockup: number;
  /** TrendIn 글자가 들어온 정도. */
  word: number;
  /** 물결 캔버스가 남아 있는 정도. 0이면 로고만 남고 배경은 깨끗한 흰색입니다. */
  settle: number;
};

export function openingFrameAt(seconds: number): OpeningFrame {
  /*
   * 물결 자체의 출렁임도 같은 시계를 쓰므로(uTime), 연출만 빨라지고 배경만 느긋한 어긋남이
   * 생기지 않습니다. 화면 전체가 한 속도로 흐릅니다.
   */
  const time = seconds * PACE;
  return {
    time,
    // 1.5초까지는 흩어진 채로 두고, 그 뒤 2.5초에 걸쳐 물결로 모입니다.
    scatter: 1 - ease((time - 1.5) / 2.5),
    // 6초부터 2초 동안 밝아집니다. 이 밝아짐 위에서 로고가 떠오릅니다.
    light: ease((time - 6) / 2),
    // 선이 그려지기 전에 비켜 줘야 합니다. 겹쳐 있으면 선이 글자를 가로지릅니다.
    caption: ease((time - 3.8) / .8) * (1 - ease((time - 6.1) / .5)),
    /*
     * 화면이 밝아지면 나머지 입자는 흩어져 사라지지만, 신호 셋만은 제자리를 지킵니다. 이걸
     * 걸어 두지 않으면 선을 그을 때쯤 무리가 이미 풀어져, 이을 점이 남아 있지 않습니다.
     * 빛이 들기 전(5.8초)에 미리 걸어야 자리가 튀지 않습니다.
     */
    hold: ease((time - 5.8) / .5),
    /*
     * 남은 신호 셋이 왼쪽부터 차례로 이어집니다. 로고로 모이기 직전의 짧은 한 박자라,
     * 0.6초에 다 긋고 곧바로 다음으로 넘어갑니다.
     */
    link: ease((time - 6.6) / .6),
    linkFade: 1 - ease((time - 7.4) / .6),
    /*
     * 이어진 신호가 그대로 로고 자리로 건너갑니다. 색은 선이 그려지는 동안 이미 보라로
     * 넘어가기 시작해, 금색이 로고가 되는 흐름이 한 줄로 이어집니다.
     */
    gather: ease((time - 7.15) / 1),
    logoTint: ease((time - 6.7) / .8),
    // 입자가 아직 로고 자리에 있는 동안 그림이 겹쳐 떠오르고, 그 뒤 입자만 조용히 빠집니다.
    mark: ease((time - 7.9) / .7),
    signal: 1 - ease((time - 8.15) / .6),
    // 로고가 홀로 선 뒤, 작아지며 왼쪽으로 물러나고 그 옆으로 글자가 들어옵니다.
    lockup: ease((time - 8.8) / .8),
    word: ease((time - 9.1) / .8),
    /*
     * 물결에서 솎아지고 남은 잔 입자들입니다. 흰 바탕 위에서는 먼지처럼 보여, 로고가 자리를
     * 잡는 동안 같이 걷어 냅니다. 마지막 프레임은 로고 말고 아무것도 없는 흰 화면입니다.
     */
    settle: 1 - ease((time - 8.8) / 1),
  };
}
