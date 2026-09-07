import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';
import { Spinner } from './Spinner';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  isLoading?: boolean;
}

export function Button({ children, isLoading = false, disabled, ...props }: PropsWithChildren<ButtonProps>) {
  return (
    <button {...props} disabled={disabled || isLoading}>
      {isLoading && <Spinner size="small" />}
      {children}
    </button>
  );
}

