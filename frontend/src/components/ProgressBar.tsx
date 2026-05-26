interface ProgressBarProps {
  value: number;
  max?: number;
  showText?: boolean;
  size?: 'sm' | 'md' | 'lg';
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple';
  className?: string;
}

const colorClasses = {
  blue: 'from-blue-500 to-blue-400',
  green: 'from-emerald-500 to-emerald-400',
  yellow: 'from-amber-500 to-amber-400',
  red: 'from-red-500 to-red-400',
  purple: 'from-purple-500 to-purple-400',
};

const bgClasses = {
  blue: 'bg-blue-100',
  green: 'bg-emerald-100',
  yellow: 'bg-amber-100',
  red: 'bg-red-100',
  purple: 'bg-purple-100',
};

const sizeClasses = {
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-4',
};

export default function ProgressBar({
  value,
  max = 100,
  showText = false,
  size = 'md',
  color = 'blue',
  className = '',
}: ProgressBarProps) {
  const percent = Math.min(Math.round((value / max) * 100), 100);

  return (
    <div className={`w-full ${className}`}>
      <div className={`w-full ${bgClasses[color]} rounded-full overflow-hidden ${sizeClasses[size]}`}>
        <div
          className={`h-full rounded-full bg-gradient-to-r ${colorClasses[color]} transition-all duration-500 ease-out`}
          style={{ width: `${percent}%` }}
        />
      </div>
      {showText && (
        <div className="flex justify-between mt-1.5">
          <span className="text-xs text-gray-400">{value}/{max}</span>
          <span className="text-xs font-medium text-gray-500">{percent}%</span>
        </div>
      )}
    </div>
  );
}
