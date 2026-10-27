import type { ReactNode } from 'react';

type Tone = 'gray' | 'blue' | 'green' | 'amber' | 'red' | 'purple' | 'indigo';

const TONE_CLASS: Record<Tone, string> = {
  gray: 'bg-gray-100 text-gray-500',
  blue: 'bg-blue-50 text-blue-600',
  green: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
  red: 'bg-red-50 text-red-600',
  purple: 'bg-purple-50 text-purple-600',
  indigo: 'bg-indigo-50 text-indigo-600',
};

interface BadgeProps {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}

export default function Badge({ tone = 'gray', className = '', children }: BadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${TONE_CLASS[tone]} ${className}`}>
      {children}
    </span>
  );
}
