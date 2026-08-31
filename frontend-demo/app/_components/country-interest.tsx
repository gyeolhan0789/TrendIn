'use client';

import { useState, type CSSProperties } from 'react';
import Link from './page-link';
import type { Trend } from '../trends';
import { searchHref } from '../trend-navigation';
import { projectPoint, type CountryId } from '../world-data';
import { interestPeriods, worldStats, type InterestPeriod } from '../country-interest';
import land from '../world-land.json';

// The original country-comparison view, kept separate from 30-day spread playback.
export default function CountryInterest({ trend, period, onDetail }: { trend: Trend; period: InterestPeriod; onDetail: () => void }) {
  const [countryId, setCountryId] = useState<CountryId>('KR');
  const stats = worldStats(trend, period);
  const selected = stats.find(c => c.id === countryId)!;
  const average = selected.series.map((_, i) => Math.round(stats.reduce((sum, c) => sum + c.series[i], 0) / stats.length));
  const fastest = [...stats].sort((a, b) => b.change - a.change)[0];
  const points = (values: number[]) => values.map((v, i) => `${45 + i * 105},${180 - v * 1.5}`).join(' ');
  const labels = interestPeriods[period].axis;
  return <>
      <section className="world-surface" aria-label={`${trend.name}의 국가별 관심도`}>
        <div className="world-map-panel">
          <div className="world-map-heading"><div><span className="explore-kicker">{`GLOBAL INTEREST · ${interestPeriods[period].label}` }</span><h2>{trend.name}</h2></div><button className="world-detail-link" onClick={onDetail}>트렌드 상세 ↗</button></div>
          <div className="world-map">
            <svg viewBox="0 0 1000 460" aria-hidden="true" className="world-land"><g fill="#edf0f3" stroke="#fff" strokeWidth=".6">{land.map((d, i) => <path key={i} d={d}/>)}</g></svg>
            {stats.map(c => { const p = projectPoint(c.lon, c.lat); return <button key={c.id} className={`world-marker marker-${c.id} ${c.id === countryId ? 'selected' : ''}`} style={{ left: `${p.x / 10}%`, top: `${p.y / 4.6}%`, '--bubble': `${12 + c.score / 7}px` } as CSSProperties} aria-label={`${c.name}, 관심 지수 ${c.score}. 국가 선택`} aria-pressed={countryId === c.id} onClick={() => setCountryId(c.id)}><i aria-hidden="true"/><span>{c.name}</span></button>; })}
          </div>
          <div className="map-caption"><span><i/> 원의 크기 = 관심 지수 · 국가를 눌러 비교하세요</span><a href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noreferrer">지도: Natural Earth ↗</a></div>
        </div>
        <aside className="country-ranking" aria-label="국가별 관심 지수 비교"><div className="country-ranking-head"><h3>어디서 주목할까요?</h3><p>{interestPeriods[period].range} · 관심 지수 기준</p></div><div className="country-table-label"><span>국가</span><span>관심 지수 / 구간 변화</span></div>
          {stats.map((c, i) => <button key={c.id} className={`country-row ${c.id === countryId ? 'selected' : ''}`} aria-pressed={c.id === countryId} onClick={() => setCountryId(c.id)}><span className="country-rank">{String(i + 1).padStart(2, '0')}</span><span className="country-row-name"><strong>{c.name}</strong><small>{c.en}</small></span><span className="country-row-stat"><strong>{c.score}</strong><small>+{c.change}p</small></span><span className="country-row-bar" style={{ width: `${c.score}%` }}/></button>)}
          <p className="country-note">관심 지수 0–100 · 수집량과 무관한 가상 비교 지표입니다. 미표시 국가는 데이터가 없습니다.</p>
        </aside>
      </section>
      <section className="world-analysis" aria-label="선택 국가의 변화 추이">
        <div className="world-chart-panel"><div className="world-chart-title"><div><p className="explore-kicker">A CLOSER LOOK</p><h2>{selected.name}의 관심 변화</h2></div><div className="world-chart-value" aria-live="polite"><strong>{selected.score}<small>/100</small></strong><span>구간 시작 대비 +{selected.change}p</span></div></div>
          <div className="chart-legend"><span><i className="selected-line"/>{selected.name}</span><span><i/>6개국 평균</span></div>
          <svg className="world-line-chart" viewBox="0 0 720 215" role="img" aria-label={`${selected.name}의 ${trend.name} 예시 관심 지수: ${selected.series.join(', ')}. 6개국 평균: ${average.join(', ')}.`}>
            {[0, 25, 50, 75, 100].map(v => <g key={v}><line x1="45" x2="675" y1={180 - v * 1.5} y2={180 - v * 1.5} stroke="#edf0f3"/><text x="27" y={184 - v * 1.5} textAnchor="end">{v}</text></g>)}
            <polyline points={points(average)} fill="none" stroke="#b9c1ce" strokeWidth="2" strokeDasharray="4 5"/>
            <polyline points={points(selected.series)} fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinejoin="round"/>
            {selected.series.map((v, i) => <g key={i}><circle cx={45 + i * 105} cy={180 - v * 1.5} r="4" fill="white" stroke="var(--accent)" strokeWidth="2"><title>{labels[i]}: {v}</title></circle><text x={45 + i * 105} y="208" textAnchor="middle">{labels[i]}</text></g>)}
          </svg>
          <details className="chart-data"><summary>수치로 보기 <span>＋</span></summary><div className="chart-table-scroll"><table><caption>{trend.name} · {interestPeriods[period].label} 예시 관심 지수</caption><thead><tr><th scope="col">구간</th>{labels.map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody><tr><th scope="row">{selected.name}</th>{selected.series.map((n, i) => <td key={i}>{n}</td>)}</tr><tr><th scope="row">6개국 평균</th>{average.map((n, i) => <td key={i}>{n}</td>)}</tr></tbody></table></div></details>
        </div>
        <div className="world-reading"><p className="explore-kicker">READ THE SIGNALS</p><h2>숫자 사이의 흐름 읽기</h2><div><span>01 / 가장 높은 관심</span><p><strong>{stats[0].name}</strong>에서 <strong>{trend.name}</strong>의 관심 지수가 가장 높게 나타나는 예시예요.</p></div><div><span>02 / 가장 큰 변화</span><p><strong>{fastest.name}</strong>은 구간 시작보다 <strong>{fastest.change}포인트</strong> 상승했어요. 높은 관심과 빠른 변화는 다를 수 있어요.</p></div><p className="world-reading-note">가상 데이터로 구성한 해석 예시입니다. 국가 간 전파 방향이나 실제 상승 원인을 의미하지 않습니다.</p><Link href={searchHref(trend)}>이 키워드로 더 찾아보기 <span>↗</span></Link></div>
      </section>
  </>;
}
