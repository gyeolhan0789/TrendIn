/*
 * 소셜 로그인 API(/auth/oauth/{provider}/login)는 계약만 확정됐고 지원 제공자는 아직 정해지지 않았습니다.
 * 누를 수 없는 제공자 버튼을 늘어놓는 대신, 마이페이지 사이드바처럼 준비 중이라고 밝힙니다.
 */
export function SocialLoginNotice() {
  return (
    <div className="auth-social">
      <span className="auth-divider"><i />또는<i /></span>
      <p>소셜 로그인은 준비 중입니다.</p>
    </div>
  );
}
