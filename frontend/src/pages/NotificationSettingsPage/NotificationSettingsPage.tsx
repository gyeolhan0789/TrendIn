import { useState } from 'react';
import { Link } from 'react-router-dom';
import { getApiErrorMessage } from '../../api/apiResponse';
import { ToggleSwitch } from '../../components/common/ToggleSwitch';
import { showToast } from '../../components/common/toast';
import { MyPageCard, MyPageCrumb, MyPageRow, MyPageScreen } from '../../features/myPage/components/MyPageShell';
import { SurgeIcon } from '../../features/myPage/components/myPageIcons';
import {
  useNotificationSettings,
  useUpdateNotificationSettings,
} from '../../features/notification/hooks/useNotificationSettings';
import {
  defaultNotificationSettings,
  updateNotificationSetting,
  type NotificationSettingKey,
  type NotificationSettings,
} from '../../features/notification/types/notificationSettings';

const trendRows: { key: NotificationSettingKey; title: string; desc: string }[] = [
  { key: 'keywordSurgeEnabled', title: '키워드 급등 알림', desc: '관심 키워드 검색량이 급등하면 즉시 알림' },
  { key: 'keywordDropEnabled', title: '키워드 급락 알림', desc: '관심 키워드 검색량이 급락하면 알림' },
  { key: 'newTrendEnabled', title: '신규 트렌드 발견', desc: '새로운 트렌드가 감지되면 알림' },
  { key: 'trendTurningPointEnabled', title: '트렌드 전환점 알림', desc: '트렌드 유형이 바뀌면 알림' },
];

function NotificationSettingsForm({ saved }: { saved: NotificationSettings }) {
  const [draft, setDraft] = useState(saved);
  const updateMutation = useUpdateNotificationSettings();
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);

  const save = () => {
    updateMutation.mutate(draft, {
      onSuccess: () => showToast({ message: '알림 설정을 저장했습니다.', type: 'success' }),
      onError: (error) => showToast({
        message: getApiErrorMessage(error) ?? '알림 설정을 저장하지 못했습니다.',
        type: 'error',
      }),
    });
  };

  return (
    <>
      <MyPageCard title="트렌드 알림" tone="rose" icon={<SurgeIcon />}>
        <div className="mypage-rows">
          {trendRows.map((row) => (
            <MyPageRow key={row.key} title={row.title} description={row.desc}>
              <ToggleSwitch
                checked={draft[row.key]}
                disabled={updateMutation.isPending}
                label={row.title}
                onChange={(on) => setDraft((current) => updateNotificationSetting(current, row.key, on))}
              />
            </MyPageRow>
          ))}
        </div>
      </MyPageCard>

      <div className="mypage-actions">
        <Link className="mypage-btn mypage-btn--ghost" to="/mypage">돌아가기</Link>
        <button
          type="button"
          className="mypage-btn mypage-btn--primary"
          disabled={!dirty || updateMutation.isPending}
          onClick={save}
        >
          {updateMutation.isPending ? '저장 중…' : '저장'}
        </button>
      </div>
    </>
  );
}

export function NotificationSettingsPage() {
  const settingsQuery = useNotificationSettings();
  const settings = settingsQuery.data ?? defaultNotificationSettings;

  return (
    <MyPageScreen width="md">
      <MyPageCrumb current="알림 설정" />
      <div className="mypage-head trendin-page-heading">
        <h1>알림 설정</h1>
        <p>받고 싶은 트렌드 알림을 세부적으로 관리하세요.</p>
      </div>

      {settingsQuery.isPending && <div className="trendin-state">알림 설정을 불러오는 중입니다.</div>}
      {!settingsQuery.isPending && (
        <NotificationSettingsForm key={JSON.stringify(settings)} saved={settings} />
      )}
    </MyPageScreen>
  );
}
