'use client';

import Link from './page-link';
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { getCategory, getTrends, getTrend, periodLabels, periods, type CategoryId, type Period, type Trend } from '../trends';
import { usePreferences } from '../preferences';
import { OrbitMark, RankChange, CategorySwitcher, Modal, Interests, Detail } from './dashboard-v1';

type Sheet = { type:'detail'; trend:Trend; fromSaved?:boolean } | { type:'saved' } | { type:'settings' } | null;
const format=(n:number)=>new Intl.NumberFormat('en-US').format(n);

function DiscoveryBand({kind,trends,expanded,onToggle,onOpen}:{kind:'new'|'rising';trends:Trend[];expanded:boolean;onToggle:()=>void;onOpen:(trend:Trend)=>void}) {
  return <div className={`ed-discovery-band ed-${kind}`}>
    <div className="ed-band-heading"><span className="ed-band-word">{kind==='new'?'Newcomers.':'On the rise.'}</span><h3>{kind==='new'?'처음 만나는 흐름':'다시, 빠르게 뜨는'}</h3><button className="ed-more" onClick={onToggle} aria-expanded={expanded} aria-controls={`ed-${kind}-items`}>{expanded?'접기':'하나 더 보기'} <span aria-hidden="true">{expanded?'−':'＋'}</span></button></div>
    <div className="ed-discovery-stream" id={`ed-${kind}-items`}>{trends.slice(0,expanded?3:2).map((t,i)=><button className="ed-signal" key={t.id} onClick={()=>onOpen(t)}><span className="ed-signal-kicker">0{i+1} <span>/</span> {t.tag}</span><strong>{t.name}<span aria-hidden="true">↗</span></strong><span className="ed-signal-description">{t.sub}</span><span className="ed-signal-evidence">{kind==='new'?<><span className="live-dot"/> 새로운 등장</>:<><span className="ed-growth">+{t.growth}%</span> 관심도 증가</>}</span></button>)}</div>
  </div>;
}

export default function EditorialDashboard() {
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
    <header className="site-header"><div className="header-inner"><Link className="brand" href="/drafts/v2" aria-label="ahead 홈">ahead<span className="brand-dot">.</span></Link><nav className="main-nav" aria-label="주 메뉴"><button className={`nav-item ${sheet?.type==='saved'?'':'active'}`} onClick={()=>{setSheet(null);window.scrollTo({top:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}}>나의 트렌드</button><button className={`nav-item ${sheet?.type==='saved'?'active':''}`} onClick={()=>setSheet({type:'saved'})}>저장한 트렌드 <span>{savedTrends.length}</span></button></nav><div className="header-right"><span className="demo-label">DEMO EDITION</span><button className="avatar" aria-label="내 관심 분야 설정" onClick={()=>setSheet({type:'settings'})}>J</button></div></div></header>
    <main className="dashboard editorial-page" id="main-content">
      <section className="ed-intro">
        <div><p className="eyebrow">YOUR INTEREST. A NEW PERSPECTIVE.</p><div className="ed-category-title"><h1>지금,</h1><CategorySwitcher current={category.id} interests={prefs.interests} onSelect={selectCategory} onEdit={()=>setSheet({type:'settings'})}/></div><p className="ed-intro-copy">같은 관심사에서 발견하는, 한발 앞선 이야기.</p></div>
        <div className="ed-issue"><span>THE DAILY EDITION</span><strong>August 30, 2026</strong><span>당신의 관심사로 엮은 오늘</span></div>
      </section>
      <div className="ed-body" key={`${category.id}-${period}`}>
        <section className="ed-top" aria-labelledby="ed-top-title">
          <div className="ed-section-heading"><h2 id="ed-top-title"><span>01</span> 오늘을 움직이는 다섯 가지<span className="ed-heading-en">THE TOP FIVE</span></h2><div className="period-control" aria-label="트렌드 집계 기간">{periods.map(p=><button key={p} className={period===p?'selected':''} aria-pressed={period===p} onClick={()=>setPeriod(p)}>{periodLabels[p]}</button>)}</div></div>
          <div className="ed-ranking"><button className="ed-lead" onClick={()=>setSheet({type:'detail',trend:trends[0]})} aria-label={`1위 ${trends[0].name}, 상세 보기`}><span className="ed-lead-kicker"><span className="ed-lead-rank">01</span><span>IN THE SPOTLIGHT</span><RankChange value={trends[0].change}/></span><span className="ed-lead-category">{trends[0].tag}{prefs.saved.includes(trends[0].id)&&<span className="saved-dot" aria-label="저장됨"/>}</span><strong className="ed-lead-title">{trends[0].name}</strong><span className="ed-lead-description">{trends[0].sub}</span><span className="ed-lead-stats"><span><strong>{format(trends[0].mentions)}</strong><span>최근 {periodLabels[period]} 언급</span></span><span><strong className="ed-growth">+{trends[0].growth}<small>%</small></strong><span>이전 {periodLabels[period]} 대비</span></span><span className="ed-read">이 흐름 읽기 <span aria-hidden="true">↗</span></span></span></button>
            <ol className="ed-index" start={2} aria-label="현재 트렌드 2위부터 5위">{trends.slice(1).map((t,i)=><li key={t.id} style={{'--i':i} as CSSProperties}><button className="ed-index-entry" onClick={()=>setSheet({type:'detail',trend:t})} aria-label={`${i+2}위 ${t.name}, 상세 보기`}><span className="ed-index-rank">0{i+2}</span><span className="ed-index-copy"><span className="ed-index-category">{t.tag}</span><strong>{t.name}{prefs.saved.includes(t.id)&&<span className="saved-dot" aria-label="저장됨"/>}</strong><span className="ed-index-note">{format(t.mentions)}건 <span>·</span> <span className="ed-growth">+{t.growth}%</span></span></span><span className="ed-index-edge"><RankChange value={t.change}/><span aria-hidden="true">↗</span></span></button></li>)}</ol>
          </div>
          <div className="ranking-foot"><span><i className="live-dot"/> 08.30 09:00 기준</span><span>이전 {periodLabels[period]} 대비 · 예시 데이터</span></div>
        </section>
        <section className="ed-discoveries" aria-labelledby="ed-discover-title">
          <div className="ed-section-heading"><h2 id="ed-discover-title"><span>02</span> 다음 이야기는 여기서<span className="ed-heading-en">BEYOND THE TOP FIVE</span></h2><span className="ed-section-aside">아직 작지만, 눈여겨볼 움직임.</span></div>
          <DiscoveryBand kind="new" trends={fresh} expanded={newExpanded} onToggle={()=>setNewExpanded(!newExpanded)} onOpen={trend=>setSheet({type:'detail',trend})}/>
          <DiscoveryBand kind="rising" trends={rising} expanded={risingExpanded} onToggle={()=>setRisingExpanded(!risingExpanded)} onOpen={trend=>setSheet({type:'detail',trend})}/>
        </section>
        <section className="ed-insight" aria-labelledby="ed-insight-title">
          <div className="ed-insight-meta"><span>03 / CONNECT THE DOTS</span><span>트렌드 인사이트 · 예시</span></div>
          <p className="ed-insight-kicker">흩어진 이야기들을 하나로 이으면,</p>
          <h2 id="ed-insight-title">{category.insight}</h2>
          <p className="ed-insight-description">따로 보이던 키워드가, 하나의 흐름으로 이어지고 있어요.</p>
          <div className="ed-keyword-area"><span>함께 떠오르는 키워드</span><div>{category.keywords.map(word=>{const following=prefs.keywords.includes(`${category.id}:${word}`);return <button key={word} onClick={()=>toggleKeyword(word)} aria-pressed={following} className={following?'following':''}><span className="ed-hash">#</span>{word}<span className="ed-keyword-action">{following?'✓':'＋'}</span></button>;})}</div><span className="ed-keyword-hint">＋ 내 관심 키워드로 추가</span></div>
        </section>
      </div>
      <footer className="page-footer"><span className="brand">ahead<span className="brand-dot">.</span></span><p>유행을 따라가기 전에, 흐름을 발견하세요.</p><span>디자인 프리뷰 · 모든 트렌드와 수치는 예시입니다.</span></footer>
    </main>
    {sheet&&<Modal title={sheet.type==='detail'?'TREND NOTE':sheet.type==='saved'?'YOUR COLLECTION':'YOUR INTERESTS'} onClose={()=>setSheet(null)} wide={sheet.type==='settings'}>
      {sheet.type==='settings'?<Interests initial={prefs.interests} onApply={ids=>{updatePrefs({interests:ids,active:ids.includes(prefs.active)?prefs.active:ids[0]});setSheet(null);notify('관심 분야를 새롭게 담았어요.');}}/>:sheet.type==='saved'?<><h2 className="modal-title">다시 만나고 싶은<br/>흐름들<span className="accent">.</span></h2><p className="modal-lead">발견한 순간을 저장해두세요. <span className="saved-count">{savedTrends.length}</span></p>{savedTrends.length?<div className="saved-list">{savedTrends.map(t=><div className="saved-item" key={t.id}><button onClick={()=>setSheet({type:'detail',trend:t,fromSaved:true})}><span>{getCategory(t.category).name} · {t.tag}</span><strong>{t.name}</strong><p>{t.sub}</p></button><button className="unsave-button" onClick={()=>toggleSave(t)} aria-label={`${t.name} 저장 해제`}>×</button></div>)}</div>:<div className="empty-state"><OrbitMark/><h3>아직 비어 있는 컬렉션</h3><p>눈길이 가는 트렌드를 누르고 저장해보세요.<br/>나만의 관심 흐름이 차곡차곡 쌓여요.</p><button className="primary-button" onClick={()=>setSheet(null)}>오늘의 흐름 살펴보기 ↗</button></div>}<p className="device-note">이 브라우저에 저장됩니다. 다른 기기와 동기화되지 않습니다.</p></>:<Detail key={sheet.trend.id} trend={sheet.trend} period={sheet.trend.period} saved={prefs.saved.includes(sheet.trend.id)} onSave={()=>toggleSave(sheet.trend)} onKeyword={word=>toggleKeyword(word,sheet.trend.category)} keywords={prefs.keywords} onBack={sheet.fromSaved?()=>setSheet({type:'saved'}):undefined}/>}
    </Modal>}
    <div className={`toast ${toast?'visible':''}`} role="status" aria-live="polite">{toast&&<><span>✓</span>{toast}</>}</div>
  </>;
}
