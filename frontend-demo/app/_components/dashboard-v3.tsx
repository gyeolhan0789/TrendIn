'use client';

import Link from './page-link';
import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react';
import { getCategory, getTrends, getTrend, periodLabels, periods, type CategoryId, type Period, type Trend } from '../trends';
import { usePreferences } from '../preferences';
import { OrbitMark, RankChange, CategorySwitcher, Modal, Interests, Detail } from './dashboard-v1';

type Sheet = { type:'detail'; trend:Trend; fromSaved?:boolean } | { type:'saved' } | { type:'settings' } | null;
const format=(n:number)=>new Intl.NumberFormat('en-US').format(n);

function StageDrawer({id,index,title,preview,expanded,onToggle,children}:{id:string;index:string;title:string;preview:string;expanded:boolean;onToggle:()=>void;children:ReactNode}) {
  return <section className={`st-drawer ${expanded?'open':''}`}><h3><button className="st-drawer-toggle" id={`st-toggle-${id}`} aria-expanded={expanded} aria-controls={`st-content-${id}`} onClick={onToggle}><span className="st-drawer-index">{index}</span><span className="st-drawer-title">{title}</span><span className="st-drawer-preview">{preview}</span><span className="st-drawer-mark" aria-hidden="true">{expanded?'−':'＋'}</span></button></h3><div className="st-drawer-content" id={`st-content-${id}`} role="region" aria-labelledby={`st-toggle-${id}`} hidden={!expanded}>{children}</div></section>;
}

function StageSignals({kind,trends,expanded,onMore,onOpen}:{kind:'new'|'rising';trends:Trend[];expanded:boolean;onMore:()=>void;onOpen:(trend:Trend)=>void}) {
  return <><div className="st-signal-rows" id={`st-signals-${kind}`}>{trends.slice(0,expanded?3:2).map((t,i)=><button key={t.id} className="st-signal-row" onClick={()=>onOpen(t)} aria-label={`${t.name} 상세 보기`}><span className="st-signal-number">0{i+1}</span><span className="st-signal-name"><strong>{t.name}</strong><span>{t.tag}</span></span><span className="st-signal-description">{t.sub}</span><span className="st-signal-data">{kind==='new'?<span className="st-new-marker">신규 등장</span>:<strong>+{t.growth}<small>%</small></strong>}<span aria-hidden="true">↗</span></span></button>)}</div><div className="st-signals-footer"><span>{kind==='new'?'처음 들리는 이름에서, 다음 가능성을 발견하세요.':'알고 있던 키워드가 다시 대화의 중심으로.'}</span><button onClick={onMore} aria-expanded={expanded} aria-controls={`st-signals-${kind}`}>{expanded?'간략히 보기':`전체 ${trends.length}개 보기`} <span aria-hidden="true">{expanded?'−':'＋'}</span></button></div></>;
}

export default function StageDashboard() {
  const [prefs,updatePrefs]=usePreferences();
  const [period,setPeriod]=useState<Period>('day');
  const [rank,setRank]=useState(0);
  const [drawer,setDrawer]=useState<'new'|'rising'|'insight'|null>('new');
  const [sheet,setSheet]=useState<Sheet>(null);
  const [newExpanded,setNewExpanded]=useState(false);
  const [risingExpanded,setRisingExpanded]=useState(false);
  const [toast,setToast]=useState('');
  const toastTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  useEffect(()=>()=>{if(toastTimer.current)clearTimeout(toastTimer.current);},[]);
  const notify=(message:string)=>{setToast(message);if(toastTimer.current)clearTimeout(toastTimer.current);toastTimer.current=setTimeout(()=>setToast(''),2800);};
  const category=getCategory(prefs.active);
  const trends=getTrends(category.id,'top',period);
  const selected=trends[rank];
  const selectRank=(next:number)=>setRank((next+trends.length)%trends.length);
  const onRankKeyDown=(event:ReactKeyboardEvent<HTMLButtonElement>,index:number)=>{
    let next=index;
    if(event.key==='ArrowRight')next=(index+1)%trends.length;
    else if(event.key==='ArrowLeft')next=(index-1+trends.length)%trends.length;
    else if(event.key==='Home')next=0;
    else if(event.key==='End')next=trends.length-1;
    else return;
    event.preventDefault();selectRank(next);document.getElementById(`stage-tab-${next}`)?.focus();
  };
  const fresh=getTrends(category.id,'new',period);
  const rising=getTrends(category.id,'rising',period);
  const savedTrends=prefs.saved.map(getTrend).filter((t):t is Trend=>!!t);
  const toggleSave=(t:Trend)=>{const has=prefs.saved.includes(t.id);updatePrefs({saved:has?prefs.saved.filter(id=>id!==t.id):[...prefs.saved,t.id]});notify(has?'저장 목록에서 삭제했어요.':'트렌드를 저장했어요. 나중에 다시 만나보세요.');};
  const toggleKeyword=(word:string,categoryId=category.id)=>{const key=`${categoryId}:${word}`;const has=prefs.keywords.includes(key);updatePrefs({keywords:has?prefs.keywords.filter(w=>w!==key):[...prefs.keywords,key]});notify(has?`${word} 관심 키워드를 해제했어요.`:`${word} 키워드를 관심 목록에 담았어요.`);};
  const selectCategory=(id:CategoryId)=>{updatePrefs({active:id});setRank(0);setNewExpanded(false);setRisingExpanded(false);};

  return <>
    <a className="skip-link" href="#main-content">본문으로 바로가기</a>
    <header className="site-header"><div className="header-inner"><Link className="brand" href="/drafts/v3" aria-label="ahead 홈">ahead<span className="brand-dot">.</span></Link><nav className="main-nav" aria-label="주 메뉴"><button className={`nav-item ${sheet?.type==='saved'?'':'active'}`} onClick={()=>{setSheet(null);window.scrollTo({top:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}}>나의 트렌드</button><button className={`nav-item ${sheet?.type==='saved'?'active':''}`} onClick={()=>setSheet({type:'saved'})}>저장한 트렌드 <span>{savedTrends.length}</span></button></nav><div className="header-right"><span className="demo-label">DEMO EDITION</span><button className="avatar" aria-label="내 관심 분야 설정" onClick={()=>setSheet({type:'settings'})}>J</button></div></div></header>
    <main className="dashboard stage-page" id="main-content">
      <section className="st-intro"><div><p className="eyebrow">AHEAD / TREND STAGE</p><h1>시선이 머무는 흐름.</h1></div><div className="st-intro-controls"><CategorySwitcher current={category.id} interests={prefs.interests} onSelect={selectCategory} onEdit={()=>setSheet({type:'settings'})}/><div className="period-control" aria-label="트렌드 집계 기간">{periods.map(p=><button key={p} className={period===p?'selected':''} aria-pressed={period===p} onClick={()=>{setPeriod(p);setRank(0);}}>{periodLabels[p]}</button>)}</div></div></section>
      <section className="st-showcase" aria-label={`${category.name} 현재 트렌드 Top 5`}>
        <div className="st-stage-meta"><span>THE TOP FIVE <span>지금 주목할 다섯 가지</span></span><span>08.30 09:00 · 예시 데이터</span></div>
        <div className="st-stage">
          <button className="st-side-arrow st-previous" onClick={()=>selectRank(rank-1)} aria-label="이전 순위 트렌드 선택">←</button>
          <div className="st-scene" key={`${category.id}-${period}-${selected.id}`} role="tabpanel" id="stage-panel" aria-labelledby={`stage-tab-${rank}`} tabIndex={0}>
            <div className="st-scene-kicker"><span className="st-position">0{rank+1}</span><span className="st-position-divider"/><span>{selected.tag}</span><RankChange value={selected.change}/></div>
            <h2>{selected.name}</h2>
            <p className="st-scene-description">{selected.sub}</p>
            <div className="st-scene-metrics"><span><strong>{format(selected.mentions)}</strong> <span>언급</span></span><span className="st-metric-divider"/><span><strong className="st-growth">+{selected.growth}%</strong> <span>관심도</span></span></div>
            <div className="st-scene-actions"><button className="st-open-detail" onClick={()=>setSheet({type:'detail',trend:selected})}>흐름 자세히 보기 <span aria-hidden="true">↗</span></button><button className={`st-save ${prefs.saved.includes(selected.id)?'saved':''}`} aria-pressed={prefs.saved.includes(selected.id)} onClick={()=>toggleSave(selected)}>{prefs.saved.includes(selected.id)?'✓ 저장됨':'＋ 저장'}</button></div>
          </div>
          <button className="st-side-arrow st-next" onClick={()=>selectRank(rank+1)} aria-label="다음 순위 트렌드 선택">→</button>
        </div>
        <div className="st-rank-track" role="tablist" aria-label="Top 5 트렌드 선택" aria-orientation="horizontal"><span className="st-track-indicator" aria-hidden="true" style={{transform:`translateX(${rank*100}%)`}}/>{trends.map((t,i)=><button key={t.id} role="tab" id={`stage-tab-${i}`} aria-controls="stage-panel" aria-selected={rank===i} tabIndex={rank===i?0:-1} className={`st-rank-stop ${rank===i?'selected':''}`} onClick={()=>selectRank(i)} onKeyDown={event=>onRankKeyDown(event,i)}><span className="st-stop-top"><span>0{i+1}</span><RankChange value={t.change}/></span><strong>{t.name}</strong><span className="st-stop-note">{format(t.mentions)}건 <span>+{t.growth}%</span></span></button>)}</div>
        <div className="st-track-caption"><span>다섯 가지 흐름, 하나씩 깊이 들여다보세요.</span><span>← → 방향키로도 탐색할 수 있어요.</span></div>
      </section>
      <section className="st-notes" aria-labelledby="st-notes-heading">
        <div className="st-notes-heading"><h2 id="st-notes-heading">시선 밖의 새로운 가능성.</h2><span>조금 더 깊이 들여다보세요.</span></div>
        <StageDrawer id="new" index="01" title="새롭게 등장한 흐름" preview={fresh.slice(0,2).map(t=>t.name).join(' · ')} expanded={drawer==='new'} onToggle={()=>setDrawer(drawer==='new'?null:'new')}><StageSignals kind="new" trends={fresh} expanded={newExpanded} onMore={()=>setNewExpanded(!newExpanded)} onOpen={trend=>setSheet({type:'detail',trend})}/></StageDrawer>
        <StageDrawer id="rising" index="02" title="다시 빠르게 떠오르는" preview={rising.slice(0,2).map(t=>`${t.name} +${t.growth}%`).join(' · ')} expanded={drawer==='rising'} onToggle={()=>setDrawer(drawer==='rising'?null:'rising')}><StageSignals kind="rising" trends={rising} expanded={risingExpanded} onMore={()=>setRisingExpanded(!risingExpanded)} onOpen={trend=>setSheet({type:'detail',trend})}/></StageDrawer>
        <StageDrawer id="insight" index="03" title="이 흐름이 말하는 것" preview={category.insight} expanded={drawer==='insight'} onToggle={()=>setDrawer(drawer==='insight'?null:'insight')}><div className="st-insight"><p className="st-insight-kicker">TREND INSIGHT · 예시 분석</p><h4>{category.insight}</h4><p>{category.summary}</p><div className="st-related"><span>함께 떠오르는 키워드</span><div>{category.keywords.map(word=>{const following=prefs.keywords.includes(`${category.id}:${word}`);return <button key={word} aria-pressed={following} className={following?'following':''} onClick={()=>toggleKeyword(word)}>{word}<span>{following?'✓':'＋'}</span></button>;})}</div><span>＋ 관심 키워드로 추가</span></div></div></StageDrawer>
      </section>
      <footer className="page-footer"><span className="brand">ahead<span className="brand-dot">.</span></span><p>유행을 따라가기 전에, 흐름을 발견하세요.</p><span>디자인 프리뷰 · 모든 트렌드와 수치는 예시입니다.</span></footer>
    </main>
    {sheet&&<Modal title={sheet.type==='detail'?'TREND NOTE':sheet.type==='saved'?'YOUR COLLECTION':'YOUR INTERESTS'} onClose={()=>setSheet(null)} wide={sheet.type==='settings'}>
      {sheet.type==='settings'?<Interests initial={prefs.interests} onApply={ids=>{updatePrefs({interests:ids,active:ids.includes(prefs.active)?prefs.active:ids[0]});setRank(0);setSheet(null);notify('관심 분야를 새롭게 담았어요.');}}/>:sheet.type==='saved'?<><h2 className="modal-title">다시 만나고 싶은<br/>흐름들<span className="accent">.</span></h2><p className="modal-lead">발견한 순간을 저장해두세요. <span className="saved-count">{savedTrends.length}</span></p>{savedTrends.length?<div className="saved-list">{savedTrends.map(t=><div className="saved-item" key={t.id}><button onClick={()=>setSheet({type:'detail',trend:t,fromSaved:true})}><span>{getCategory(t.category).name} · {t.tag}</span><strong>{t.name}</strong><p>{t.sub}</p></button><button className="unsave-button" onClick={()=>toggleSave(t)} aria-label={`${t.name} 저장 해제`}>×</button></div>)}</div>:<div className="empty-state"><OrbitMark/><h3>아직 비어 있는 컬렉션</h3><p>눈길이 가는 트렌드를 누르고 저장해보세요.<br/>나만의 관심 흐름이 차곡차곡 쌓여요.</p><button className="primary-button" onClick={()=>setSheet(null)}>오늘의 흐름 살펴보기 ↗</button></div>}<p className="device-note">이 브라우저에 저장됩니다. 다른 기기와 동기화되지 않습니다.</p></>:<Detail key={sheet.trend.id} trend={sheet.trend} period={sheet.trend.period} saved={prefs.saved.includes(sheet.trend.id)} onSave={()=>toggleSave(sheet.trend)} onKeyword={word=>toggleKeyword(word,sheet.trend.category)} keywords={prefs.keywords} onBack={sheet.fromSaved?()=>setSheet({type:'saved'}):undefined}/>}
    </Modal>}
    <div className={`toast ${toast?'visible':''}`} role="status" aria-live="polite">{toast&&<><span>✓</span>{toast}</>}</div>
  </>;
}
