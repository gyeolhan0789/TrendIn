import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FilterSelect } from '../../../components/common/FilterSelect';
import { useTrends } from '../../../features/trend/hooks/useTrends';
import { useTrendDetailLink } from '../../../features/trend/trendDetailLink';
import { formatGrowth } from '../../../features/trend/trendFormat';
import type { PeriodCode } from '../../../constants/filterCodes';
import type { Trend, TrendType } from '../../../features/trend/types/trend';
import type { LandingDomain } from '../useLandingDomain';

/*
 * 랜딩의 '오늘의 트렌드'. 판 셋이 서버의 갈래 셋과 1:1 입니다.
 * tone 은 시안이 정한 판 색이라 갈래 이름과 다릅니다. 손대면 판 색이 서로 바뀝니다.
 */
const BOARDS: readonly { type: TrendType; tone: string; title: string }[] = [
  { type: 'CURRENT', tone: 'rising', title: '인기 트렌드' },
  { type: 'NEW', tone: 'new', title: '신규 트렌드' },
  { type: 'RISING', tone: 'returning', title: '급상승 트렌드' },
];

const BOARD_PERIOD: PeriodCode = '24H';
/** 판 하나에 세 줄. 시안이 정한 줄 수이고, 그만큼만 받아 옵니다. */
const BOARD_SIZE = 3;

type OpenDetail = ReturnType<typeof useTrendDetailLink>;

/** 분야는 아래 콘텐츠 구역과 함께 써야 해서 바깥(useLandingDomain)에서 받아 옵니다. */
export function TodayTrends({ domains, domain, options, pick, noChosenDomain, loggedIn }: LandingDomain) {
  const location = useLocation();
  const navigate = useNavigate();
  const openDetail = useTrendDetailLink();

  /*
   * 상세는 토큰이 있어야 열립니다. 눌러 보고 가드에 막히는 대신 미리 로그인으로 보내고,
   * 로그인을 마치면 보던 자리로 돌아오도록 지금 주소를 함께 넘깁니다.
   */
  const requireLogin = () => {
    if (loggedIn) return false;
    navigate('/login', { state: { from: `${location.pathname}${location.search}` } });
    return true;
  };

  return (
    <>
      <div className="section-heading">
        <div>
          <h1>오늘의 트렌드</h1>
          <p>지금 가장 주목받는 키워드를 한눈에 확인해보세요.</p>
        </div>
        <FilterSelect
          value={domain ?? ''}
          options={options}
          ariaLabel="분야"
          onChange={pick}
          disabled={domains.length === 0}
        />
      </div>

      {/* 고른 분야가 없으면 받아 올 판이 없습니다. 무엇이 비었고 어디서 채우는지를 짚어 줍니다. */}
      {noChosenDomain && loggedIn && (
        <p className="trend-boards-empty">
          아직 고른 관심 분야가 없습니다. <Link to="/mypage/profile">관심 분야 고르러 가기</Link>
        </p>
      )}

      {!noChosenDomain && (
        <div className="trend-boards">
          {BOARDS.map((board) => (
            <TrendBoard
              key={board.type}
              board={board}
              domain={domain}
              loggedIn={loggedIn}
              openDetail={openDetail}
              requireLogin={requireLogin}
            />
          ))}
        </div>
      )}
    </>
  );
}

interface TrendBoardProps {
  board: { type: TrendType; tone: string; title: string };
  /** 분야를 아직 모르면 비어 있습니다. 그동안은 부르지 않습니다. */
  domain: string | undefined;
  loggedIn: boolean;
  openDetail: OpenDetail;
  requireLogin: () => boolean;
}

function TrendBoard({ board, domain, loggedIn, openDetail, requireLogin }: TrendBoardProps) {
  const listQuery = useTrends(
    domain ? { domain, type: board.type, period: BOARD_PERIOD, page: 0, size: BOARD_SIZE } : undefined,
  );
  const trends = listQuery.data?.trends ?? [];

  return (
    <article className={`trend-board trend-board--${board.tone}`}>
      <div className="trend-board-body">
        <h2>{board.title}</h2>
        {listQuery.isPending && <p className="trend-board-state">불러오는 중…</p>}
        {listQuery.isError && <p className="trend-board-state" role="alert">불러오지 못했습니다.</p>}
        {listQuery.isSuccess && trends.length === 0 && (
          <p className="trend-board-state">아직 집계된 트렌드가 없습니다.</p>
        )}
        {trends.map((trend, index) => (
          <TrendRow
            key={trend.trendId}
            trend={trend}
            /*
             * 판 안에서의 차례입니다. **`trend.rank` 를 쓰지 않습니다** — 그 값은 분야
             * 전체의 언급량 순위라, 갈래가 다른 기준으로 줄을 세운 판에서는 251·35·52
             * 처럼 뒤섞여 찍힙니다. 급상승 판은 증가율로 줄을 세우니 언급량 순위와
             * 애초에 다른 순서입니다.
             *
             * 줄 세우는 기준은 서버가 갈래마다 다르게 쓰고(인기·신규는 언급량, 급상승은
             * 증가율) 여기서는 그 순서를 그대로 둡니다. 번호만 1부터 답니다.
             */
            rank={index + 1}
            loggedIn={loggedIn}
            openDetail={openDetail}
            requireLogin={requireLogin}
          />
        ))}
      </div>
    </article>
  );
}

interface TrendRowProps {
  trend: Trend;
  rank: number;
  loggedIn: boolean;
  openDetail: OpenDetail;
  requireLogin: () => boolean;
}

function TrendRow({ trend, rank, loggedIn, openDetail, requireLogin }: TrendRowProps) {
  const body = (
    <>
      <span className="trend-rank">{String(rank).padStart(2, '0')}</span>
      <span className="trend-keyword">{trend.keyword}</span>
      {/* 직전 구간 언급량이 없으면 증감률을 낼 수 없어 서버가 비웁니다. 0% 와 갈라 적습니다. */}
      <span className={`trend-growth${trend.growthRate === null ? ' trend-growth--none' : ''}`}>
        {formatGrowth(trend.growthRate)}
      </span>
    </>
  );

  if (!loggedIn) {
    return (
      <button type="button" className="trend-row" onClick={requireLogin} aria-label={`${trend.keyword} 상세 보기, 로그인이 필요합니다`}>
        {body}
      </button>
    );
  }

  return (
    <Link className="trend-row" {...openDetail(trend.trendId)} aria-label={`${trend.keyword} 상세 보기`}>
      {body}
    </Link>
  );
}
