import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageContainer } from '../../components/layout/PageContainer';
import { NewTrendSection } from '../../features/trend/components/NewTrendSection';
import { RelatedTrendSection } from '../../features/trend/components/RelatedTrendSection';
import { ResurgingTrendSection } from '../../features/trend/components/ResurgingTrendSection';
import { TopTrendSection } from '../../features/trend/components/TopTrendSection';

const categories = ['전체', '패션', '개발'];
const weekdays = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

function formatDate(today: Date) {
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${today.getFullYear()}.${month}.${day}`;
}

function formatCurrentTime(now: Date) {
  return [now.getHours(), now.getMinutes(), now.getSeconds()].map((value) => String(value).padStart(2, '0')).join(':');
}

export function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [now, setNow] = useState(() => new Date());
  const categoryParam = searchParams.get('category') ?? '';
  const category = categories.includes(categoryParam) ? categoryParam : '';
  const period = searchParams.get('period') ?? '24h';
  const params = { category: category || undefined, period };

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  const updateFilter = (key: 'category' | 'period', value: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (!value || (key === 'category' && value === '전체')) nextParams.delete(key);
    else nextParams.set(key, value);
    setSearchParams(nextParams);
  };

  return (
    <PageContainer>
      <section className="intro">
        <div><h1>가장 빠르게 만나는 {category ? `${category} ` : ''}<span>트렌드.</span></h1><p className="intro-copy">지금 뜨는 흐름부터, 아직 낯선 가능성까지.</p></div>
        <div className="edition"><time className="edition-date" dateTime={now.toISOString()}>{formatDate(now)}<span className="edition-weekday">{weekdays[now.getDay()]}</span></time><time className="edition-time" dateTime={now.toISOString()}>{formatCurrentTime(now)}</time></div>
      </section>
      <div className="category-bar">
        <div className="category-selector"><details className="category-dropdown"><summary aria-label={`관심 분야 선택, 현재 ${category || '전체'}`}><span className="current-category">{category || '전체'}</span><span className="chevron" /></summary><div className="category-popover"><p>어떤 흐름을 살펴볼까요?</p>{categories.map((item) => <button type="button" key={item} className={(item === '전체' ? !category : category === item) ? 'chosen' : ''} onClick={(event) => { updateFilter('category', item); event.currentTarget.closest('details')?.removeAttribute('open'); }}>{item}<span>{(item === '전체' ? !category : category === item) ? '✓' : '↗'}</span></button>)}</div></details></div>
      </div>
      <div className="section-stack">
        <TopTrendSection params={params} period={period} onPeriodChange={(value) => updateFilter('period', value)} />
        <div className="discovery-grid">
          <NewTrendSection params={params} />
          <ResurgingTrendSection params={params} />
        </div>
        <RelatedTrendSection params={params} />
      </div>
      <footer className="page-footer"><span className="brand">TrendIn<span className="brand-dot">.</span></span><p>유행을 따라가기 전에, 흐름을 발견하세요.</p></footer>
    </PageContainer>
  );
}
