import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { startSplit, getSplitResult, splitProgressSSE } from '../api/books';

interface SplitProgressProps {
  bookId: string;
  onComplete: (result: { chapters_count: number; sections_count: number; units_count: number }) => void;
  onError: (message: string) => void;
}

const STAGE_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  pending:    { icon: '⏳', label: '准备中',    color: 'gray' },
  reading:    { icon: '📖', label: '读取文件',  color: 'blue' },
  parsing:    { icon: '🔍', label: '解析文档',  color: 'blue' },
  splitting_chapters: { icon: '📑', label: '拆分章节', color: 'purple' },
  splitting_units:    { icon: '🧩', label: '拆分知识单元', color: 'purple' },
  saving:     { icon: '💾', label: '保存数据',  color: 'green' },
  done:       { icon: '✅', label: '完成',      color: 'green' },
  error:      { icon: '❌', label: '出错',      color: 'red' },
};

const STAGES_ORDER = ['pending', 'reading', 'parsing', 'splitting_chapters', 'splitting_units', 'saving', 'done'];

// 判断是否为 NoTOCError（书本导入模块问题）
const isNoTOCError = (message: string): boolean => {
  return message.includes('书本导入模块') || message.includes('未能识别目录');
};

export default function SplitProgress({ bookId, onComplete, onError }: SplitProgressProps) {
  const navigate = useNavigate();
  const [started, setStarted] = useState(false);
  const [stage, setStage] = useState('pending');
  const [percent, setPercent] = useState(0);
  const [message, setMessage] = useState('正在启动...');
  const [error, setError] = useState('');
  const [errorDetail, setErrorDetail] = useState('');
  const [chaptersCount, setChaptersCount] = useState(0);
  const [sectionsCount, setSectionsCount] = useState(0);
  const [unitsCount, setUnitsCount] = useState(0);
  const cancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        // 1. 启动拆分任务
        await startSplit(bookId);
        if (cancelled) return;
        setStarted(true);

        // 2. 连接 SSE 监听进度
        cancelRef.current = splitProgressSSE(
          bookId,
          (data) => {
            if (cancelled) return;
            setStage(data.stage);
            setPercent(data.percent);
            setMessage(data.message);

            if (data.done && !data.error) {
              // 3. 完成后拉取结果
              getSplitResult(bookId).then((result) => {
                if (cancelled) return;
                setChaptersCount(result.chapters_count);
                setSectionsCount(result.sections_count ?? 0);
                setUnitsCount(result.units_count);
                setStage('done');
                setPercent(100);
                const sectionInfo = result.sections_count ? `，${result.sections_count} 个小节` : '';
                setMessage(`拆分完成！${result.chapters_count} 章节${sectionInfo}，${result.units_count} 知识单元`);
                onComplete({
                  chapters_count: result.chapters_count,
                  sections_count: result.sections_count ?? 0,
                  units_count: result.units_count,
                });
              }).catch(() => {
                if (cancelled) return;
                setStage('done');
                setPercent(100);
                setMessage('拆分完成！');
                onComplete({ chapters_count: 0, sections_count: 0, units_count: 0 });
              });
            }

            if (data.error) {
              setError(data.message);
              // 解析错误详情（NoTOCError 会返回多行建议）
              const lines = data.message.split('\n');
              if (lines.length > 1) {
                setErrorDetail(lines.slice(1).join('\n'));
              }
              onError(data.message);
            }
          },
          (err) => {
            if (cancelled) return;
            setError(err.message);
            onError(err.message);
          },
        );
      } catch (e: any) {
        if (cancelled) return;
        setError(e.message || '启动拆分失败');
        onError(e.message || '启动拆分失败');
      }
    };

    run();

    return () => {
      cancelled = true;
      cancelRef.current?.();
    };
  }, [bookId]);

  const currentStage = STAGE_CONFIG[stage] || STAGE_CONFIG.pending;
  const currentIndex = STAGES_ORDER.indexOf(stage);

  const getStageStatus = (s: string) => {
    const idx = STAGES_ORDER.indexOf(s);
    if (s === 'error' && stage === 'error') return 'error';
    if (idx < currentIndex) return 'done';
    if (s === stage) return 'active';
    return 'pending';
  };

  const noTOCError = isNoTOCError(error);

  return (
    <div className="animate-scale-in">
      {/* 主进度卡片 */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800 via-slate-700 to-slate-800 p-8 text-white shadow-xl">
        {/* 背景装饰 */}
        <div className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-blue-500/10 blur-3xl" />
        <div className="absolute -left-8 -bottom-8 w-36 h-36 rounded-full bg-purple-500/10 blur-2xl" />

        <div className="relative">
          {/* 头部 */}
          <div className="flex items-center gap-4 mb-6">
            <div className="relative w-14 h-14">
              <svg className="w-14 h-14 -rotate-90" viewBox="0 0 56 56">
                <circle cx="28" cy="28" r="24" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="4" />
                <circle
                  cx="28" cy="28" r="24" fill="none"
                  stroke="url(#splitGradient)" strokeWidth="4" strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 24}`}
                  strokeDashoffset={`${2 * Math.PI * 24 * (1 - percent / 100)}`}
                  className="transition-all duration-500"
                />
                <defs>
                  <linearGradient id="splitGradient" x1="0%" y1="0%" x2="100%" y2="0%">
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
              <h3 className="text-lg font-bold">知识拆分中</h3>
              <p className="text-sm text-slate-300 mt-0.5">{message}</p>
            </div>
          </div>

          {/* 阶段步骤 */}
          <div className="flex items-center gap-1 mb-4">
            {STAGES_ORDER.filter(s => s !== 'pending' && s !== 'done').map((s, i) => {
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
                  {i < 4 && (
                    <div className={`flex-1 h-px mx-1 ${
                      getStageStatus(STAGES_ORDER[i + 2]) === 'done' ? 'bg-emerald-500/40' : 'bg-white/10'
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

      {/* 完成结果 */}
      {stage === 'done' && !error && (chaptersCount > 0 || unitsCount > 0) && (
        <div className="mt-4 p-4 bg-emerald-50 border border-emerald-100 rounded-xl flex items-center gap-4 animate-fade-in">
          <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center text-xl">🎉</div>
          <div>
            <p className="text-sm font-semibold text-emerald-700">拆分完成！</p>
            <p className="text-xs text-emerald-600 mt-0.5">
              共 {chaptersCount} 个章节
              {sectionsCount > 0 ? `，${sectionsCount} 个小节` : ''}
              ，{unitsCount} 个知识单元
            </p>
          </div>
        </div>
      )}

      {/* 错误 — NoTOCError 特殊展示 */}
      {error && noTOCError && (
        <div className="mt-4 p-5 bg-amber-50 border border-amber-200 rounded-xl animate-fade-in">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center text-xl shrink-0">⚠️</div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-800 mb-2">书本导入模块未能识别目录</p>
              {errorDetail && (
                <ul className="text-xs text-amber-700 space-y-1 mb-4 list-disc list-inside">
                  {errorDetail.split('\n').filter(l => l.trim()).map((line, i) => (
                    <li key={i}>{line.replace(/^[①②③]\s*/, '')}</li>
                  ))}
                </ul>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => navigate(`/books/${bookId}/toc`)}
                  className="px-4 py-2 bg-amber-500 text-white rounded-lg text-xs font-medium hover:bg-amber-400 transition-colors"
                >
                  📝 手动编辑目录
                </button>
                <button
                  onClick={() => navigate('/upload')}
                  className="px-4 py-2 bg-white text-amber-700 border border-amber-200 rounded-lg text-xs font-medium hover:bg-amber-50 transition-colors"
                >
                  📤 重新上传文件
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 错误 — 通用错误 */}
      {error && !noTOCError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-100 rounded-xl flex items-center gap-3 animate-fade-in">
          <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center text-red-500 shrink-0">❌</div>
          <div className="flex-1">
            <p className="text-sm text-red-600">{error}</p>
          </div>
          <button
            onClick={() => navigate(0)}
            className="px-3 py-1.5 bg-red-100 text-red-600 rounded-lg text-xs font-medium hover:bg-red-200 transition-colors shrink-0"
          >
            重试
          </button>
        </div>
      )}
    </div>
  );
}
