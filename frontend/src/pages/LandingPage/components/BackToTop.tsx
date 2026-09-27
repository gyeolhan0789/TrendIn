import { useEffect, useState } from 'react';

/**
 * 맨 위로 올라가는 단추. 히어로를 벗어나면 오른쪽 아래에 떠 있습니다.
 *
 * 홈은 한 번 굴리면 한 칸씩 넘어가서(useSectionGlide), 콘텐츠 칸이나 푸터에서 검색창으로
 * 돌아가려면 칸 수만큼 거꾸로 굴려야 했습니다. 이 단추가 그 길을 한 번에 줄여 줍니다.
 *
 * 올라가는 움직임은 브라우저의 부드러운 스크롤에 맡깁니다. 칸 넘김은 우리가 옮기지 않은
 * 스크롤이 멎으면 가장 가까운 칸으로 붙잡는데, 맨 위가 곧 첫 칸이라 붙잡을 것이 없습니다.
 */
export function BackToTop() {
  const [shown, setShown] = useState(false);

  useEffect(() => {
    /* 히어로의 절반을 지나면 띄웁니다. 첫 화면에서는 이미 맨 위라 띄울 이유가 없습니다. */
    const update = () => setShown(window.scrollY > window.innerHeight * 0.5);
    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, []);

  const toTop = () => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
  };

  return (
    <button
      type="button"
      className={`back-to-top${shown ? ' is-shown' : ''}`}
      onClick={toTop}
      aria-label="맨 위로"
      title="맨 위로"
      /* 숨어 있는 동안에는 탭 순서에서도 빠져야 합니다. 보이지 않는 단추에 초점이 가면 헤맵니다. */
      tabIndex={shown ? 0 : -1}
      aria-hidden={!shown}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
    </button>
  );
}
