import Link from './page-link';
import type { ReactNode } from 'react';

export default function DraftFrame({ version, children }: { version: 'v1' | 'v2' | 'v3'; children: ReactNode }) {
  return <>
    <div className="draft-strip">
      <div className="draft-strip-inner"><span>DESIGN EXPLORATION <span className="draft-strip-note">같은 취향, 세 가지 시선</span></span>
        <nav aria-label="디자인 초안 비교">
          <Link href="/drafts/v1" className={version === 'v1' ? 'selected' : ''} aria-current={version === 'v1' ? 'page' : undefined}>초안.v1 <span>Grid</span></Link>
          <Link href="/drafts/v2" className={version === 'v2' ? 'selected' : ''} aria-current={version === 'v2' ? 'page' : undefined}>초안.v2 <span>Editorial</span></Link>
          <Link href="/drafts/v3" className={version === 'v3' ? 'selected' : ''} aria-current={version === 'v3' ? 'page' : undefined}>초안.v3 <span>Stage</span></Link>
        </nav>
      </div>
    </div>
    {children}
  </>;
}
