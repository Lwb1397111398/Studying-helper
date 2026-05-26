import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  hover?: boolean;
  gradient?: boolean;
}

export default function Card({ children, className = '', onClick, hover = true, gradient = false }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`
        relative bg-white rounded-2xl border border-gray-100/80 p-6
        shadow-[0_1px_3px_0_rgb(0_0_0_0.04),0_1px_2px_-1px_rgb(0_0_0_0.03)]
        ${hover ? 'hover:shadow-[0_8px_24px_-4px_rgb(0_0_0_0.08),0_4px_8px_-4px_rgb(0_0_0_0.04)] hover:-translate-y-0.5 cursor-pointer' : ''}
        ${gradient ? 'bg-gradient-to-br from-white via-white to-blue-50/30' : ''}
        transition-all duration-200 ease-out
        ${className}
      `}
    >
      {children}
    </div>
  );
}
