'use client';

import { useEffect, useState, useSyncExternalStore, type CSSProperties } from 'react';
import Link from './page-link';
import AppHeader from './app-header';
import { CategorySwitcher } from './dashboard-v1';
import { ExploreFooter, useTrendWorkspace, WorkspaceOverlays } from './trend-workspace';
import { getTrends, periods, type Period } from '../trends';
import CountryInterest from './country-interest';
import { interestPeriods } from '../country-interest';
import { searchHref, worldSelection } from '../trend-navigation';
import { countries, dayLabel, getSpreadStory, LAST_DAY, projectPoint, spreadAtDay, spreadCurve, type CountryId } from '../world-data';
import land from '../world-land.json';
import { advanceFlightClock, flightAtTime } from '../flight';

export default function WorldExplorer({ initialTrend = '' }: { initialTrend?: string }) {
  const w = useTrendWorkspace();
  const [selectedId, setSelectedId] = useState(initialTrend);
  const [period, setPeriod] = useState<Period>('month');
  const { category, trend, options: trends } = worldSelection(selectedId, w.prefs.active);
  const displayTrend = getTrends(category.id, trend.kind, period).find(t => t.id === trend.id)!;
  const isSpread = period === 'month';
  const visibleCategories = [...new Set([...w.prefs.interests, category.id])];
  return <div className="explore-page world-page spread-page">
    <a className="skip-link" href="#main-content">본문으로 바로가기</a>
    <AppHeader active="world" savedCount={w.savedTrends.length} onSaved={() => w.setSheet({ type: 'saved' })} onSettings={() => w.setSheet({ type: 'settings' })}/>
    <main className="explore-main" id="main-content">
      <section className="explore-heading"><div><p className="eyebrow">{isSpread ? 'EVERY TREND HAS A JOURNEY' : 'BEYOND YOUR FEED'}</p><h1>{isSpread ? '하나의 시작, 세계로 이어지다' : '같은 흐름, 다른 온도'}<span className="accent">.</span></h1><p>{isSpread ? '처음 관측된 곳부터 새로운 나라의 대화가 되기까지, 30일의 흐름을 따라가세요.' : '관심 있는 키워드가 어디에서 주목받고 있는지, 국가별 관심도와 변화를 살펴보세요.'}</p></div><span className="sample-stamp">{isSpread ? '30 DAYS OF A TREND' : 'WORLD VIEW'}<span>{isSpread ? '2026.08.01 — 08.30' : interestPeriods[period].range} · 예시 데이터</span></span></section>
      <div className="explore-toolbar"><CategorySwitcher current={category.id} interests={visibleCategories} onSelect={id => { if (w.prefs.interests.includes(id)) w.updatePrefs({ active: id }); setSelectedId(getTrends(id, 'top', 'month')[0].id); }} onEdit={() => w.setSheet({ type: 'settings' })}/><div className="world-period-switch"><span className="world-mode-label">{isSpread ? '확산 경로' : '국가별 관심도'}</span><div className="period-control" role="group" aria-label="세계 추이 집계 기간">{periods.map(p => <button key={p} aria-pressed={period === p} className={period === p ? 'selected' : ''} onClick={() => setPeriod(p)}>{p === 'month' ? '30일' : interestPeriods[p].label}</button>)}</div></div></div>
      <div className="world-keywords" aria-label="살펴볼 트렌드 선택">{trends.map((t, i) => <button key={t.id} className={trend.id === t.id ? 'selected' : ''} aria-pressed={trend.id === t.id} onClick={() => setSelectedId(t.id)}><span>{i < 5 ? `0${i + 1}` : '선택'}</span>{t.name}<span aria-hidden="true">↗</span></button>)}</div>
      {isSpread
        ? <SpreadJourney key={trend.id} trend={displayTrend} paused={!!w.sheet} onDetail={() => w.openTrend(displayTrend)}/>
        : <CountryInterest key={trend.id} trend={displayTrend} period={period} onDetail={() => w.openTrend(displayTrend)}/>}
      <ExploreFooter/>
    </main><WorkspaceOverlays workspace={w}/>
  </div>;
}

const subscribeMotion = (listener: () => void) => {
  const query = window.matchMedia('(prefers-reduced-motion: reduce)');
  query.addEventListener('change', listener);
  return () => query.removeEventListener('change', listener);
};
const motionSnapshot = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const subscribeVisibility = (listener: () => void) => {
  document.addEventListener('visibilitychange', listener);
  return () => document.removeEventListener('visibilitychange', listener);
};
const visibilitySnapshot = () => document.visibilityState === 'visible';

function SpreadJourney({ trend, onDetail, paused }: { trend: ReturnType<typeof getTrends>[number]; onDetail: () => void; paused: boolean }) {
  const [story] = useState(() => getSpreadStory(trend));
  const startDay = story.observations[0].firstDay;
  const [position, setPosition] = useState(startDay);
  const day = Math.min(LAST_DAY, Math.floor(position));
  const [countryId, setCountryId] = useState<CountryId | null>(null);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const reducedMotion = useSyncExternalStore(subscribeMotion, motionSnapshot, () => true);
  const visible = useSyncExternalStore(subscribeVisibility, visibilitySnapshot, () => false);
  const activePlaying = playing && !paused && visible && !reducedMotion;
  useEffect(() => {
    if (!activePlaying) return;
    let frame = 0;
    let previous = 0;
    const tick = (now: number) => {
      if (!previous) previous = now;
      const elapsed = now - previous;
      if (elapsed >= 1000 / 30) {
        previous = now;
        setPosition(current => advanceFlightClock(current, Math.min(elapsed, 100), speed, startDay));
      }
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [activePlaying, speed, startDay]);
  const seek = (target: number) => { setPlaying(false); setCountryId(null); setPosition(Math.max(0, Math.min(LAST_DAY, target))); };
  const togglePlayback = () => {
    if (playing) { setPlaying(false); return; }
    setCountryId(null);
    if (day === LAST_DAY) setPosition(startDay);
    setPlaying(true);
  };
  const flight = flightAtTime(story, position);
  const snapshot = spreadAtDay(story, day);
  const origin = story.observations[0];
  const selected = snapshot.reached.find(o => o.country.id === countryId) ?? snapshot.latest;
  const parent = selected?.parent ? story.observations.find(o => o.country.id === selected.parent) : null;
  const nextObservation = story.observations.find(o => o.firstDay > day);
  const elapsed = selected ? day - selected.firstDay : 0;
  const totalMentions = selected?.dailyMentions.slice(0, day + 1).reduce((sum, n) => sum + n, 0) ?? 0;
  const countByDay = Array.from({ length: day + 1 }, (_, d) => spreadAtDay(story, d).reached.length);
  const todayRecord = snapshot.newlyReached.length ? `${snapshot.newlyReached.map(o => o.country.name).join(', ')}에서 처음 관측됐어요.` : snapshot.latest ? '새로운 관측 국가는 없어요. 기존 국가의 이야기가 이어집니다.' : '아직 관측된 국가는 없어요.';
  return <>
    <section className="spread-surface" aria-label={`${trend.name}의 30일 확산 예시`}>
      <div className="spread-map-side"><div className="world-map-heading"><div><span className="explore-kicker">FOLLOW THE FIRST SIGNAL</span><h2>{trend.name}</h2></div><button className="world-detail-link" onClick={onDetail}>트렌드 상세 ↗</button></div>
        <div className="spread-overview"><div><span>기간 내 최초 관측</span><strong>{day >= origin.firstDay ? origin.country.name : '관측 전'}</strong><small>{day >= origin.firstDay ? dayLabel(origin.firstDay) : '아직 관측된 국가가 없어요'}</small></div><span className="spread-summary-arrow" aria-hidden="true">↗</span><div><span>현재까지 관측</span><strong>{snapshot.reached.length}<small>개국</small></strong><small>추적 대상 {countries.length}개국 중</small></div><div className="spread-current-date"><span>지금 보고 있는 날짜</span><strong>{dayLabel(day)}</strong><small>DAY {String(day + 1).padStart(2, '0')} / 30</small></div></div>
        <div className="flight-status" role="status" aria-live={activePlaying ? 'off' : 'polite'}><span className={activePlaying ? 'flight-live' : ''}>{activePlaying ? 'AUTO FLIGHT' : 'PAUSED'}</span><p>{reducedMotion ? '모션 줄이기 설정 · 날짜를 직접 선택해 살펴보세요.' : flight ? `${flight.source.country.name} → ${flight.target.country.name}` : day === LAST_DAY ? '30일의 여정 완료' : snapshot.reached.length === countries.length ? '모든 관측 국가에 도착했어요' : '첫 관측을 기다리는 중'}</p><small>{activePlaying ? '자동으로 이어지는 확산의 흐름' : '선택한 시점에서 멈춰 있어요'}</small></div>
        <div className="world-map spread-map">
          <svg viewBox="0 0 1000 460" aria-hidden="true" className="world-land"><defs><marker id="spread-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#8e9dc9"/></marker></defs><g fill="#edf0f3" stroke="#fff" strokeWidth=".6">{land.map((d, i) => <path key={i} d={d}/>)}</g><g fill="none" stroke="#8e9dc9" strokeWidth="1.8" strokeDasharray="4 5" markerEnd="url(#spread-arrow)">{snapshot.links.map(o => <path className={`spread-route ${selected?.country.id === o.country.id ? 'focused' : ''}`} key={o.country.id} d={spreadCurve(story.observations.find(source => source.country.id === o.parent)!, o)}/>)}</g>{flight && <g fill="none"><path className="flight-upcoming-route" d={flight.path}/><path className="flight-progress-route" d={flight.path} pathLength="1" strokeDasharray={`${flight.progress} 1`}/></g>}</svg>
          {flight && !reducedMotion && <div className="spread-airplane" role="img" aria-label={`${flight.source.country.name}에서 ${flight.target.country.name}로 이동하는 비행기`} style={{ left: `${flight.x / 10}%`, top: `${flight.y / 4.6}%`, '--heading': `${flight.angle}deg` } as CSSProperties}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 12c0 .8-1.1 1.3-2.2 1.3H14l-5.5 7H6l3-7H4.8L3 16H1.5l1.1-4-1.1-4H3l1.8 2.7H9l-3-7h2.5l5.5 7h5.8c1.1 0 2.2 .5 2.2 1.3Z"/></svg></div>}
          {story.observations.map((o, i) => { const p = projectPoint(o.country.lon, o.country.lat); const reached = o.firstDay <= day; return <button key={o.country.id} className={`world-marker marker-${o.country.id} ${reached ? 'reached' : 'unreached'} ${i === 0 && reached ? 'origin' : ''} ${flight?.target.country.id === o.country.id ? 'flight-destination' : ''} ${selected?.country.id === o.country.id ? 'selected' : ''}`} style={{ left: `${p.x / 10}%`, top: `${p.y / 4.6}%`, '--bubble': `${reached ? 21 + Math.min(10, o.dailyMentions[day] / 25) : 12}px` } as CSSProperties} disabled={!reached} aria-label={`${o.country.name}, ${reached ? `${dayLabel(o.firstDay)} 최초 관측, 기록 보기` : '아직 관측 전'}`} aria-pressed={selected?.country.id === o.country.id} onClick={() => { setCountryId(o.country.id); setPlaying(false); }}><i aria-hidden="true"/><span>{o.country.name}{i === 0 && reached && <b>최초</b>}</span></button>; })}
        </div>
        <div className="spread-legend"><span><i className="origin"/>최초 관측</span><span><i/>관측 국가</span><span><i className="pending"/>관측 전</span><span><i className="route"/>확산 추정 경로</span><span className="flight-legend">비행기 · 흐름을 표현한 시각화</span></div>
        <div className="spread-timeline">
          <div className="spread-time-heading"><label htmlFor="spread-day">30일의 흐름을 따라가세요</label><div className="spread-playback"><button className="spread-step-button" aria-label="하루 전" disabled={day === 0} onClick={() => seek(day - 1)}>‹</button><button className="spread-play" aria-pressed={activePlaying} disabled={reducedMotion} onClick={togglePlayback}><span aria-hidden="true">{activePlaying ? 'Ⅱ' : '▷'}</span>{activePlaying ? '일시정지' : '이어 재생'}</button><button className="spread-step-button" aria-label="하루 뒤" disabled={day === LAST_DAY} onClick={() => seek(day + 1)}>›</button><button className="spread-speed" aria-label={`재생 속도 ${speed}배, 눌러서 변경`} onClick={() => setSpeed(speed === 1 ? 2 : 1)}>{speed}×</button></div></div>
          <input id="spread-day" type="range" min="0" max={LAST_DAY} value={day} onChange={e => seek(Number(e.target.value))} aria-valuetext={`8월 ${day + 1}일, ${snapshot.reached.length}개국 관측`} style={{ '--progress': `${day / LAST_DAY * 100}%` } as CSSProperties}/><div className="spread-ticks">{[0, 9, 19, 29].map(d => <button key={d} onClick={() => seek(d)}>{dayLabel(d)}</button>)}</div>
          <div className="spread-today"><p role="status" aria-live={activePlaying ? 'off' : 'polite'}><time>{dayLabel(day)}</time>{todayRecord}</p><button disabled={!nextObservation} onClick={() => { if (nextObservation) seek(nextObservation.firstDay); }}>다음 관측 <span>↗</span></button></div>
        </div>
      </div>
      <aside className="spread-log"><p className="explore-kicker">THE JOURNEY SO FAR</p><h2>어디로 이어졌을까요?</h2><p className="spread-log-intro">{dayLabel(day)}까지의 최초 관측 순서</p><ol>{snapshot.reached.map((o, i) => <li key={o.country.id}><button className={selected?.country.id === o.country.id ? 'selected' : ''} aria-pressed={selected?.country.id === o.country.id} onClick={() => { setCountryId(o.country.id); setPlaying(false); }}><span className="spread-step">{String(i + 1).padStart(2, '0')}</span><span><strong>{o.country.name}</strong><small>{i === 0 ? '기간 내 최초 관측' : '새로운 국가에서 관측'}</small></span><time>{dayLabel(o.firstDay)}</time></button></li>)}</ol>{!snapshot.reached.length && <p className="spread-no-events">아직 관측 기록이 없어요.<br/>날짜를 앞으로 옮겨보세요.</p>}<p className="spread-log-note">관측 순서는 수집된 기록의 시간 순서입니다. 실제 유행의 발생지나 전파 경로를 확정하지 않습니다.</p></aside>
    </section>
    <p className="spread-disclaimer">시연용 가상 데이터 · 비행기는 확산을 표현한 아이콘이며 실제 항공 이동을 뜻하지 않습니다. 점선은 설명을 위해 설정한 확산 가설입니다. 실제 서비스에서는 원문과 인용 관계 등 별도 근거가 필요합니다. <a href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noreferrer">지도: Natural Earth ↗</a></p>
    <section className="spread-details" aria-label="관측 국가의 기록과 누적 확산">
      <div className="spread-country-detail"><p className="explore-kicker">BEHIND THE ARRIVAL</p><div className="spread-detail-title"><h2>{selected ? `${selected.country.name}에 닿기까지` : '첫 관측을 기다리는 중'}</h2><span>관측 기록 예시</span></div>
        {selected ? <><div className="spread-arrival"><span>{parent ? `${parent.country.name} 이후` : '기간 내 첫 관측'}<small>{parent ? `${dayLabel(parent.firstDay)} 관측` : '이전 경로 미확인'}</small></span><span aria-hidden="true">→</span><span><strong>{selected.country.name}</strong><small>{dayLabel(selected.firstDay)} 최초 관측</small></span><span className="spread-arrival-gap">{parent ? `${selected.firstDay - parent.firstDay}일 간격` : 'START'}</span></div>
          <p className="spread-context">{selected.context}을 보여주는 가상 시나리오입니다.</p>
          <dl className="spread-country-metrics"><div><dt>관측 경과</dt><dd>{elapsed}<small>일</small></dd></div><div><dt>{dayLabel(day)} 언급량</dt><dd>{selected.dailyMentions[day].toLocaleString('ko-KR')}<small>건</small></dd></div><div><dt>관측 후 누적 언급</dt><dd>{totalMentions.toLocaleString('ko-KR')}<small>건</small></dd></div></dl>
          <div className="spread-evidence"><span>경로 근거</span><p>{parent ? '원문 연결 전 · 앞선 국가의 관측과 시간 차이만으로 직접 전파를 확인할 수 없습니다.' : '원문 연결 전 · 추적한 국가와 기간 안에서 가장 먼저 관측된 예시이며, 실제 발생지를 뜻하지 않습니다.'}</p><b>검증 전</b></div></>
          : <p className="spread-no-events">이 날짜에는 아직 기록이 없습니다. 타임라인을 앞으로 이동하거나 재생을 눌러보세요.</p>}
        <Link className="spread-search-link" href={searchHref(trend)}>이 키워드로 더 찾아보기 <span>↗</span></Link>
      </div>
      <div className="spread-footprint"><div className="spread-detail-title"><div><p className="explore-kicker">A GROWING FOOTPRINT</p><h2>관측 범위가 넓어지는 속도</h2></div><strong>{snapshot.reached.length}<small>/ {countries.length}개국</small></strong></div><p>선택한 날짜까지, 누적으로 관측된 국가 수</p>
        <svg viewBox="0 0 640 175" role="img" aria-label={`${dayLabel(day)}까지의 누적 관측 국가 수 ${snapshot.reached.length}개국. 국가별 최초 관측일은 관측 기록에서 확인할 수 있습니다.`}>{[0, 2, 4, 6].map(n => <g key={n}><line x1="35" x2="605" y1={140 - n * 18} y2={140 - n * 18} stroke="#edf0f3"/><text x="21" y={144 - n * 18} textAnchor="end">{n}</text></g>)}<polyline points={countByDay.map((n, i) => `${i ? `${35 + i / LAST_DAY * 570},${140 - countByDay[i - 1] * 18} ` : ''}${35 + i / LAST_DAY * 570},${140 - n * 18}`).join(' ')} fill="none" stroke="var(--accent)" strokeWidth="2"/><circle cx={35 + day / LAST_DAY * 570} cy={140 - snapshot.reached.length * 18} r="4" fill="var(--accent)"/>{[0, 9, 19, 29].map(d => <text key={d} x={35 + d / LAST_DAY * 570} y="168" textAnchor="middle">{dayLabel(d)}</text>)}</svg>
        <details className="chart-data"><summary>날짜별 수치 보기 <span>＋</span></summary><div className="spread-data-scroll"><table><caption>{trend.name} · 선택 날짜까지의 예시 기록</caption><thead><tr><th scope="col">날짜</th><th scope="col">관측 국가 수</th><th scope="col">새로 관측된 국가</th></tr></thead><tbody>{countByDay.map((count, d) => <tr key={d}><th scope="row">{dayLabel(d)}</th><td>{count}</td><td>{story.observations.filter(o => o.firstDay === d).map(o => o.country.name).join(', ') || '—'}</td></tr>)}</tbody></table></div></details>
        <div className="spread-method"><strong>‘최초’와 ‘확산’은 어떻게 읽나요?</strong><p>최초 관측은 분석 기간과 수집 범위 안의 첫 기록입니다. 국가는 언어만으로 판단하지 않으며, 관측 시점에 더해 원문 인용·재게시 관계 등 근거를 확인해야 전파 방향을 추정할 수 있습니다.</p></div>
      </div>
    </section>
  </>;
}
