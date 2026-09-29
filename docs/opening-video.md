# 발표 오프닝 영상 만들기

PPT 첫 장에 넣을 9.2초짜리 오프닝(1920×1080 · 30fps · MP4)을 뽑는 방법입니다.
앞 6.2초가 연출이고, 나머지 3초는 완성된 로고가 머무는 시간입니다.

랜딩의 파티클 물결을 그대로 쓰되, 검색창·머리말·알림 같은 서비스 UI는 한 조각도 들어가지
않은 별도 화면(`/opening`)을 녹화합니다. 랜딩 화면 자체는 건드리지 않았습니다.

## 연출

| 구간 | 하는 일 |
| --- | --- |
| 0.0 – 0.9초 | 파티클이 화면 곳곳에 흩어진 채로 떠 있습니다 |
| 0.9 – 2.5초 | 흩어진 파티클이 하나의 물결로 모입니다 |
| 2.4 – 2.9초 | 물결이 완성되며 중앙에 카피가 떠오릅니다 |
| 2.9 – 3.8초 | 카피가 머무릅니다. 금색 신호 군집 3개가 카피를 둘러쌉니다 |
| 3.8 – 5.0초 | 빛이 아래에서 위로 차오르며 흰 화면으로 넘어갑니다 |
| 4.1 – 4.5초 | 나머지 입자가 흩어지는 사이, 남은 신호 셋이 **왼쪽부터 차례로 이어집니다** |
| 4.5 – 5.1초 | 이어진 신호가 로고 실루엣 위로 건너갑니다 (금색 → 보라) |
| 4.9 – 5.4초 | 모여든 입자 위로 마크가 떠오릅니다 |
| 5.5 – 6.2초 | 마크가 작아져 왼쪽으로 물러나고, 옆으로 TrendIn 글자가 들어옵니다 |
| 6.2 – 9.2초 | 완성된 로고가 그대로 머무릅니다 (3초) |

전체 빠르기는 [openingTimeline.ts](../frontend/src/pages/OpeningPage/openingTimeline.ts) 의 `PACE`
하나로 조절합니다. 1.0 이 원래 속도이고 클수록 빨라집니다(지금은 1.6). 이 값만 바꾸면 위 구간이
서로의 비율을 지킨 채 함께 줄거나 늘어나므로, 연출을 다시 짤 필요가 없습니다. 마지막 유지
시간은 `FINAL_HOLD` 로 따로 잡아 두어 빠르기와 무관하게 3초를 지킵니다 — 영상 전체를 더
줄이려면 이쪽을 손대면 됩니다.

### 입자가 로고에 정확히 내려앉는 방법

가운데 대목은 "3개의 신호 군집이 로고와 겹친다"입니다. 점을 눈대중으로 찍으면 그림과
어긋나므로, [openingLogo.ts](../frontend/src/pages/OpeningPage/openingLogo.ts) 가 마크 PNG 의
알파를 직접 읽어 실루엣을 뽑습니다. 그 실루엣을 물결(왼쪽·오른쪽)과 위쪽 점, 세 덩어리로
갈라 군집 하나씩 맡기므로 **마크 그림을 갈아 끼워도 좌표가 알아서 따라옵니다**.

쓰는 그림은 두 장입니다.

- 마크: [trendin-wave-mark.png](../frontend/src/assets/trendin-wave-mark.png) — 머리말이 쓰는 것과 같은 파일
- 글자: [trendin-wordmark.png](../frontend/src/pages/OpeningPage/trendin-wordmark.png)

흰 바탕으로 끝나므로, 다음 슬라이드가 흰 배경이면 이어붙인 티가 나지 않습니다.

## 뽑는 순서

### 1. 도구 설치 (처음 한 번)

playwright 와 ffmpeg 는 이 저장소의 의존성이 **아닙니다**. 발표 자료를 만들 때만 쓰는 무거운
꾸러미를 팀 공용 `package.json` 에 얹지 않으려고 일부러 뺐습니다. 아무 폴더에나 설치한 뒤
그 경로를 알려 주면 됩니다.

```bash
mkdir -p ~/opening-tools && cd ~/opening-tools
npm init -y
npm i playwright ffmpeg-static
npx playwright install chromium
```

ffmpeg 가 이미 PATH 에 있다면 `ffmpeg-static` 은 건너뛰어도 됩니다.

### 2. 프런트 dev 서버 띄우기

```bash
cd frontend
npm run dev
```

백엔드는 필요 없습니다. 오프닝 화면은 서버에서 아무것도 받아 오지 않습니다.

### 3. 녹화

```bash
cd frontend
PLAYWRIGHT_PATH=~/opening-tools node scripts/record-opening.mjs
```

PowerShell 이라면:

```powershell
cd frontend
$env:PLAYWRIGHT_PATH = "$HOME\opening-tools"
node scripts/record-opening.mjs
```

끝나면 `frontend/trendin-opening.mp4` 가 생깁니다. 중간 산출물인 PNG 240 장은
`frontend/opening-frames/` 에 남습니다. 둘 다 `.gitignore` 에 있어 저장소에 들어가지 않습니다.

### 바꿔 쓸 수 있는 값

| 환경 변수 | 기본값 | 뜻 |
| --- | --- | --- |
| `PLAYWRIGHT_PATH` | 스크립트가 있는 폴더 | playwright·ffmpeg-static 을 설치한 폴더 |
| `OPENING_URL` | `http://localhost:5173/opening?capture` | 녹화할 주소 |
| `OPENING_OUT` | `opening-frames` | PNG 를 담을 폴더 |
| `OPENING_VIDEO` | `trendin-opening.mp4` | 만들 영상 파일 |
| `OPENING_FPS` | `30` | 초당 프레임 수 |

## 왜 화면 녹화가 아니라 프레임을 한 장씩 받는가

오프닝은 시각 `t` 하나만으로 그림이 정해지도록 짜여 있습니다
([openingTimeline.ts](../frontend/src/pages/OpeningPage/openingTimeline.ts)). 그래서 브라우저에
`t` 를 주고 그려진 판을 받아 오면, 녹화에 몇 분이 걸리든 30fps 가 정확히 떨어집니다. 실시간
화면 녹화처럼 프레임을 흘리거나, 컴퓨터가 잠깐 버벅여 움직임이 끊기는 일이 없습니다.

눈으로 구도만 확인하고 싶을 때는 dev 서버에서 `http://localhost:5173/opening?t=5` 처럼 열면
그 순간 한 장이 멈춘 채로 뜹니다. 그냥 `http://localhost:5173/opening` 으로 열면 실제 속도로
한 번 재생됩니다.

## PPT 에 넣기

파워포인트에서 **삽입 → 비디오 → 이 디바이스**로 `trendin-opening.mp4` 를 고른 뒤,

- 슬라이드를 꽉 채우도록 크기를 맞춥니다 (16:9 그대로라 여백 없이 맞습니다)
- **재생 → 시작: 자동 실행**
- **반복 재생 끄기**, **재생 후 되감기 끄기** — 마지막 흰 프레임이 그대로 남아 있어야
  다음 장으로 자연스럽게 넘어갑니다

발표장 컴퓨터에 영상을 못 넣는 상황이 걱정되면, 같은 폴더의 PNG 중 마지막 장
(`frame-0275.png`)을 표지 이미지로 깔아 두면 영상이 안 돌아도 화면이 비지 않습니다.

## 손보고 싶을 때

- **전체 빠르기** — [openingTimeline.ts](../frontend/src/pages/OpeningPage/openingTimeline.ts) 의
  `PACE` 한 줄. 마지막 유지 시간은 `FINAL_HOLD`.
- **구간별 타이밍** — 같은 파일의 숫자들. 이 값은 "연출 초"라 영상에서는 `PACE` 로 나눈
  시각에 나타납니다. 여기만 바꾸면 영상과 화면이 같이 따라옵니다.
- **카피 글자 크기·위치** — [opening.css](../frontend/src/pages/OpeningPage/opening.css) 의
  `.opening-caption`.
- **물결 높이·색** — [openingWave.ts](../frontend/src/pages/OpeningPage/openingWave.ts) 의
  `uWaveDrop`(물결을 얼마나 내릴지)과 재색 부분의 `keep`(랜딩의 파랑~라벤더 그라데이션을
  얼마나 남길지).
- **카피 둘레 여백** — 같은 파일 셰이더의 `captionClearance`. 카피가 뜰수록 그 둘레 입자가
  비켜서는 폭입니다.
- **로고 크기와 락업 자리** — [openingLogo.ts](../frontend/src/pages/OpeningPage/openingLogo.ts) 의
  `MARK_WIDTH`(떠오를 때 크기), `MARK_LOCKUP_WIDTH`(작아진 뒤 크기), `WORD_SLIDE`(글자가
  밀려 들어오는 거리). 입자가 내려앉는 좌표도 같은 값에서 나오므로 그림과 어긋나지 않습니다.
- **신호가 넘어가는 보랏빛** — [openingWave.ts](../frontend/src/pages/OpeningPage/openingWave.ts)
  프래그먼트의 `signalInk`.
- **신호를 잇는 선** — 같은 파일의 `createLinkGeometry`(알갱이 수 `grains`)와 `linkVertexShader`
  (알갱이 크기), `linkFragmentShader`(색). 선 하나를 긋는 대신 잔 알갱이를 줄지어 세웁니다.
  WebGL 의 선은 두께가 1픽셀에 묶여 1920 폭에서는 실처럼 얇고, 이 화면의 다른 것이 모두
  입자라 점으로 잇는 편이 같은 말을 합니다. 양 끝은 물결 위 무리 한가운데에 붙어 함께
  출렁이므로, 위치를 따로 맞춰 줄 필요가 없습니다.
