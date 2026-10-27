import type { ButtonHTMLAttributes, ReactNode } from 'react';
import Icon from './Icon';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success' | 'warning';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: string;
  loading?: boolean;
  children?: ReactNode;
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary: 'bg-blue-600 text-white hover:bg-blue-500 shadow-sm shadow-blue-600/20 disabled:hover:bg-blue-600',
  secondary: 'bg-white text-gray-700 border border-gray-200 hover:border-gray-300 hover:bg-gray-50',
  ghost: 'bg-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-100',
  danger: 'bg-red-500 text-white hover:bg-red-400 shadow-sm shadow-red-500/20 disabled:hover:bg-red-500',
  success: 'bg-emerald-500 text-white hover:bg-emerald-400 shadow-sm shadow-emerald-500/20 disabled:hover:bg-emerald-500',
  warning: 'bg-amber-500 text-white hover:bg-amber-400 shadow-sm shadow-amber-500/20 disabled:hover:bg-amber-500',
};

const SIZE_CLASS: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
  lg: 'px-6 py-3 text-sm gap-2',
};

const ICON_SIZE: Record<Size, string> = {
  sm: 'w-3.5 h-3.5',
  md: 'w-4 h-4',
  lg: 'w-4 h-4',
};

export default function Button({
  variant = 'primary', size = 'md', icon, loading = false,
  className = '', disabled, children, ...rest
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-medium rounded-xl
        transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed
        ${VARIANT_CLASS[variant]} ${SIZE_CLASS[size]} ${className}`}
      {...rest}
    >
      {loading ? (
        <span className={`${ICON_SIZE[size]} border-2 border-current border-t-transparent rounded-full animate-spin`} />
      ) : icon ? (
        <Icon name={icon} className={ICON_SIZE[size]} />
      ) : null}
      {children}
    </button>
  );
}
