export type ToastType = 'success' | 'error';
export interface ToastDetail { message: string; type?: ToastType; }

export function showToast(detail: ToastDetail) {
  window.dispatchEvent(new CustomEvent<ToastDetail>('app:toast', { detail }));
}

