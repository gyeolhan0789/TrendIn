# 2. 외부 서비스

> **로컬에서 띄워 보실 거라면 아무것도 가입하지 않아도 됩니다.** 아래 서비스는 모두 선택이거나 서버 운영에만 쓰입니다.

| 서비스 | 용도 | 가입 | 언제 필요한가 |
| --- | --- | :---: | --- |
| **SSAFY GitLab OAuth** | 소셜 로그인 | 필요 | 선택 — 없으면 **이메일 로그인만** 동작 |
| **SSAFY GMS (OpenAI 게이트웨이)** | 트렌드 AI 해설 생성 | 필요 | **파이프라인을 직접 돌릴 때만.** 로컬·덤프 복원에는 불필요 |
| **Let's Encrypt** | HTTPS 인증서 | 무료·자동 | 자체 도메인에 HTTPS 로 올릴 때만 |
| **수집 대상 매체 42곳** | 기사 수집 | 불필요 | 공개 RSS·API |

**유료 결제가 필요한 서비스는 없습니다.** GitLab 과 GMS 는 SSAFY 가 제공하는 자원입니다.

---

## 1. SSAFY GitLab OAuth (선택)

이메일 회원가입 외에 GitLab 계정으로 로그인하는 경로입니다. **키가 비어 있어도 서버는 정상 기동하고 이메일 로그인은 그대로 됩니다.**

### 발급 절차

1. <https://lab.ssafy.com> 로그인
2. 프로필 → **Edit profile** → **Applications** → **Add new application**

| 항목 | 값 |
| --- | --- |
| Name | `TrendIn` |
| Redirect URI | 아래 「값을 넣는 곳」과 같은 주소 |
| Confidential | 체크 |
| Scopes | `read_user` **만** |

3. 저장 시 나오는 **Application ID** 와 **Secret** 을 복사합니다. Secret 은 이때 한 번만 보입니다.

### 값을 넣는 곳

```sh
# infra/.env  (백엔드)
GITLAB_OAUTH_CLIENT_ID=<Application ID>
GITLAB_OAUTH_CLIENT_SECRET=<Secret>
GITLAB_OAUTH_REDIRECT_URI=http://localhost:5173/oauth/gitlab/callback

# frontend/.env.local  (프론트)
VITE_GITLAB_OAUTH_BASE_URL=https://lab.ssafy.com
VITE_GITLAB_OAUTH_CLIENT_ID=<Application ID — 백엔드와 같은 값>
VITE_GITLAB_OAUTH_REDIRECT_URI=http://localhost:5173/oauth/gitlab/callback
```

> ⚠️ **Redirect URI 는 세 곳이 글자 하나까지 같아야 합니다** — GitLab 등록값 · `infra/.env` · `frontend/.env.local`. 끝 슬래시 하나만 달라도 토큰 교환이 거절됩니다.
>
> 서버에 올릴 때는 세 곳 모두 그 도메인 주소로 바꿉니다 (예: `https://j15a102.p.ssafy.io/oauth/gitlab/callback`).

---

## 2. SSAFY GMS — OpenAI 게이트웨이

트렌드마다 **정의 · 주요 흐름 · 주목받는 이유**를 생성합니다.

**수집·분석 파이프라인을 직접 돌릴 때만 필요합니다.** 로컬 실행은 시드 데이터에, DB 덤프 복원은 이미 생성된 해설에 각각 AI 분석이 들어 있어 키가 없어도 화면에 그대로 나옵니다.

| 항목 | 값 |
| --- | --- |
| 엔드포인트 | `https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions` |
| 모델 | `gpt-5.4-nano` |
| 정의 위치 | `pipeline/src/trendin/ai/client.py` |

SSAFY 에서 배포한 GMS API 키를 `pipeline/.env` 에 넣습니다.

```sh
GMS_KEY=<발급받은 키>
```

코드는 키 값을 저장하지 않습니다. 컴포즈가 환경 변수로 주입하고 실행 시점에 읽습니다.

---

## 3. Let's Encrypt (서버 운영 시에만)

무료이며 별도 계정이 없습니다. 도메인 소유만 증명하면 됩니다.

```sh
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d <도메인>
```

인증서는 `/etc/letsencrypt/live/<도메인>/` 에 생기고, 자동 갱신은 certbot 이 등록하는 systemd timer 가 합니다.

> `infra/nginx/trendin.conf` 의 80 포트 블록이 `.well-known/acme-challenge/` 를 통과시킵니다. **그 블록을 지우면 갱신이 실패합니다.**

---

## 4. 수집 대상 매체 (가입 불필요)

공개된 RSS 피드와 목록 페이지에서 받습니다. API 키나 계약이 필요한 곳은 없습니다.

| 분야 | 소스 | 방식 | 정의 위치 |
| --- | --- | --- | --- |
| 패션 | **41곳** (RSS 39 + 목록 2) | RSS·목록 페이지 파싱 | `pipeline/src/trendin/fashion/collect/sources/` |
| 개발 | 1곳 | Algolia HN Search API (인증 불필요) | `pipeline/src/trendin/dev/collect/sources.py` |

Vogue(KR/US/UK/FR/IT/JP), Harper's Bazaar, Cosmopolitan, Elle, GQ, W Korea, Marie Claire, Dazed, Hypebeast, Highsnobiety, Numéro, L'Officiel 등입니다. 소스 하나가 TOML 파일 하나이며, 더하거나 빼는 일은 파일을 더하거나 지우는 것입니다.

---

## 5. 사용하지 않는 외부 서비스

| 항목 | 사용 |
| --- | :---: |
| 포톤 클라우드(Photon) | ❌ 실시간 멀티플레이 기능 없음 |
| 코드 컴파일 서비스 | ❌ 사용자 코드 실행 기능 없음 |
| 결제 PG | ❌ |
| 지도 API (카카오·구글) | ❌ 국가별 트렌드 지도는 **자체 SVG·Three.js 렌더링** |
| 푸시 알림(FCM 등) | ❌ 알림은 서비스 내부에만 쌓임 |
| S3 등 클라우드 스토리지 | ❌ **자체 호스팅 MinIO** 사용 |
