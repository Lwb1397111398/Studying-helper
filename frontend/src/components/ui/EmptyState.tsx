import type { ReactNode } from 'react';
import Icon from './Icon';

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function EmptyState({ icon = 'folder', title, description, action }: EmptyStateProps) {
  return (
    <div className="text-center py-16 animate-fade-in">
      <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center">
        <Icon name={icon} className="w-8 h-8 text-blue-300" />
      </div>
      <h3 className="text-lg font-semibold text-gray-700 mb-2">{title}</h3>
      {description && <p className="text-sm text-gray-400 mb-6 max-w-sm mx-auto">{description}</p>}
      {action}
    </div>
  );
}
