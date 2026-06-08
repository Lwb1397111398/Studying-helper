import { useEffect, useState, useRef } from 'react';
import { parseProgressSSE, type ParseProgressData } from '../api/books';
import type { Book } from '../types';

interface ParseProgressProps {
  uploadId: string;
  onComplete: (book: Book) => void;
  onError: (message: string) => void;
}

const STAGE_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  uploading: { icon: '📤', label: '上传文件', color: 'blue' },
  reading:   { icon: '📖', label: '读取解析', color: 'blue' },
  parsing:   { icon: '🔍', label: '解析文档', color: 'purple' },
  saving:    { icon: '💾', label: '保存数据', color: 'green' },
  done:      { icon: '✅', label: '完成',     color: 'green' },
  error:     { icon: '❌', label: '出错',     color: 'red' },
};

const STAGES_ORDER = ['uploading', 'reading', 'parsing', 'saving', 'done'];

export default function ParseProgress({ uploadId, onComplete, onError }: ParseProgressProps) {
  const [stage, setStage] = useState('uploading');
  const [percent, setPercent] = useState(0);
  const [message, setMessage] = useState('正在上传文件...');
  const [error, setError] = useState('');
  const [book, setBook] = useState<Book | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let cancelled = false;

    cancelRef.current = parseProgressSSE(
      uploadId,
      (data: ParseProgressData) => {
        if (cancelled) return;
        setStage(data.stage);
        setPercent(data.percent);
        setMessage(data.message);

        if (data.done && !data.error && data.book) {
          setBook(data.book);
          onComplete(data.book);
        }

        if (data.error) {
          setError(data.message);
          onError(data.message);
        }
      },
      (err) => {
        if (cancelled) return;
        setError(err.message);
        onError(err.message);
      },
    );

    return () => {
      cancelled = true;
      cancelRef.current?.();
    };
  }, [uploadId]);

  const currentStageCfg = STAGE_CONFIG[stage] || STAGE_CONFIG.uploading;
  const currentIndex = STAGES_ORDER.indexOf(stage);

  const getStageStatus = (s: string) => {
    const idx = STAGES_ORDER.indexOf(s);
    if (s === 'error' && stage === 'error') return 'error';
    if (idx < currentIndex) return 'done';
    if (s === stage) return 'active';
    return 'pending';
  };

  return (
    <div className="animate-scale-in">
      {/* 主进度卡片 */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800 via-slate-700 to-slate-800 p-8 text-white shadow-xl">
        <div className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-blue-500/10 blur-3xl" />
        <div className="absolute -left-8 -bottom-8 w-36 h-36 rounded-full bg-purple-500/10 blur-2xl" />

        <div className="relative">
          {/* 头部：圆环 + 文字 */}
          <div className="flex items-center gap-4 mb-6">
            <div className="relative w-14 h-14">
              <svg className="w-14 h-14 -rotate-90" viewBox="0 0 56 56">
                <circle cx="28" cy="28" r="24" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="4" />
                <circle
                  cx="28" cy="28" r="24" fill="none"
                  stroke="url(#parseGradient)" strokeWidth="4" strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 24}`}
                  strokeDashoffset={`${2 * Math.PI * 24 * (1 - percent / 100)}`}
                  className="transition-all duration-500"
                />
                <defs>
                  <linearGradient id="parseGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#3b82f6" />
                    <stop offset="100%" stopColor="#8b5cf6" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-sm font-bold">{percent}%</span>
              </div>
            </div>
            <div>
              <h3 className="text-lg font-bold">正在解析文档</h3>
              <p className="text-sm text-slate-300 mt-0.5">{message}</p>
            </div>
          </div>

          {/* 阶段步骤条 */}
          <div className="flex items-center gap-1 mb-4">
            {STAGES_ORDER.filter(s => s !== 'done').map((s, i, arr) => {
              const cfg = STAGE_CONFIG[s];
              const status = getStageStatus(s);
              return (
                <div key={s} className="flex items-center flex-1">
                  <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                    status === 'done' ? 'bg-emerald-500/20 text-emerald-300' :
                    status === 'active' ? 'bg-blue-500/20 text-blue-300 ring-1 ring-blue-400/30' :
                    status === 'error' ? 'bg-red-500/20 text-red-300' :
                    'bg-white/5 text-slate-500'
                  }`}>
                    <span>{status === 'done' ? '✓' : cfg.icon}</span>
                    <span className="hidden sm:inline">{cfg.label}</span>
                  </div>
                  {i < arr.length - 1 && (
                    <div className={`flex-1 h-px mx-1 ${
                      getStageStatus(STAGES_ORDER[i + 1]) === 'done' ? 'bg-emerald-500/40' : 'bg-white/10'
                    }`} />
                  )}
                </div>
              );
            })}
          </div>

          {/* 进度条 */}
          <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 transition-all duration-500 ease-out"
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>
      </div>

      {/* 完成提示 */}
      {stage === 'done' && !error && book && (
        <div className="mt-4 p-4 bg-emerald-50 border border-emerald-100 rounded-xl flex items-center gap-4 animate-fade-in">
          <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center text-xl">🎉</div>
          <div>
            <p className="text-sm font-semibold text-emerald-700">解析完成！</p>
            <p className="text-xs text-emerald-600 mt-0.5">
              《{book.title}》共 {book.total_chapters} 个章节
            </p>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-100 rounded-xl flex items-center gap-3 animate-fade-in">
          <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center text-red-500 shrink-0">❌</div>
          <div className="flex-1">
            <p className="text-sm font-medium text-red-700">解析失败</p>
            <p className="text-xs text-red-500 mt-0.5">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
