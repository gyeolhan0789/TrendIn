import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { ErrorState } from '../../components/common/ErrorState';
import { showToast } from '../../components/common/toast';
import { AuthShell } from '../../features/auth/components/AuthShell';
import { getAuthSession } from '../../features/auth/api/authSessionStorage';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';
import { describeAuthError } from '../../features/auth/authErrors';
import { DomainChoice } from '../../features/onboarding/components/DomainChoice';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import { useUpdateMyDomains } from '../../features/onboarding/hooks/useUpdateMyDomains';

export function OnboardingPage() {
  const session = useAuthSession();
  const navigate = useNavigate();
  const domainsQuery = useDomains();
  const myDomainsQuery = useMyDomains(Boolean(session));
  const updateMutation = useUpdateMyDomains();

  const [selected, setSelected] = useState<string[]>([]);
  const [formError, setFormError] = useState<string>();
  // 고른 분야를 한 번만 켜 둡니다. 이후에는 사용자가 누른 것이 이깁니다.
  const [seeded, setSeeded] = useState(false);

  // 고친 뒤 다시 들어오는 경우가 있어, 이미 고른 분야를 켜 둔 채로 시작합니다.
  useEffect(() => {
    if (seeded || !myDomainsQuery.data) return;
    setSelected(myDomainsQuery.data.map((option) => option.domain));
    setSeeded(true);
  }, [myDomainsQuery.data, seeded]);

  const toggle = (domain: string) => {
    setFormError(undefined);
    setSelected((current) => (current.includes(domain)
      ? current.filter((value) => value !== domain)
      : [...current, domain]));
  };

  const submit = async () => {
    if (selected.length === 0) {
      setFormError('관심 분야는 최소 1개 이상 선택해야 합니다.');
      return;
    }
    setFormError(undefined);

    try {
      await updateMutation.mutateAsync(selected);
      showToast({ message: '관심 분야를 저장했습니다.', type: 'success' });
      navigate('/', { replace: true });
    } catch (error) {
      setFormError(describeAuthError(error, '관심 분야를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.'));
    }
  };

  // 로그인해야 고른 분야를 저장할 수 있습니다.
  if (!getAuthSession()) return <Navigate to="/login" state={{ from: '/onboarding' }} replace />;

  const options = domainsQuery.data ?? [];
  const loading = domainsQuery.isLoading || (myDomainsQuery.isLoading && !myDomainsQuery.isError);

  return (
    <AuthShell
      eyebrow="ONBOARDING"
      title="어떤 분야를 보시겠어요?"
      description="고른 분야의 트렌드만 모아서 보여 드립니다. 하나 이상 골라 주세요. 나중에 언제든 바꿀 수 있습니다."
    >
      {domainsQuery.isError && (
        <ErrorState message="분야 목록을 불러오지 못했습니다." onRetry={() => domainsQuery.refetch()} />
      )}

      {!domainsQuery.isError && loading && (
        <div className="auth-progress" aria-label="불러오는 중"><span /><span /><span /></div>
      )}

      {!domainsQuery.isError && !loading && (
        <>
          <div className="onboarding-choices" role="group" aria-label="관심 분야">
            {options.map((option) => (
              <DomainChoice
                key={option.domain}
                option={option}
                selected={selected.includes(option.domain)}
                disabled={updateMutation.isPending}
                onToggle={toggle}
              />
            ))}
          </div>

          <p className="onboarding-count">{selected.length}개 선택함</p>

          {formError && <p className="auth-alert" role="alert">{formError}</p>}

          <Button className="auth-submit" type="button" isLoading={updateMutation.isPending} onClick={submit}>
            {updateMutation.isPending ? '저장하는 중…' : '시작하기'}
          </Button>
        </>
      )}
    </AuthShell>
  );
}
