import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
import Icon from './Icon';

type ToastType = 'success' | 'error' | 'info';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TYPE_STYLE: Record<ToastType, { icon: string; cls: string }> = {
  success: { icon: 'checkCircle', cls: 'bg-emerald-600 text-white' },
  error: { icon: 'alert', cls: 'bg-red-500 text-white' },
  info: { icon: 'sparkles', cls: 'bg-slate-800 text-white' },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = nextId.current++;
    setItems(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setItems(prev => prev.filter(t => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] flex flex-col items-center gap-2 pointer-events-none">
        {items.map(t => (
          <div key={t.id}
               className={`flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-lg text-sm font-medium animate-scale-in ${TYPE_STYLE[t.type].cls}`}>
            <Icon name={TYPE_STYLE[t.type].icon} className="w-4 h-4 shrink-0" />
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}
