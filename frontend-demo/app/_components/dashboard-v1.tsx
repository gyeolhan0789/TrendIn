'use client';

import Link from './page-link';
import AppHeader from './app-header';
import TrendLinks from './trend-links';
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { categories, getCategory, getTrends, getTrend, periodLabels, periods, type CategoryId, type Period, type Trend } from '../trends';
import { usePreferences } from '../preferences';

type Sheet = { type:'detail'; trend:Trend; fromSaved?:boolean } | { type:'saved' } | { type:'settings' } | null;
const format=(n:number)=>new Intl.NumberFormat('en-US').format(n);

export function OrbitMark() { return <span className="orbit-mark" aria-hidden="true"><i/><i/><i/></span>; }
export function RankChange({value}:{value:Trend['change']}) { return <span className={`rank-change ${value==='NEW'?'new':typeof value==='number'&&value<0?'down':''}`} aria-label={value==='NEW'?'순위 신규 진입':value===0?'순위 변동 없음':`${Math.abs(value)}계단 ${value>0?'상승':'하락'}`}>{value==='NEW'?'NEW':value===0?'—':`${value>0?'▲':'▼'} ${Math.abs(value)}`}</span>; }

export function CategorySwitcher({current,interests,onSelect,onEdit}:{current:CategoryId;interests:CategoryId[];onSelect:(id:CategoryId)=>void;onEdit:()=>void}) {
  const dropdown=useRef<HTMLDetailsElement>(null);
  useEffect(()=>{
    const onPointer=(e:PointerEvent)=>{if(!dropdown.current?.contains(e.target as Node))dropdown.current?.removeAttribute('open');};
    const onKey=(e:KeyboardEvent)=>{if(e.key==='Escape'&&dropdown.current?.open){dropdown.current.removeAttribute('open');dropdown.current.querySelector('summary')?.focus();}};
    document.addEventListener('pointerdown',onPointer);document.addEventListener('keydown',onKey);
    return ()=>{document.removeEventListener('pointerdown',onPointer);document.removeEventListener('keydown',onKey);};
  },[]);
  const close=()=>{dropdown.current?.removeAttribute('open');dropdown.current?.querySelector('summary')?.focus();};
  return <div className="category-selector"><span className="category-eyebrow">MY INTEREST</span><span className="current-category" aria-live="polite">{getCategory(current).name}</span><details ref={dropdown} className="category-dropdown"><summary aria-label={`관심 분야 전환, 현재 ${getCategory(current).name}`}><span className="chevron" aria-hidden="true"/></summary><div className="category-popover"><p>어떤 흐름을 살펴볼까요?</p>{interests.map(id=><button key={id} className={current===id?'chosen':''} aria-pressed={current===id} onClick={()=>{onSelect(id);close();}}><span>{getCategory(id).name}</span><span aria-hidden="true">{current===id?'✓':'↗'}</span></button>)}<button className="category-edit" onClick={()=>{close();onEdit();}}>관심 분야 편집 <span>＋</span></button></div></details></div>;
}

function TrendCard({trend,rank,saved,onOpen}:{trend:Trend;rank:number;saved:boolean;onOpen:()=>void}) {
  return <button className={`trend-card card-${rank}`} onClick={onOpen} aria-label={`${rank}위 ${trend.name}, ${trend.change==='NEW'?'순위 신규 진입':trend.change===0?'순위 유지':`${Math.abs(trend.change)}계단 ${trend.change>0?'상승':'하락'}`}, 언급 ${format(trend.mentions)}건, 관심도 ${trend.growth}% 증가. 상세 보기`}>
    <span className="card-topline"><span className="card-rank">0{rank}</span><RankChange value={trend.change}/><span className="card-open" aria-hidden="true">↗</span></span>
    <span className="card-copy"><span className="card-tag">{rank===1&&<span className="spotlight-dot"/>}{trend.tag}{rank===1?' / IN THE SPOTLIGHT':''}{saved&&<span className="saved-dot" aria-label="저장됨"/>}</span><strong className="card-title">{trend.name}</strong><span className="card-description">{trend.sub}</span></span>
    {rank===1&&<span className="card-context">오늘의 대화가 모이는 곳.<br/>지금 가장 주목받는 흐름을 만나보세요.</span>}
    <span className="card-metrics"><span><span className="metric-label">언급량</span><strong>{format(trend.mentions)}<small>건</small></strong></span><span><span className="metric-label">관심도 증가</span><strong className="card-growth">+{trend.growth}<small>%</small></strong></span></span>
  </button>;
}

export function Modal({children,title,onClose,wide=false}:{children:ReactNode;title:string;onClose:()=>void;wide?:boolean}) {
  const panel=useRef<HTMLDivElement>(null);const closeRef=useRef(onClose);
  useEffect(()=>{closeRef.current=onClose;},[onClose]);
  useEffect(()=>{
    const prior=document.activeElement as HTMLElement|null;
    const overflow=document.body.style.overflow;document.body.style.overflow='hidden';
    panel.current?.focus();
    const handle=(e:KeyboardEvent)=>{
      if(e.key==='Escape'){e.preventDefault();closeRef.current();}
      if(e.key==='Tab'){
        const list=panel.current?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),[tabindex="0"]');
        if(!list?.length){e.preventDefault();return;}
        const first=list[0],last=list[list.length-1];
        if(e.shiftKey&&(document.activeElement===first||!panel.current?.contains(document.activeElement)||document.activeElement===panel.current)){e.preventDefault();last.focus();}
        else if(!e.shiftKey&&(document.activeElement===last||!panel.current?.contains(document.activeElement)||document.activeElement===panel.current)){e.preventDefault();first.focus();}
      }
    };
    document.addEventListener('keydown',handle);
    return ()=>{document.body.style.overflow=overflow;document.removeEventListener('keydown',handle);prior?.focus();};
  },[]);
  useEffect(()=>{panel.current?.focus();},[title]);
  return <div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)onClose();}}><div ref={panel} className={`modal-panel ${wide?'settings-panel':''}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}><div className="modal-top"><span className="eyebrow">AHEAD / {title}</span><button className="close-button" onClick={onClose} aria-label="패널 닫기">×</button></div>{children}</div></div>;
}

export function Interests({initial,onApply}:{initial:CategoryId[];onApply:(ids:CategoryId[])=>void}) {
  const [chosen,setChosen]=useState(initial);
  return <><h2 className="modal-title">무엇이 궁금한가요<span className="accent">?</span></h2><p className="modal-lead">관심 분야를 2~3개 골라주세요.<br/>선택한 분야의 흐름만 홈에 담아드릴게요.</p><div className="interest-options">{categories.map(c=><button key={c.id} className={`interest-option ${chosen.includes(c.id)?'chosen':''}`} aria-pressed={chosen.includes(c.id)} disabled={!chosen.includes(c.id)&&chosen.length>=3} onClick={()=>setChosen(chosen.includes(c.id)?chosen.filter(id=>id!==c.id):[...chosen,c.id])}><span>{c.icon}</span><strong>{c.name}</strong><i>{chosen.includes(c.id)?'✓':'＋'}</i></button>)}</div><p className="selection-note">{chosen.length} / 3 선택 <span>{chosen.length<2?'최소 2개를 선택해주세요.':chosen.length===3?'다른 분야를 고르려면 하나를 해제해주세요.':'하나 더 선택하거나, 이대로 시작할 수 있어요.'}</span></p><button className="primary-button" disabled={chosen.length<2} onClick={()=>onApply(chosen)}>내 관심 분야 적용하기 <span>↗</span></button><p className="device-note">관심 분야와 저장한 트렌드는 이 브라우저에 보관됩니다.</p></>;
}

export function Detail({trend,period,saved,onSave,onKeyword,keywords,onBack}:{trend:Trend;period:Period;saved:boolean;onSave:()=>void;onKeyword:(word:string)=>void;keywords:string[];onBack?:()=>void}) {
  const c=getCategory(trend.category);
  const bars=[18,23,19,30,28,36,32,42,45,41,57,63,69,86];
  return <>
    {onBack&&<button className="back-link" onClick={onBack}>← 저장한 트렌드로</button>}
    <div className="detail-label"><span>{c.name} / {trend.tag}</span><span className="example-chip">예시 분석</span></div>
    <div className="detail-title-row"><h2 className="detail-title">{trend.name}</h2><button className={`save-button ${saved?'is-saved':''}`} aria-pressed={saved} onClick={onSave}>{saved?'✓ 저장됨':'＋ 저장'}</button></div>
    <p className="detail-sub">{trend.sub}</p>
    <TrendLinks trend={trend}/>
    <div className="detail-stats"><div><span>언급량 · 최근 {periodLabels[period]}</span><strong>{format(trend.mentions)}<small>건</small></strong></div><div><span>{trend.kind==='new'?'탐지 유형':`이전 ${periodLabels[period]} 대비`}</span><strong className="accent">{trend.kind==='new'?'신규 등장':`+${trend.growth}%`}</strong></div></div>
    <section className="detail-chart-section"><div className="detail-section-heading"><h3>관심의 움직임</h3><span>최근 {periodLabels[period]} · 상대 언급 지수</span></div><div className="detail-chart" role="img" aria-label={`${trend.name} 예시 언급 지수. 시작 18에서 마지막 86으로 전반적으로 상승하는 가상 데이터입니다.`}>{bars.map((v,i)=><div className="detail-bar-track" key={i}><span style={{height:`${v}%`,'--i':i} as CSSProperties}><b>{v}</b></span></div>)}</div><div className="chart-axis"><span>구간 시작</span><span>구간 종료</span></div><p className="chart-disclaimer">차트는 인터페이스 설명을 위한 가상 추이입니다.</p></section>
    <section className="detail-summary"><p className="eyebrow"><span className="small-star">↗</span> CONTEXT, NOT JUST NUMBERS</p><h3>왜 눈여겨볼까요?</h3><p><strong>{trend.name}</strong> — {trend.sub}. 이 예시 화면에서는 {c.name} 분야의 관심이 어떻게 새로운 키워드와 연결되는지 보여줍니다. {c.summary}</p><span>AI 요약 영역 예시 · 실제 원문 분석 전</span></section>
    <section className="detail-related"><h3>함께 살펴볼 키워드</h3><div className="keyword-list">{c.keywords.map(word=><button key={word} className={keywords.includes(`${c.id}:${word}`)?'following':''} onClick={()=>onKeyword(word)} aria-pressed={keywords.includes(`${c.id}:${word}`)}>{word}<span>{keywords.includes(`${c.id}:${word}`)?'✓':'＋'}</span></button>)}</div></section>
    <section className="evidence-section"><div className="detail-section-heading"><h3>트렌드의 근거</h3><span>원문 연결 예정</span></div><div className="evidence-placeholder"><span>≡</span><div><strong>숫자 다음에는, 맥락이 필요하니까.</strong><p>실서비스에서는 수집한 기사와 커뮤니티 원문을<br/>출처·게시일과 함께 이곳에 제공합니다.</p></div></div></section>
    <p className="detail-footer">모든 수치와 분석 문구는 디자인 검토용 예시입니다.<br/>실시간 수집·분석 및 AI 요약은 연결되지 않았습니다.</p>
  </>;
}

function DiscoverCard({kind,trends,expanded,onExpand,onSelect}:{kind:'new'|'rising';trends:Trend[];expanded:boolean;onExpand:()=>void;onSelect:(t:Trend)=>void}) {
  const fresh=kind==='new';
  return <article className={`discovery-card ${fresh?'new-card':'rising-card'}`}><div className="discovery-heading"><div><span className="mini-icon" aria-hidden="true">{fresh?'↗':'↗'}</span><h2>{fresh?'처음 만나는 흐름':'다시, 빠르게 뜨는'}</h2><span className="little-label">{fresh?'NEW':'RISING'}</span></div><button className="text-button" onClick={onExpand} aria-expanded={expanded} aria-controls={`discovery-${kind}`}>{expanded?'접기':'더보기'} <span className="small-arrow">{expanded?'−':'↗'}</span></button></div><p className="section-description">{fresh?'어제는 낯설었지만, 오늘은 눈여겨볼 키워드.':'알고 있던 키워드의, 모르고 있던 새로운 움직임.'}</p><div id={`discovery-${kind}`}>{trends.slice(0,expanded?3:2).map((t,i)=><button className="discovery-item" key={t.id} onClick={()=>onSelect(t)}><span className="discovery-item-text"><span className="item-kicker">0{i+1} · {t.tag}</span><strong>{t.name}</strong><span className="item-description">{t.sub}</span></span><span className="item-side">{fresh?<span className="new-pill">새로운 등장</span>:<strong className="rising-growth">+{t.growth}<span>%</span></strong>}<span aria-hidden="true">↗</span></span></button>)}</div></article>;
}

export default function Home() {
  const [prefs,updatePrefs]=usePreferences();
  const [period,setPeriod]=useState<Period>('day');
  const [sheet,setSheet]=useState<Sheet>(null);
  const [newExpanded,setNewExpanded]=useState(false);
  const [risingExpanded,setRisingExpanded]=useState(false);
  const [toast,setToast]=useState('');
  const toastTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  useEffect(()=>()=>{if(toastTimer.current)clearTimeout(toastTimer.current);},[]);
  const notify=(message:string)=>{setToast(message);if(toastTimer.current)clearTimeout(toastTimer.current);toastTimer.current=setTimeout(()=>setToast(''),2800);};
  const category=getCategory(prefs.active);
  const trends=getTrends(category.id,'top',period);
  const fresh=getTrends(category.id,'new',period);
  const rising=getTrends(category.id,'rising',period);
  const savedTrends=prefs.saved.map(getTrend).filter((t):t is Trend=>!!t);
  const toggleSave=(t:Trend)=>{const has=prefs.saved.includes(t.id);updatePrefs({saved:has?prefs.saved.filter(id=>id!==t.id):[...prefs.saved,t.id]});notify(has?'저장 목록에서 삭제했어요.':'트렌드를 저장했어요. 나중에 다시 만나보세요.');};
  const toggleKeyword=(word:string,categoryId=category.id)=>{const key=`${categoryId}:${word}`;const has=prefs.keywords.includes(key);updatePrefs({keywords:has?prefs.keywords.filter(w=>w!==key):[...prefs.keywords,key]});notify(has?`${word} 관심 키워드를 해제했어요.`:`${word} 키워드를 관심 목록에 담았어요.`);};
  const selectCategory=(id:CategoryId)=>{updatePrefs({active:id});setNewExpanded(false);setRisingExpanded(false);};

  return <>
    <a className="skip-link" href="#main-content">본문으로 바로가기</a>
    <AppHeader active="home" savedCount={savedTrends.length} onSaved={()=>setSheet({type:'saved'})} onSettings={()=>setSheet({type:'settings'})}/>
    <main className="dashboard" id="main-content">
      <section className="intro"><div><p className="eyebrow"><span className="live-dot"/> A LITTLE AHEAD OF EVERYONE</p><h1>당신의 취향, <span>그다음의 발견.</span></h1><p className="intro-copy">지금 뜨는 흐름부터, 아직 낯선 가능성까지.</p></div><div className="edition"><span className="edition-day">30<span>AUG</span></span><div><span>SUNDAY EDITION</span><strong>오늘의 새로운 시선</strong></div></div></section>
      <div className="category-bar"><CategorySwitcher current={category.id} interests={prefs.interests} onSelect={selectCategory} onEdit={()=>setSheet({type:'settings'})}/><span className="category-caption">오직, 지금의 관심사에 집중하세요.</span></div>
      <div className="category-content" key={`${category.id}-${period}`}>
        <section className="top-section" aria-labelledby="top-heading"><div className="section-heading"><div><h2 id="top-heading">지금 눈여겨볼 <span className="top-label">TOP 5<span className="tiny-orbit" aria-hidden="true"/></span></h2><p>가장 많이 이야기되고 있는, {category.name}의 다섯 가지 흐름.</p></div><div className="period-control" aria-label="트렌드 집계 기간">{periods.map(p=><button key={p} className={period===p?'selected':''} aria-pressed={period===p} onClick={()=>setPeriod(p)}>{periodLabels[p]}</button>)}</div></div>
          <ol className="trend-grid">{trends.map((trend,i)=><li key={trend.id} style={{'--i':i} as CSSProperties}><TrendCard trend={trend} rank={i+1} saved={prefs.saved.includes(trend.id)} onOpen={()=>setSheet({type:'detail',trend})}/></li>)}</ol>
          <div className="ranking-foot"><span><i className="live-dot"/> 08.30 09:00 기준</span><span>이전 {periodLabels[period]} 대비 · 예시 데이터</span></div>
        </section>
        <section className="discovery-grid" aria-label="신규 및 급상승 트렌드"><DiscoverCard kind="new" trends={fresh} expanded={newExpanded} onExpand={()=>setNewExpanded(!newExpanded)} onSelect={trend=>setSheet({type:'detail',trend})}/><DiscoverCard kind="rising" trends={rising} expanded={risingExpanded} onExpand={()=>setRisingExpanded(!risingExpanded)} onSelect={trend=>setSheet({type:'detail',trend})}/></section>
        <section className="insight-section" aria-label="트렌드 인사이트와 연관 키워드"><div className="insight-copy"><p className="eyebrow"><span className="small-star" aria-hidden="true">↗</span> CONNECT THE DOTS</p><h2>{category.insight}</h2><p>따로 보이던 키워드가, 하나의 흐름으로 이어지고 있어요.</p><span className="insight-example">인사이트 예시</span></div><div className="insight-keywords"><div className="keyword-heading"><h3>함께 떠오르는 키워드</h3><span>＋ 관심 키워드로 추가</span></div><div className="keyword-list">{category.keywords.map(word=><button key={word} onClick={()=>toggleKeyword(word)} aria-pressed={prefs.keywords.includes(`${category.id}:${word}`)} className={prefs.keywords.includes(`${category.id}:${word}`)?'following':''}>{word}<span>{prefs.keywords.includes(`${category.id}:${word}`)?'✓':'＋'}</span></button>)}</div><p className="keyword-footnote">작은 연결 하나가, 다음 관심사의 시작.</p></div></section>
      </div>
      <footer className="page-footer"><span className="brand">ahead<span className="brand-dot">.</span></span><p>유행을 따라가기 전에, 흐름을 발견하세요.</p><span>모든 트렌드와 수치는 예시입니다. · <Link href="/drafts/v1">디자인 시안 비교 ↗</Link></span></footer>
    </main>
    {sheet&&<Modal title={sheet.type==='detail'?'TREND NOTE':sheet.type==='saved'?'YOUR COLLECTION':'YOUR INTERESTS'} onClose={()=>setSheet(null)} wide={sheet.type==='settings'}>
      {sheet.type==='settings'?<Interests initial={prefs.interests} onApply={ids=>{updatePrefs({interests:ids,active:ids.includes(prefs.active)?prefs.active:ids[0]});setSheet(null);notify('관심 분야를 새롭게 담았어요.');}}/>:sheet.type==='saved'?<><h2 className="modal-title">다시 만나고 싶은<br/>흐름들<span className="accent">.</span></h2><p className="modal-lead">발견한 순간을 저장해두세요. <span className="saved-count">{savedTrends.length}</span></p>{savedTrends.length?<div className="saved-list">{savedTrends.map(t=><div className="saved-item" key={t.id}><button onClick={()=>setSheet({type:'detail',trend:t,fromSaved:true})}><span>{getCategory(t.category).name} · {t.tag}</span><strong>{t.name}</strong><p>{t.sub}</p></button><button className="unsave-button" onClick={()=>toggleSave(t)} aria-label={`${t.name} 저장 해제`}>×</button></div>)}</div>:<div className="empty-state"><OrbitMark/><h3>아직 비어 있는 컬렉션</h3><p>눈길이 가는 트렌드를 누르고 저장해보세요.<br/>나만의 관심 흐름이 차곡차곡 쌓여요.</p><button className="primary-button" onClick={()=>setSheet(null)}>오늘의 흐름 살펴보기 ↗</button></div>}<p className="device-note">이 브라우저에 저장됩니다. 다른 기기와 동기화되지 않습니다.</p></>:<Detail key={sheet.trend.id} trend={sheet.trend} period={sheet.trend.period} saved={prefs.saved.includes(sheet.trend.id)} onSave={()=>toggleSave(sheet.trend)} onKeyword={word=>toggleKeyword(word,sheet.trend.category)} keywords={prefs.keywords} onBack={sheet.fromSaved?()=>setSheet({type:'saved'}):undefined}/>}
    </Modal>}
    <div className={`toast ${toast?'visible':''}`} role="status" aria-live="polite">{toast&&<><span>✓</span>{toast}</>}</div>
  </>;
}
