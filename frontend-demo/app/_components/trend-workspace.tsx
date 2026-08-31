'use client';

import { useState } from 'react';
import Link from './page-link';
import { usePreferences } from '../preferences';
import { getCategory, getTrend, type Trend } from '../trends';
import { Detail, Interests, Modal, OrbitMark } from './dashboard-v1';

type Sheet = { type: 'detail'; trend: Trend; fromSaved?: boolean } | { type: 'saved' } | { type: 'settings' } | null;
export function useTrendWorkspace() {
  const [prefs, updatePrefs] = usePreferences();
  const [sheet, setSheet] = useState<Sheet>(null);
  const savedTrends = prefs.saved.map(getTrend).filter((t): t is Trend => !!t);
  const toggleSave = (trend: Trend) => updatePrefs({ saved: prefs.saved.includes(trend.id) ? prefs.saved.filter(id => id !== trend.id) : [...prefs.saved, trend.id] });
  const toggleKeyword = (word: string, categoryId: string) => {
    const key = `${categoryId}:${word}`;
    updatePrefs({ keywords: prefs.keywords.includes(key) ? prefs.keywords.filter(k => k !== key) : [...prefs.keywords, key] });
  };
  return { prefs, updatePrefs, sheet, setSheet, savedTrends, toggleSave, toggleKeyword, openTrend: (trend: Trend) => setSheet({ type: 'detail', trend }) };
}
export function WorkspaceOverlays({ workspace: w }: { workspace: ReturnType<typeof useTrendWorkspace> }) {
  const { sheet, prefs } = w;
  if (!sheet) return null;
  return <Modal title={sheet.type === 'detail' ? 'TREND NOTE' : sheet.type === 'saved' ? 'YOUR COLLECTION' : 'YOUR INTERESTS'} onClose={() => w.setSheet(null)} wide={sheet.type === 'settings'}>
    {sheet.type === 'settings' ? <Interests initial={prefs.interests} onApply={ids => { w.updatePrefs({ interests: ids, active: ids.includes(prefs.active) ? prefs.active : ids[0] }); w.setSheet(null); }}/>
      : sheet.type === 'saved' ? <><h2 className="modal-title">다시 만나고 싶은<br/>흐름들<span className="accent">.</span></h2><p className="modal-lead">이 브라우저에서 모아둔 트렌드 <span className="saved-count">{w.savedTrends.length}</span></p>
        {w.savedTrends.length ? <div className="saved-list">{w.savedTrends.map(t => <div className="saved-item" key={t.id}><button onClick={() => w.setSheet({ type: 'detail', trend: t, fromSaved: true })}><span>{getCategory(t.category).name} · {t.tag}</span><strong>{t.name}</strong><p>{t.sub}</p></button><button className="unsave-button" onClick={() => w.toggleSave(t)} aria-label={`${t.name} 저장 해제`}>×</button></div>)}</div>
          : <div className="empty-state"><OrbitMark/><h3>아직 비어 있는 컬렉션</h3><p>관심 있는 트렌드를 저장하면<br/>어느 페이지에서든 다시 만날 수 있어요.</p><button className="primary-button" onClick={() => w.setSheet(null)}>계속 둘러보기 ↗</button></div>}
        <p className="device-note">이 브라우저에 저장됩니다. 다른 기기와 동기화되지 않습니다.</p></>
        : <Detail key={sheet.trend.id} trend={sheet.trend} period={sheet.trend.period} saved={prefs.saved.includes(sheet.trend.id)} onSave={() => w.toggleSave(sheet.trend)} onKeyword={word => w.toggleKeyword(word, sheet.trend.category)} keywords={prefs.keywords} onBack={sheet.fromSaved ? () => w.setSheet({ type: 'saved' }) : undefined}/>}
  </Modal>;
}

export function ExploreFooter() {
  return <footer className="explore-footer"><span>ahead<span className="brand-dot">.</span></span><p>모든 트렌드·수치·분석은 디자인 검토용 예시입니다. 실시간 데이터는 연결되지 않았습니다.</p><Link href="/">대시보드로 ↗</Link></footer>;
}
