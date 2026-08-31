import type { AnchorHTMLAttributes } from 'react';

/**
 * Use document navigation for this deployed Vinext build. Its next/link shim
 * prevents the browser's default click, then fails while loading the client
 * router ("navigateClientSide is not a function"). A native anchor preserves
 * query strings, keyboard activation, new-tab gestures and browser history.
 * Device-local interests and saved trends survive the document navigation.
 */
export default function PageLink(props: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a {...props}/>;
}
