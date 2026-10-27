import { useEffect, type ReactNode } from 'react';
import Button from './Button';
import Icon from './Icon';

interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}

export default function Modal({ open, title, onClose, children, footer, width = 'max-w-md' }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className={`relative w-full ${width} bg-white rounded-2xl shadow-2xl animate-scale-in`}>
        <div className="flex items-center justify-between px-6 pt-5 pb-3">
          <h3 className="text-base font-bold text-gray-800">{title}</h3>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
            <Icon name="x" className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 pb-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-100">{footer}</div>}
      </div>
    </div>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmText?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open, title, message, confirmText = '确认', danger = false, loading = false,
  onConfirm, onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} title={title} onClose={onCancel} footer={
      <>
        <Button variant="secondary" onClick={onCancel} disabled={loading}>取消</Button>
        <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={loading}>{confirmText}</Button>
      </>
    }>
      <p className="text-sm text-gray-500 leading-relaxed">{message}</p>
    </Modal>
  );
}
