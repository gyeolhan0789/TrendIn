import { useEffect, useRef } from 'react';
import markImage from '../../assets/trendin-wave-mark.png';
import wordImage from './trendin-wordmark.png';
import {
  MARK_LOCKUP_SHIFT, MARK_LOCKUP_WIDTH, MARK_WIDTH, WORD_SHIFT, WORD_SLIDE, WORD_WIDTH,
  loadMarkShape,
} from './openingLogo';
import { SIGNAL_COUNTS, createOpeningWave, type OpeningWave } from './openingWave';
import { OPENING_DURATION, openingFrameAt, type OpeningFrame } from './openingTimeline';
import './opening.css';

declare global {
  interface Window {
    /* 녹화용 손잡이. 아래 record-opening.mjs 가 프레임마다 seek 을 부릅니다. */
    __opening?: { duration: number; seek: (seconds: number) => void };
  }
}

/*
 * PPT 첫 장에 넣을 오프닝입니다. 랜딩과 같은 물결을 쓰지만 서비스 UI 는 한 조각도 없고,
 * 들어오자마자 저절로 한 번 재생되고 끝납니다.
 *
 * 마지막 대목이 이 화면의 핵심입니다. 화면이 밝아지는 동안 물결 위의 금색 신호 무리 셋이
 * 흩어지지 않고 로고 실루엣 위로 건너가 금색에서 보라로 물들고, 그 위로 마크가 떠오릅니다.
 * 그다음 마크가 작아져 왼쪽으로 물러나고 옆으로 TrendIn 글자가 들어옵니다.
 *
 * 주소에 ?capture 를 붙이면 제 시계를 멈추고 window.__opening.seek 이 주는 시각만 그립니다.
 * 녹화기가 프레임을 하나씩 당겨 갈 수 있어야 30fps 가 흔들림 없이 떨어집니다. ?t=7.4 처럼
 * 주면 그 순간 한 장만 세워 두므로, 구도를 눈으로 볼 때 씁니다.
 */
export function OpeningPage() {
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const stage = stageRef.current;
    const canvas = canvasRef.current;
    if (!stage || !canvas) return;

    let wave: OpeningWave | null = null;
    let animationFrame = 0;
    let disposed = false;
    const onResize = () => wave?.resize();

    const applyFrame = (frame: OpeningFrame) => {
      /*
       * 바탕색은 빛의 제곱으로 늦게 따라옵니다. 그냥 비례로 두면 화면 전체가 고르게 흐려져
       * 위쪽이 잿빛으로 뜨고, 아래에서 차오른다는 느낌이 사라집니다. 랜딩 머리말이 같은
       * 이유로 eased² 를 쓰고 있습니다.
       */
      stage.style.setProperty('--opening-light', `${frame.light * frame.light * 100}%`);
      stage.style.setProperty('--opening-dark', `${1 - frame.light}`);
      stage.style.setProperty('--opening-caption', `${frame.caption}`);
      /*
       * 랜딩은 화면 전체를 한 번에 밝히지만, 오프닝은 빛이 아래에서 위로 차오릅니다. 흰 면의
       * 윗선을 화면 밖(-50%)에서 시작해 화면 위(120%)까지 밀어 올리고, 그 위로 46% 만큼
       * 흐리게 풀어 선이 보이지 않게 합니다.
       */
      const front = frame.light * 170 - 50;
      stage.style.setProperty('--opening-sweep-solid', `${front}%`);
      stage.style.setProperty('--opening-sweep-mid', `${front + 22}%`);
      stage.style.setProperty('--opening-sweep-edge', `${front + 46}%`);

      /*
       * 로고 상자의 폭과 자리. 입자가 내려앉는 좌표는 셰이더가 같은 상수로 따로 계산하므로,
       * 둘은 반드시 같은 값에서 나와야 합니다. 크기는 transform 이 아니라 폭을 직접 바꿔
       * 줄입니다. translate(-50%) 로 가운데를 잡고 있어, 폭이 변해도 중심이 흔들리지 않습니다.
       */
      const markWidth = MARK_WIDTH + (MARK_LOCKUP_WIDTH - MARK_WIDTH) * frame.lockup;
      stage.style.setProperty('--mark-opacity', `${frame.mark}`);
      stage.style.setProperty('--mark-width', `${markWidth * 100}vw`);
      stage.style.setProperty('--mark-shift', `${MARK_LOCKUP_SHIFT * frame.lockup * 100}vw`);
      stage.style.setProperty('--word-opacity', `${frame.word}`);
      stage.style.setProperty('--word-width', `${WORD_WIDTH * 100}vw`);
      stage.style.setProperty('--word-shift', `${(WORD_SHIFT + (1 - frame.word) * WORD_SLIDE) * 100}vw`);
      stage.style.setProperty('--canvas-opacity', `${frame.settle}`);

      wave?.renderAt(frame);
    };

    const parameters = new URLSearchParams(window.location.search);
    const still = parameters.get('t');
    const captureMode = parameters.has('capture');

    /*
     * 로고 실루엣을 읽어야 입자가 갈 자리를 정할 수 있어, 물결은 그림을 받은 뒤에 세웁니다.
     * 녹화기는 window.__opening 이 생기기를 기다리므로, 이 준비가 끝나기 전에 프레임을
     * 가져가는 일은 없습니다.
     */
    loadMarkShape(SIGNAL_COUNTS).then((markShape) => {
      if (disposed) return;
      wave = createOpeningWave(canvas, markShape);
      window.addEventListener('resize', onResize);

      if (captureMode || still !== null) {
        /* 시계를 돌리지 않습니다. 밖에서 준 시각만 그리므로 몇 번을 그려도 같은 그림입니다. */
        window.__opening = { duration: OPENING_DURATION, seek: (seconds) => applyFrame(openingFrameAt(seconds)) };
        applyFrame(openingFrameAt(still === null ? 0 : Number(still) || 0));
        stage.dataset.openingReady = 'true';
        return;
      }

      /* 되감기 없이 한 번만 흐릅니다. 마지막 프레임은 그대로 세워 둡니다. */
      let start = 0;
      const draw = (now: number) => {
        if (!start) start = now;
        const elapsed = Math.min((now - start) / 1000, OPENING_DURATION);
        applyFrame(openingFrameAt(elapsed));
        if (elapsed < OPENING_DURATION) animationFrame = window.requestAnimationFrame(draw);
        else stage.dataset.openingReady = 'done';
      };
      animationFrame = window.requestAnimationFrame(draw);
    });

    document.body.classList.add('opening-body');
    return () => {
      disposed = true;
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', onResize);
      document.body.classList.remove('opening-body');
      delete window.__opening;
      wave?.dispose();
    };
  }, []);

  return (
    <div className="opening-stage" ref={stageRef}>
      <div className="opening-nebula" aria-hidden="true" />
      <div className="opening-sweep" aria-hidden="true" />
      <canvas className="opening-canvas" ref={canvasRef} aria-hidden="true" />
      <p className="opening-caption">흐름 속에서,<br />새로운 신호를 발견하다.</p>
      {/* 모여든 입자 위로 떠오르는 마크. 그 뒤 작아지며 왼쪽으로 물러납니다. */}
      <img className="opening-mark" src={markImage} alt="" aria-hidden="true" />
      <img className="opening-word" src={wordImage} alt="" aria-hidden="true" />
    </div>
  );
}
