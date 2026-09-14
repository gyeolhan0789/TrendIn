/** 새 시안의 공용 푸터. 랜딩과 트렌드 탐색이 같은 모양을 씁니다. */
export function SiteFooter() {
  return (
    <footer className="landing-footer">
      <div className="landing-footer-inner">
        <div className="landing-footer-brand">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" fill="#9ca3af" />
          </svg>
          <span>TrendIn</span>
        </div>
        <p>© {new Date().getFullYear()} TrendIn. 실시간 트렌드 분석 플랫폼</p>
      </div>
    </footer>
  );
}
