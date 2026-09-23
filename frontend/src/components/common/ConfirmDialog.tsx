import { useEffect, useRef } from 'react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  /** 보내는 중에 단추에 대신 띄울 말. 주면 그동안 닫을 수도 없습니다. */
  pendingLabel?: string;
  pending?: boolean;
  /** 되돌릴 수 없는 일이면 확인 단추를 붉게 세웁니다. 상자 자체의 모양은 같습니다. */
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * 한 번 더 묻는 대화상자.
 *
 * **네이티브 `<dialog>` 를 씁니다.** 직접 만든 오버레이로는 배경 잠금, 초점 가두기, Esc 닫기,
 * 뒤 내용 비활성을 하나씩 다시 구현해야 하는데 `showModal()` 은 그 넷을 그냥 줍니다.
 * 접근성에서 틀리기 쉬운 부분이라 브라우저에 맡기는 쪽이 안전합니다.
 *
 * 보내는 중에는 닫히지 않습니다. 요청이 날아가는 동안 상자가 사라지면 사용자는 취소된 줄
 * 알지만 서버는 그대로 처리합니다.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  pendingLabel,
  pending = false,
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    /* 이미 열려 있는데 또 부르면 예외가 납니다. 상태와 실제 열림을 맞춰 둡니다. */
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="confirm-dialog"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
      /* Esc 로 닫는 길. 보내는 중에는 막습니다. */
      onCancel={(event) => {
        event.preventDefault();
        if (!pending) onCancel();
      }}
      /*
       * 바깥을 누르면 닫습니다. `<dialog>` 자신이 배경까지 차지하므로, 눌린 자리가 상자
       * 바깥이면 그 대상이 dialog 자신으로 잡힙니다.
       */
      onClick={(event) => {
        if (event.target === dialogRef.current && !pending) onCancel();
      }}
    >
      <h2 id="confirm-dialog-title">{title}</h2>
      <p id="confirm-dialog-description">{description}</p>
      <div className="confirm-dialog-actions">
        <button type="button" className="mypage-btn mypage-btn--ghost" disabled={pending} onClick={onCancel}>
          취소
        </button>
        <button
          type="button"
          className={`mypage-btn ${danger ? 'mypage-btn--danger' : 'mypage-btn--primary'}`}
          disabled={pending}
          onClick={onConfirm}
        >
          {pending ? pendingLabel ?? confirmLabel : confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
