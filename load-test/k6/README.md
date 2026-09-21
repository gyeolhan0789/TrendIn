# k6 측정

엔드포인트를 하나씩 격리해 한계를 찾는다. 사용자 여정 시나리오는 이 다음 단계다.

```bash
cd ~/S15P21A102/load-test/k6
./run.sh                             # 전부 (엔드포인트당 3분, 총 25분쯤)
./run.sh endpoint/notifications.js   # 하나만
PEAK_RPS=300 ./run.sh endpoint/notifications.js
```

결과는 `results/<이름>-<시각>.txt` 에 남는다.

## 왜 EC2 에서 돌리나

대상이 `127.0.0.1:18080` 에만 열려 있다. 밖에서 닿지 않는다. SSH 터널로 로컬에서
돌리면 p95 가 서버 성능이 아니라 인터넷 왕복 시간을 재게 된다.

대가로 k6 가 같은 CPU 를 쓴다. Grafana 의 CPU 패널에서 **프로세스(백엔드)는 여유가
있는데 시스템만 1 에 붙으면 k6 가 병목**이라는 뜻이다. 그때 나온 숫자는 서버의
한계가 아니므로 `PEAK_RPS` 를 낮춰 다시 잰다.

## 한계를 찾는 법

`PEAK_RPS` 를 올려 가며 다시 돌린다. **응답시간이 꺾이고 에러가 붙기 시작하는
지점**이 그 엔드포인트의 한계다. 한 번 돌려 나온 p95 하나는 한계가 아니다.

`ramping-arrival-rate` 를 쓴다. 고정 VU 로 재면 서버가 느려질 때 요청도 같이
느려져 부하가 저절로 줄고, 포화점이 그래프에서 사라진다.

## 토큰을 미리 받는 이유

`setup()` 에서 토큰 50개를 발급해 VU 들이 나눠 쓴다. VU 마다 로그인시키면 bcrypt
해싱이 CPU 를 차지해 **로그인이 가짜 병목**으로 잡힌다. 실제 사용자도 15분짜리
토큰으로 여러 번 조회한다. 로그인 비용은 `endpoint/auth-login.js` 에서만 잰다.

## 스크립트

| 스크립트 | 무엇을 보나 | 기본 RPS |
| --- | --- | ---: |
| `trends-list.js` | 인증 없는 목록. 다른 측정의 기준선 | 200 |
| `trend-contents.js` | `keyword_contents` 가 `keyword_id` 단독 조회를 받는다 | 100 |
| `notifications.js` | **`notifications` 에 `member_id` 인덱스가 없다** | 100 |
| `saved-trends.js` | 인덱스가 있는 개인화 조회. 비교군 | 100 |
| `trend-history.js` | 450만 행 위의 기간별 조회 | 100 |
| `trend-regions.js` | 242만 행 + `journey` 의 나라별 집계 | 50 |
| `auth-login.js` | bcrypt. 데이터 양과 무관한 비용 | 30 |

**헤비 회원으로 잰다.** 시드가 회원을 `id % 100` 으로 갈라, 95~99 인 회원에게
알림 300~1,500건과 저장 100~500건을 몰아줬다. 평균 회원만 재면 문제가 드러나지
않는다. `lib/config.js` 의 `heavyMemberId()` 가 그 규칙에서 id 를 계산한다 —
특정 id 를 박아 두면 시드 규모를 바꿀 때 조용히 어긋나기 때문이다.

**상위 트렌드를 고른다.** 콘텐츠의 70% 와 국가 데이터 전부가 상위 2,000 개
키워드에 몰려 있다. 그 밖을 고르면 빈 결과가 와서 아무것도 재지 못한다.

## Grafana 와 함께 보기

k6 의 터미널 요약은 클라이언트가 본 것이고, 서버 안에서 무슨 일이 있었는지는
Grafana **TrendIn 부하테스트** 대시보드가 보여준다. 상단 `대상` 을
`backend-loadtest` 로 두고 본다.

특히 **HikariCP 대기(pending)** 를 본다. 0 을 넘으면 커넥션 풀이 마른 것이고,
그때는 API 코드를 아무리 고쳐도 소용없다.

k6 결과까지 같은 그래프에 얹으려면 remote write 로 밀어넣는다. Phase 0 에서
Prometheus 에 수신을 켜 뒀다.

```bash
export K6_PROMETHEUS_RW_SERVER_URL=http://localhost:9090/api/v1/write
export K6_OUT=experimental-prometheus-rw   # k6 버전에 따라 이름이 다르다
./run.sh
```

출력 이름이 맞지 않으면 k6 가 시작하며 거절한다. 그때는 이 줄만 빼면 터미널
요약과 `results/*.txt` 로 충분하다.

## 종료 코드

| 코드 | 뜻 |
| --- | --- |
| 0 | 임계값을 모두 통과 |
| 99 | 임계값 초과. **측정은 정상이다** — 한계를 찾는 중이라면 이것이 정상 결과다 |
| 그 밖 | 실행 실패. 대상이 떴는지, 시드가 들어갔는지 본다 |
