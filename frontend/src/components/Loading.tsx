interface LoadingProps {
  text?: string;
}

export default function Loading({ text = '加载中...' }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
      <div className="relative w-12 h-12">
        <div className="absolute inset-0 rounded-full border-3 border-blue-100" />
        <div className="absolute inset-0 rounded-full border-3 border-transparent border-t-blue-500 animate-spin" />
        <div className="absolute inset-2 rounded-full border-3 border-transparent border-t-purple-400 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '0.8s' }} />
      </div>
      <p className="mt-5 text-sm text-gray-400 font-medium">{text}</p>
    </div>
  );
}
