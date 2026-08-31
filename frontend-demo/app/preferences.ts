'use client';
import { useSyncExternalStore } from 'react';
import { categories, type CategoryId } from './trends';
type Preferences = { interests: CategoryId[]; active: CategoryId; saved: string[]; keywords: string[]; recentSearches: string[] };
const defaults: Preferences = { interests:['dev','fashion','game'],active:'dev',saved:[],keywords:[],recentSearches:[] };
const key='ahead-demo-preferences-v1';
const serverSnapshot=JSON.stringify(defaults);
let fallback=serverSnapshot;
const listeners=new Set<()=>void>();
function getSnapshot() { try { return window.localStorage.getItem(key) ?? fallback; } catch { return fallback; } }
function read(raw:string): Preferences {
  try {
    const v=JSON.parse(raw); const valid=categories.map(c=>c.id);
    const interests: CategoryId[]=Array.isArray(v.interests)?[...new Set<CategoryId>(v.interests.filter((x:CategoryId)=>valid.includes(x)))].slice(0,3):defaults.interests;
    const chosen=interests.length>=2?interests:defaults.interests;
    return { interests:chosen,active:chosen.includes(v.active)?v.active:chosen[0],saved:Array.isArray(v.saved)?v.saved.filter((x:unknown)=>typeof x==='string'):[],keywords:Array.isArray(v.keywords)?v.keywords.filter((x:unknown)=>typeof x==='string'):[],recentSearches:Array.isArray(v.recentSearches)?v.recentSearches.filter((x:unknown)=>typeof x==='string'&&x.trim().length>0).slice(0,8):[] };
  } catch { return defaults; }
}
function subscribe(listener:()=>void) { listeners.add(listener); window.addEventListener('storage',listener); return ()=>{listeners.delete(listener);window.removeEventListener('storage',listener);}; }
export function usePreferences() {
  const raw=useSyncExternalStore(subscribe,getSnapshot,()=>serverSnapshot);
  const update=(changes:Partial<Preferences>)=>{
    const next=JSON.stringify({...read(getSnapshot()),...changes});fallback=next;
    try { window.localStorage.setItem(key,next); } catch { /* Device-local storage may be unavailable in private browsing. */ }
    listeners.forEach(listener=>listener());
  };
  return [read(raw),update] as const;
}
