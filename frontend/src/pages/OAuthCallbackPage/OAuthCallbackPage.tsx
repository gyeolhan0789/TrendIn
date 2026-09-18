import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { showToast } from '../../components/common/toast';
import { AuthShell } from '../../features/auth/components/AuthShell';
import { describeAuthError } from '../../features/auth/authErrors';
import { consumeOAuthState } from '../../features/auth/api/oauthAuthorize';
import { useOAuthLogin } from '../../features/auth/hooks/useOAuthLogin';

/*
 * 제공자가 프론트엔드 콜백으로 돌려준 code·state를 백엔드에 넘겨 로그인을 마칩니다.
 * 지원 제공자가 확정되기 전이라 이 화면은 provider를 경로에서 그대로 받아 씁니다.
 */
export function OAuthCallbackPage() {
  const { provider = '' } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const oauthLoginMutation = useOAuthLogin();

  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const deniedReason = searchParams.get('error_description') ?? searchParams.get('error');
  // 개발 모드의 이중 실행과 재렌더로 일회용 code를 두 번 쓰지 않도록 한 번만 보냅니다.
  const started = useRef(false);
  const [forgedRequest, setForgedRequest] = useState(false);

  useEffect(() => {
    if (started.current || !provider || !code || !state) return;
    started.current = true;

    /*
     * state 대조는 서버가 하지 않습니다. 인가 URL 을 만든 쪽이 화면이라 서버는 발급한 값을
     * 알지 못합니다. 그래서 떠나기 전에 심어 둔 값과 여기서 맞춰 봐야, 남이 쥐여 준 링크로 들어온
     * 콜백이 그대로 로그인으로 이어지는 일을 막을 수 있습니다. 심어 둔 값이 아예 없어도 막습니다.
     */
    if (consumeOAuthState(provider) !== state) {
      setForgedRequest(true);
      return;
    }

    oauthLoginMutation
      .mutateAsync({ provider, code, state })
      .then((result) => {
        showToast({
          message: result.isNewMember ? '가입을 마쳤습니다. 먼저 관심 분야를 골라 주세요.' : '로그인했습니다.',
          type: 'success',
        });
        navigate(result.onboardingCompleted ? '/' : '/onboarding', { replace: true });
      })
      .catch(() => undefined);
  }, [code, navigate, oauthLoginMutation, provider, state]);

  const missingGrant = !code || !state;
  const failure = deniedReason
    ?? (missingGrant ? '인증 정보가 없어 로그인을 마치지 못했습니다.' : undefined)
    ?? (forgedRequest ? '이 브라우저에서 시작한 로그인인지 확인하지 못했습니다. 로그인 화면에서 다시 시도해 주세요.' : undefined)
    ?? (oauthLoginMutation.isError ? describeAuthError(oauthLoginMutation.error, '소셜 로그인에 실패했습니다.') : undefined);

  return (
    <AuthShell
      eyebrow="SIGN IN"
      title={failure ? '로그인을 마치지 못했습니다' : '로그인하는 중입니다'}
      description={failure ?? '제공자에게 받은 인증 정보를 확인하고 있습니다. 잠시만 기다려 주세요.'}
      footer={failure ? <Link to="/login">로그인 화면으로 돌아가기</Link> : undefined}
    >
      {!failure && <div className="auth-progress" aria-label="불러오는 중"><span /><span /><span /></div>}
    </AuthShell>
  );
}
