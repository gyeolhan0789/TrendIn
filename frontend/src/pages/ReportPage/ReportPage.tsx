import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { FilterSelect } from '../../components/common/FilterSelect';
import { showToast } from '../../components/common/toast';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import {
  QUICK_REPORTS,
  REPORT_KINDS,
  REPORT_KIND_LABELS,
  REPORT_KIND_TONES,
  SAMPLE_REPORTS,
} from '../../features/report/reportSample';
import type { ReportKind } from '../../features/report/reportSample';
import { TagChip } from '../../features/trend/components/TagChip';
import { TrendSparkline } from '../../features/trend/components/TrendSparkline';
import { useTrendHistory } from '../../features/trend/hooks/useTrendHistory';
import { useTrends } from '../../features/trend/hooks/useTrends';
import { useTrendDetailLink } from '../../features/trend/trendDetailLink';
import { formatCount, formatGrowth } from '../../features/trend/trendFormat';
import { downloadFile, toCsv, today } from '../../utils/download';
import { pageList } from '../../utils/pageList';
import { resolveDomainCode } from '../../constants/filterCodes';
import type { PeriodCode } from '../../constants/filterCodes';
import type { Trend, TrendAnalysisWindow } from '../../features/trend/types/trend';

/*
 * 리포트. 위쪽 한 칸은 고른 분야의 이번 주 집계를 리포트 모양으로 펼쳐 보여 주고,
 * 아래 목록은 만들어 둔 리포트를 모아 둡니다.
 *
 * 주간 요약 칸과 상위 급상승 키워드는 트렌드 목록 API에서 받은 실제 값입니다. 반면 리포트를
 * 만들어 두고 다시 꺼내는 API는 아직 없어서, 아래 목록과 빠른 리포트 갈래는 reportSample.ts 의
 * 표본이고 화면에도 표본이라고 밝혀 둡니다.
 */

/** 주간 리포트라서 기간은 7일로 고정입니다. 기간을 고르는 일은 트렌드 탐색이 맡습니다. */
const REPORT_PERIOD: PeriodCode = '7D';
/* 시안의 목록이 다섯 줄이라 한 쪽을 다섯 줄로 끊습니다. */
const PAGE_SIZE = 5;
/** 한 번에 받아 오는 트렌드 수. 주간 요약은 상위 몇 개가 아니라 분야를 넓게 세어야 합니다. */
const TREND_SAMPLE_SIZE = 24;

const ALL_KINDS = 'ALL';

const sorts = [
  { value: 'recent', label: '최신순' },
  /* 시안의 '인기순' 자리입니다. 리포트를 몇 번 열어 봤는지 세어 주는 곳이 없어 날짜 반대순으로 둡니다. */
  { value: 'oldest', label: '오래된순' },
];

function formatDay(iso: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;
  return `${match[1]}. ${Number(match[2])}. ${Number(match[3])}`;
}

/** 시안 오른쪽 위의 '9. 1 – 9. 7'. 서버가 알려 준 집계 구간을 그대로 씁니다. */
function windowRange(window: TrendAnalysisWindow | null | undefined) {
  if (!window) return null;
  const short = (iso: string) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    return match ? `${Number(match[2])}. ${Number(match[3])}` : iso;
  };
  return `${short(window.recentStart)} – ${short(window.recentEnd)}`;
}

function ArrowIcon({ size = 14, color = 'currentColor', width = 2 }: { size?: number; color?: string; width?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

/** 주간 요약 석 장. 값이 없는 칸은 숫자를 지어내지 않고 그렇다고 밝힙니다. */
function SummaryTile({ label, value, note, tone = 'plain' }: { label: string; value: string; note: string; tone?: 'plain' | 'up' }) {
  return (
    <div className="report-tile">
      <p className="report-tile-label">{label}</p>
      <p className="report-tile-value">{value}</p>
      <p className={`report-tile-note${tone === 'up' ? ' is-up' : ''}`}>{note}</p>
    </div>
  );
}

function WeeklyChart({ trend }: { trend: Trend }) {
  const historyQuery = useTrendHistory(trend.trendId, REPORT_PERIOD);
  const history = historyQuery.data?.history ?? [];

  if (history.length === 0) {
    return (
      <p className="report-chart-empty">
        {historyQuery.isLoading ? '추이를 불러오는 중…' : '표시할 추이가 없습니다.'}
      </p>
    );
  }

  const peak = Math.max(...history.map((point) => point.mentionCount));

  return (
    <>
      <TrendSparkline
        points={history.map((point) => point.mentionCount)}
        width={480}
        height={110}
        color="#4F46E5"
        filled
        gradientId={`report-weekly-${trend.trendId}`}
        className="report-chart-svg"
      />
      <span className="report-chart-badge">‘{trend.keyword}’ 최고 {formatCount(peak)}</span>
    </>
  );
}

export function ReportPage() {
  const domainsQuery = useDomains();
  const [domainChoice, setDomainChoice] = useState<string>();
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState<ReportKind | typeof ALL_KINDS>(ALL_KINDS);
  const [sort, setSort] = useState('recent');
  const [page, setPage] = useState(1);

  const domains = useMemo(() => domainsQuery.data ?? [], [domainsQuery.data]);
  // 분야 목록을 아직 못 받았으면 고를 분야가 없어 트렌드 요청도 멈춰 둡니다.
  const domain = resolveDomainCode(domainChoice, domains);
  const listQuery = useTrends(domain
    ? { domain, type: 'CURRENT', period: REPORT_PERIOD, size: TREND_SAMPLE_SIZE }
    : undefined);

  const trends = useMemo(() => listQuery.data?.trends ?? [], [listQuery.data]);
  const domainName = domains.find((option) => option.domain === domain)?.name;

  /*
   * 주간 요약 수치입니다. 서버가 이 화면을 위한 집계를 따로 주지 않아, 받은 목록을 그대로 셉니다.
   * 직전 구간 언급량이 없는 분야는 증가율을 낼 수 없어 비워 둡니다.
   */
  const summary = useMemo(() => {
    const mentions = trends.reduce((total, trend) => total + trend.mentionCount, 0);
    const previous = trends.reduce((total, trend) => total + trend.previousMentionCount, 0);
    const rated = trends.filter((trend) => trend.growthRate !== null);
    return {
      mentions,
      overall: previous > 0 ? Math.round(((mentions - previous) / previous) * 100) : null,
      average: rated.length > 0
        ? Math.round(rated.reduce((total, trend) => total + (trend.growthRate ?? 0), 0) / rated.length)
        : null,
      rising: trends.filter((trend) => (trend.growthRate ?? 0) > 0).length,
    };
  }, [trends]);

  // 급상승 순서는 목록 순서(언급량 순위)와 달라서 따로 세웁니다.
  const rising = useMemo(
    () => [...trends].sort((a, b) => (b.growthRate ?? -Infinity) - (a.growthRate ?? -Infinity)).slice(0, 5),
    [trends],
  );
  const leader = rising[0];
  const range = windowRange(listQuery.data?.analysisWindow);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const found = SAMPLE_REPORTS.filter((report) => {
      if (kind !== ALL_KINDS && report.kind !== kind) return false;
      if (!needle) return true;
      return `${report.title} ${report.summary}`.toLowerCase().includes(needle);
    });
    // 날짜가 같은 표본이 없어 만든 날만으로 줄을 세웁니다.
    return [...found].sort((a, b) => (sort === 'oldest'
      ? a.createdOn.localeCompare(b.createdOn)
      : b.createdOn.localeCompare(a.createdOn)));
  }, [kind, query, sort]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  // 거르개를 좁히면 쪽수가 줄어, 보던 쪽이 사라질 수 있습니다.
  const currentPage = Math.min(page, totalPages);
  const shown = visible.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const openDetail = useTrendDetailLink();
  const loading = domainsQuery.isLoading || listQuery.isLoading;
  const failed = domainsQuery.isError || listQuery.isError;
  const retry = () => {
    if (domainsQuery.isError) void domainsQuery.refetch();
    if (listQuery.isError) void listQuery.refetch();
  };

  const filterBy = (value: ReportKind | typeof ALL_KINDS) => {
    setKind(value);
    setPage(1);
  };

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setQuery(draft);
    setPage(1);
  };

  /*
   * 리포트를 서버에 만들어 두는 API가 없어, 지금 화면이 들고 있는 이번 주 집계로 그 자리에서
   * 파일을 만들어 내려 줍니다. 계정 설정의 내려받기와 같은 방식입니다.
   */
  const generate = () => {
    downloadFile(
      `trendin-주간리포트-${domainName ?? domain}-${today()}.csv`,
      toCsv(
        ['순위', '키워드', '분야', '언급량', '직전 구간', '증가율'],
        trends.map((trend, index) => [
          String(trend.rank ?? index + 1),
          trend.keyword,
          trend.domain.name,
          String(trend.mentionCount),
          String(trend.previousMentionCount),
          formatGrowth(trend.growthRate),
        ]),
      ),
      'text/csv',
    );
    showToast({ message: '이번 주 집계를 리포트 파일로 내려받았습니다.', type: 'success' });
  };

  return (
    <div className="report-page">
      <section className="report-hero">
        <div>
          <p className="report-eyebrow">트렌드가 만드는 더 나은 인사이트</p>
          <h1>리포트</h1>
          <p className="report-lead">트렌드 데이터를 한눈에 정리한 인사이트 리포트를 생성하고 공유하세요.</p>
        </div>
        <button type="button" className="report-generate" onClick={generate} disabled={trends.length === 0}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
          리포트 생성
        </button>
      </section>

      <section className="report-search">
        <form onSubmit={submitSearch} role="search">
          <SearchIcon />
          <input
            type="text"
            value={draft}
            placeholder="리포트를 검색해보세요"
            aria-label="리포트 검색"
            onChange={(event) => setDraft(event.target.value)}
          />
          {query && (
            <button type="button" className="report-search-clear" onClick={() => { setDraft(''); setQuery(''); setPage(1); }}>
              지우기
            </button>
          )}
          <button type="submit" className="report-search-go" aria-label="검색">
            <ArrowIcon size={16} color="#fff" width={2.5} />
          </button>
        </form>

        <div className="report-kinds" role="group" aria-label="리포트 갈래">
          <button
            type="button"
            className={`report-kind${kind === ALL_KINDS ? ' is-selected' : ''}`}
            aria-pressed={kind === ALL_KINDS}
            onClick={() => filterBy(ALL_KINDS)}
          >
            전체
          </button>
          {REPORT_KINDS.map((code) => (
            <button
              type="button"
              key={code}
              className={`report-kind${kind === code ? ' is-selected' : ''}`}
              aria-pressed={kind === code}
              onClick={() => filterBy(code)}
            >
              {REPORT_KIND_LABELS[code]}
            </button>
          ))}
        </div>
      </section>

      <section className="report-featured">
        {loading && <div className="trendin-state" aria-label="불러오는 중"><span /><span /><span /></div>}
        {!loading && failed && (
          <div className="trendin-state is-error" role="alert">
            <p>이번 주 집계를 불러오지 못했습니다.</p>
            <button type="button" onClick={retry}>다시 시도</button>
          </div>
        )}

        {!loading && !failed && (
          <div className="report-featured-grid">
            <article className="report-weekly">
              <div className="report-weekly-head">
                <div className="report-weekly-badges">
                  <span className="report-badge">주간 리포트</span>
                  {domainName && <TagChip label={domainName} />}
                </div>
                {/* 어느 분야의 한 주인지는 고를 수 있어야 합니다. 트렌드 목록 API가 분야를 반드시 받습니다. */}
                <FilterSelect
                  value={domain ?? ''}
                  options={domains.map((option) => ({ value: option.domain, label: option.name }))}
                  ariaLabel="리포트 분야"
                  onChange={setDomainChoice}
                  disabled={domains.length === 0}
                />
              </div>

              <div className="report-weekly-title">
                <h2>주간 트렌드 리포트</h2>
                <p>최근 7일간 가장 주목받은 트렌드를 종합적으로 정리했습니다.</p>
                {range && <p className="report-weekly-range">{range} 집계 · 직전 구간과 비교</p>}
              </div>

              <div className="report-tiles">
                <SummaryTile
                  label="총 언급량"
                  value={formatCount(summary.mentions)}
                  note={summary.overall === null ? '직전 구간 없음' : `${summary.overall > 0 ? '+' : ''}${summary.overall}%`}
                  tone={summary.overall !== null && summary.overall > 0 ? 'up' : 'plain'}
                />
                <SummaryTile label="평균 증가율" value={formatGrowth(summary.average)} note="직전 구간 대비" />
                {/* 시안의 '관련 콘텐츠' 자리입니다. 콘텐츠 수를 분야 단위로 세어 주는 API가 없어, 같은 목록으로 셀 수 있는 값을 둡니다. */}
                <SummaryTile label="오른 키워드" value={`${summary.rising}개`} note={`집계한 ${trends.length}개 중`} />
              </div>

              <div className="report-chart">
                {/* 가장 크게 오른 키워드 하나만 이력을 따로 불러옵니다. 키워드마다 부르면 한 쪽에 수십 번이 됩니다. */}
                {leader ? <WeeklyChart trend={leader} /> : <p className="report-chart-empty">이번 주 집계가 없습니다.</p>}
              </div>

              {leader && (
                <p className="report-insight">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" />
                  </svg>
                  이번 주 {domainName ?? '이 분야'} 트렌드는 ‘{leader.keyword}’를 중심으로 움직였습니다.
                  직전 구간 대비 {formatGrowth(leader.growthRate)}, 언급량 {formatCount(leader.mentionCount)}입니다.
                </p>
              )}

              <Link className="report-weekly-more" to={`/dashboard?period=${REPORT_PERIOD}${domain ? `&category=${domain}` : ''}`}>
                트렌드 탐색에서 자세히 보기
                <ArrowIcon />
              </Link>
            </article>

            <div className="report-side">
              <div className="report-panel">
                <div className="report-panel-head">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                  </svg>
                  <h3>빠른 리포트</h3>
                  <span className="report-panel-note">준비 중</span>
                </div>
                <div className="report-quick">
                  {/* 누르면 그 갈래로 리포트가 만들어져야 하는데 받아 줄 API가 없어, 자리만 두고 잠가 둡니다. */}
                  {QUICK_REPORTS.map((item) => (
                    <button type="button" key={item.label} disabled title="준비 중입니다">
                      <span className={`report-quick-icon report-quick-icon--${item.tone}`} aria-hidden="true">{item.icon}</span>
                      <span className="report-quick-label">{item.label}</span>
                      <ArrowIcon color="#d1d5db" />
                    </button>
                  ))}
                </div>
              </div>

              <div className="report-panel report-panel--grow">
                <div className="report-panel-head">
                  <h3>상위 급상승 키워드</h3>
                  <span className="report-panel-note">직전 구간 대비</span>
                </div>
                {rising.length === 0 && <p className="report-panel-empty">이번 주 집계가 없습니다.</p>}
                {rising.map((trend, index) => (
                  <div className="report-rank" key={trend.trendId}>
                    <span className={`report-rank-no${index < 3 ? ' is-top' : ''}`}>{index + 1}</span>
                    <Link className="report-rank-keyword" {...openDetail(trend.trendId, `?period=${REPORT_PERIOD}`)}>{trend.keyword}</Link>
                    <span className="report-rank-change">{formatGrowth(trend.growthRate)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="report-list-section">
        <div className="report-list-head">
          <div className="report-list-title">
            <h2>생성된 리포트</h2>
            <span className="report-count">{visible.length}개</span>
          </div>
          <FilterSelect value={sort} options={sorts} ariaLabel="정렬" onChange={setSort} />
        </div>

        {/* 표본을 실제 기록으로 읽고 나서야 알게 되면 곤란해서, 목록 바로 위에서 밝혀 둡니다. */}
        <p className="report-notice">
          리포트를 만들어 두고 다시 꺼내는 API가 아직 없습니다. 아래 목록은 화면 모양을 잡기 위한 <strong>표본</strong>이고,
          위쪽 주간 요약은 실제 트렌드 집계입니다.
        </p>

        <div className="report-list">
          {shown.length === 0 && (
            <p className="report-list-empty">
              {query ? `‘${query}’와 맞는 리포트가 없습니다.` : '이 갈래로 만들어 둔 리포트가 없습니다.'}
            </p>
          )}
          {shown.map((report) => (
            <article className="report-row" key={report.id}>
              <span className={`report-tag report-tag--${REPORT_KIND_TONES[report.kind]}`}>{REPORT_KIND_LABELS[report.kind]}</span>
              <div className="report-row-body">
                <p className="report-row-title">{report.title}</p>
                <p className="report-row-summary">{report.summary}</p>
              </div>
              <span className="report-row-date">{formatDay(report.createdOn)}</span>
              <span className="report-row-period">{report.period}</span>
              {/* 내려받기·공유·더 보기는 모두 리포트가 서버에 있어야 되는 일이라 함께 잠가 둡니다. */}
              <div className="report-row-actions">
                <button type="button" disabled title="준비 중입니다" aria-label="내려받기">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><path d="M7 10l5 5 5-5M12 15V3" />
                  </svg>
                </button>
                <button type="button" disabled title="준비 중입니다" aria-label="공유">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                    <path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8" /><path d="M16 6l-4-4-4 4M12 2v13" />
                  </svg>
                </button>
                <button type="button" disabled title="준비 중입니다" aria-label="더 보기">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" />
                  </svg>
                </button>
              </div>
            </article>
          ))}
        </div>

        {totalPages > 1 && (
          <div className="report-pagination">
            <div className="trendin-pages">
              <button type="button" className="is-step" disabled={currentPage <= 1} aria-label="이전 쪽" onClick={() => setPage(currentPage - 1)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
              </button>
              {pageList(currentPage, totalPages).map((item, index) => (item === 'gap'
                ? <span className="trendin-page-gap" key={`gap-${index}`}>···</span>
                : (
                  <button
                    type="button"
                    key={item}
                    className={item === currentPage ? 'is-current' : ''}
                    aria-current={item === currentPage ? 'page' : undefined}
                    onClick={() => setPage(item)}
                  >
                    {item}
                  </button>
                )))}
              <button type="button" className="is-step" disabled={currentPage >= totalPages} aria-label="다음 쪽" onClick={() => setPage(currentPage + 1)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M9 18l6-6-6-6" /></svg>
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
