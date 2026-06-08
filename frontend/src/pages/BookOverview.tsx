import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { getBook, getBookChapters, deleteBook, updateBookMotivation } from '../api/books';
import SplitProgress from '../components/SplitProgress';
import { getMasteryRecords } from '../api/review';
import { relearnUnit, enrichUnit, getLearningProgress, getKnowledgeUnit } from '../api/learning';
import type { Book, Chapter, MasteryRecord, LearningProgress, KnowledgeUnit } from '../types';

// 根据层级深度生成样式标记，不硬编码名称
const getLevelBadge = (level: number) => {
  const colors = [
    'bg-blue-100 text-blue-700',
    'bg-indigo-100 text-indigo-700',
    'bg-violet-100 text-violet-700',
    'bg-purple-100 text-purple-700',
    'bg-fuchsia-100 text-fuchsia-700',
  ];
  return colors[Math.min(level, colors.length - 1)];
};

// 根据层级深度生成渐变色
const getLevelGradient = (depth: number) => {
  const gradients = [
    'from-blue-500 to-purple-500',
    'from-indigo-500 to-blue-500',
    'from-violet-500 to-indigo-500',
    'from-purple-500 to-violet-500',
    'from-fuchsia-500 to-purple-500',
  ];
  return gradients[Math.min(depth, gradients.length - 1)];
};

// 层级标题字体大小
const getLevelTitleClass = (level: number): string => {
  switch (level) {
    case 0: return 'text-xl font-bold text-gray-900';
    case 1: return 'text-lg font-semibold text-gray-800';
    case 2: return 'text-base font-medium text-gray-700';
    default: return 'text-sm font-medium text-gray-600';
  }
};

// 中文层级名称
const getLevelName = (level: number): string => {
  const names = ['编', '章', '节', '小节', '条'];
  return names[Math.min(level, names.length - 1)] || `L${level}`;
};

// 递归章节组件
function ChapterNode({
  chapter,
  depth,
  index,
  mastery,
  expandedUnitId,
  onUnitClick,
  onRelearn,
  onEnrich,
}: {
  chapter: Chapter;
  depth: number;
  index: number;
  mastery: MasteryRecord[];
  expandedUnitId: string | null;
  onUnitClick: (unitId: string) => void;
  onRelearn: (unitId: string) => Promise<void>;
  onEnrich: (unitId: string) => Promise<void>;
}) {
  const getUnitMastery = (unitId: string) => {
    const record = mastery.find((m) => m.knowledge_unit_id === unitId);
    return Math.round((record?.mastery_score ?? 0) * 100);
  };

  const getMasteryLevelLabel = (level: string) => {
    const map: Record<string, { label: string; color: string }> = {
      mastered: { label: '已掌握', color: 'bg-emerald-100 text-emerald-700' },
      proficient: { label: '熟练', color: 'bg-blue-100 text-blue-700' },
      familiar: { label: '熟悉', color: 'bg-amber-100 text-amber-700' },
      beginner: { label: '初学', color: 'bg-red-100 text-red-700' },
    };
    return map[level] || { label: '未学习', color: 'bg-gray-100 text-gray-500' };
  };

  const unitCount = chapter.knowledge_units?.length || 0;
  const hasChildren = chapter.children && chapter.children.length > 0;
  const hasUnits = unitCount > 0;
  const isContainer = chapter.is_container;
  const gradientClass = getLevelGradient(depth);
  const badgeClass = getLevelBadge(chapter.level);
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Card className={`animate-fade-in delay-${Math.min((index + 1) * 100, 400)} ${isContainer ? 'bg-gradient-to-r from-slate-50 to-gray-50 border-l-4 border-l-blue-400' : ''}`}>
      {/* 章节标题 */}
      <div
        className={`flex items-center gap-3 mb-3 ${isContainer ? 'cursor-pointer' : ''}`}
        style={{ paddingLeft: depth * 12 }}
        onClick={() => isContainer && setCollapsed(!collapsed)}
      >
        {isContainer ? (
          <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${gradientClass} flex items-center justify-center shadow-sm`}>
            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
            </svg>
          </div>
        ) : (
          <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${gradientClass} flex items-center justify-center text-white text-xs font-bold shadow-sm`}>
            {index + 1}
          </div>
        )}
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${badgeClass}`}>
              {getLevelName(chapter.level)}
            </span>
            <h3 className={getLevelTitleClass(chapter.level)}>{chapter.title}</h3>
          </div>
        </div>
        {isContainer && hasChildren && (
          <span className="text-[10px] text-blue-500 bg-blue-50 px-2 py-0.5 rounded-full font-medium">
            {chapter.children!.length} 子章节
          </span>
        )}
        {!isContainer && hasUnits && (
          <span className="text-[10px] text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">
            {unitCount} 单元
          </span>
        )}
        {isContainer && (
          <span className="text-xs text-gray-400 transition-transform" style={{ transform: collapsed ? 'rotate(0deg)' : 'rotate(90deg)' }}>▶</span>
        )}
      </div>

      {/* 子章节递归渲染 */}
      {hasChildren && !collapsed && (
        <div className={`space-y-3 pl-6 ml-4 ${isContainer ? 'border-l-2 border-blue-200' : 'border-l-2 border-gray-100'}`}>
          {chapter.children!.map((child, i) => (
            <ChapterNode
              key={child.id}
              chapter={child}
              depth={depth + 1}
              index={i}
              mastery={mastery}
              expandedUnitId={expandedUnitId}
              onUnitClick={onUnitClick}
              onRelearn={onRelearn}
              onEnrich={onEnrich}
            />
          ))}
        </div>
      )}

      {/* 知识单元列表（容器节点不显示） */}
      {!isContainer && hasUnits && (
        <div className="space-y-2 pl-11 mt-2">
          {chapter.knowledge_units.map((unit) => {
            const score = getUnitMastery(unit.id);
            const record = mastery.find((m) => m.knowledge_unit_id === unit.id);
            const levelInfo = getMasteryLevelLabel(record?.mastery_level || '');
            const hasAiContent = !!unit.summary;
            const isExpanded = expandedUnitId === unit.id;

            return (
              <div key={unit.id}>
                <div className="flex items-center gap-3 group cursor-pointer" onClick={() => onUnitClick(unit.id)}>
                  <div className="flex-1 flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${score >= 80 ? 'bg-emerald-400' : score >= 50 ? 'bg-amber-400' : score > 0 ? 'bg-red-400' : 'bg-gray-300'}`} />
                    <p className="text-sm text-gray-600 group-hover:text-gray-800 transition-colors">{unit.title}</p>
                    {hasAiContent && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-500 font-medium">已学习</span>
                    )}
                    {record?.mastery_level && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${levelInfo.color}`}>{levelInfo.label}</span>
                    )}
                  </div>
                  <div className="w-24">
                    <ProgressBar value={score} size="sm" color={score >= 80 ? 'green' : score >= 50 ? 'yellow' : 'red'} />
                  </div>
                  <span className="text-xs text-gray-400 w-10 text-right font-medium">{score}%</span>
                  {hasAiContent && (
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={async (e) => { e.stopPropagation(); await onRelearn(unit.id); }}
                        className="text-[10px] text-purple-500 hover:text-purple-600 px-1.5 py-0.5 rounded hover:bg-purple-50 transition-colors"
                        title="重新生成 AI 分析">
                        🔄
                      </button>
                      <button
                        onClick={async (e) => { e.stopPropagation(); await onEnrich(unit.id); }}
                        className="text-[10px] text-emerald-500 hover:text-emerald-600 px-1.5 py-0.5 rounded hover:bg-emerald-50 transition-colors"
                        title="增量更新（补充例子）">
                        ✨
                      </button>
                    </div>
                  )}
                  <span className="text-xs text-gray-400 transition-transform" style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
                </div>

                {/* 展开的详情面板 */}
                {isExpanded && <UnitDetailPanel unitId={unit.id} />}
              </div>
            );
          })}
        </div>
      )}

      {/* 无子章节也无单元时显示提示 */}
      {!isContainer && !hasChildren && !hasUnits && (
        <p className="text-sm text-gray-400 pl-11">暂无知识单元</p>
      )}
    </Card>
  );
}

// 知识单元详情面板组件
function UnitDetailPanel({ unitId }: { unitId: string }) {
  const [detail, setDetail] = useState<KnowledgeUnit | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getKnowledgeUnit(unitId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch(() => { if (!cancelled) setDetail(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [unitId]);

  if (loading) {
    return (
      <div className="mt-3 ml-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>
          加载中...
        </div>
      </div>
    );
  }

  if (!detail?.summary) {
    return (
      <div className="mt-3 ml-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100 text-center py-4">
        <p className="text-sm text-gray-500">暂无 AI 学习数据</p>
      </div>
    );
  }

  return (
    <div className="mt-3 ml-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100 animate-fade-in">
      <div className="space-y-4">
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">AI 摘要</h4>
          <p className="text-sm text-gray-700 leading-relaxed">{detail.summary}</p>
        </div>
        {detail.key_points && detail.key_points.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">关键要点</h4>
            <ul className="space-y-1">
              {detail.key_points.map((point, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                  <span className="text-blue-500 mt-0.5">•</span>
                  <span>{typeof point === 'string' ? point : point.title}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {detail.concepts && detail.concepts.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">核心概念</h4>
            <div className="flex flex-wrap gap-2">
              {detail.concepts.map((concept, idx) => (
                <span key={idx} className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-white text-gray-700 border border-gray-200 shadow-sm">
                  {typeof concept === 'string' ? concept : concept.name}
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="flex items-center gap-4 pt-2 border-t border-blue-100">
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500">难度:</span>
            <div className="flex gap-0.5">
              {[1, 2, 3, 4, 5].map((level) => (
                <div key={level} className={`w-2 h-2 rounded-full ${level <= (detail.difficulty_level || 0) ? 'bg-amber-400' : 'bg-gray-200'}`} />
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500">重要性:</span>
            <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full" style={{ width: `${((detail.importance_score || 0) * 100)}%` }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BookOverview() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [book, setBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [mastery, setMastery] = useState<MasteryRecord[]>([]);
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [splitting, setSplitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [splitError, setSplitError] = useState<string | null>(null);
  const [expandedUnitId, setExpandedUnitId] = useState<string | null>(null);
  const [editingMotivation, setEditingMotivation] = useState(false);
  const [motivationText, setMotivationText] = useState('');
  const [savingMotivation, setSavingMotivation] = useState(false);

  const loadData = async () => {
    try {
      const results = await Promise.allSettled([
        getBook(bookId!),
        getBookChapters(bookId!),
        getMasteryRecords(bookId!),
        getLearningProgress(bookId!),
      ]);
      if (results[0].status === 'fulfilled') setBook(results[0].value);
      if (results[1].status === 'fulfilled') setChapters(results[1].value);
      if (results[2].status === 'fulfilled') setMastery(results[2].value);
      if (results[3].status === 'fulfilled') setProgress(results[3].value);
    } catch (error) {
      console.error('加载书籍详情失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    if (bookId) {
      (async () => {
        try {
          await loadData();
        } catch (error) {
          if (!cancelled) console.error('加载书籍详情失败:', error);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
    }
    return () => { cancelled = true; };
  }, [bookId]);

  // 构建树形结构（支持 parent_id 缺失时按 level 推断层级）
  const chapterTree = useMemo(() => {
    // 先按 order_index 排序（确保文档顺序），再按 level 排序作为次要条件
    const sorted = [...chapters].sort((a, b) => a.order_index - b.order_index || a.level - b.level);

    const roots: Chapter[] = [];
    const map = new Map<string, Chapter>();

    // 初始化所有节点
    for (const ch of sorted) {
      map.set(ch.id, { ...ch, children: [] });
    }

    // 建立父子关系
    // 当 parent_id 缺失时，根据 level 推断：找最近的 level-1 节点作为父节点
    const levelStack: Chapter[] = []; // 维护各级别最近的节点

    for (const ch of sorted) {
      const node = map.get(ch.id)!;

      if (ch.parent_id && map.has(ch.parent_id)) {
        // 有 parent_id 时直接使用
        map.get(ch.parent_id)!.children!.push(node);
      } else if (ch.level > 0) {
        // parent_id 缺失时，按 level 推断父节点
        const parent = levelStack[ch.level - 1];
        if (parent) {
          parent.children!.push(node);
        } else {
          roots.push(node);
        }
      } else {
        roots.push(node);
      }

      // 更新 levelStack：清除当前及更深级别，设置当前节点
      levelStack.length = ch.level;
      levelStack[ch.level] = node;
    }

    // 递归计算 is_container（有子节点的为容器）
    const markContainers = (nodes: Chapter[]) => {
      for (const node of nodes) {
        if (node.children && node.children.length > 0) {
          (node as any).is_container = true;
          markContainers(node.children);
        } else {
          (node as any).is_container = false;
        }
      }
    };
    markContainers(roots);

    return roots;
  }, [chapters]);

  // 统计各级别数量
  const levelStats = useMemo(() => {
    const stats: Record<number, number> = {};
    for (const ch of chapters) {
      stats[ch.level] = (stats[ch.level] || 0) + 1;
    }
    return stats;
  }, [chapters]);

  const handleSplitComplete = async () => {
    setSplitting(false);
    setSplitError(null);
    await loadData();
  };

  const handleSplitError = (message: string) => {
    setSplitting(false);
    setSplitError(message);
  };

  const handleDelete = async () => {
    if (!bookId || !confirm('确定要删除这本书吗？此操作不可恢复。')) return;
    setDeleting(true);
    try {
      await deleteBook(bookId);
      navigate('/');
    } catch (error) {
      console.error('删除失败:', error);
      alert('删除失败，请重试');
      setDeleting(false);
    }
  };

  const handleUnitClick = (unitId: string) => {
    setExpandedUnitId(expandedUnitId === unitId ? null : unitId);
  };

  const handleRelearn = async (unitId: string) => {
    try {
      await relearnUnit(unitId);
      await loadData();
    } catch {
      alert('重新生成失败');
    }
  };

  const handleEnrich = async (unitId: string) => {
    try {
      await enrichUnit(unitId, { focus: 'examples' });
      await loadData();
    } catch {
      alert('增量更新失败');
    }
  };

  if (loading) return <Loading />;
  if (!book) return <div className="text-center py-12 text-gray-500">书籍不存在</div>;

  const needsSplit = chapters.length === 0;

  // 构建统计文本（只显示数量，不假设层级名称）
  const statsText = Object.entries(levelStats)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([level, count]) => `${count} L${level}`)
    .join(' · ');

  // 总章节数
  const totalChapters = chapters.length;

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {/* 书籍头部 */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-800 via-slate-700 to-slate-800 p-8 mb-8 text-white shadow-xl">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PHBhdGggZD0iTTIwIDBMMCA0MGg0MEwyMCAweiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />
        <div className="relative flex items-start justify-between">
          <div className="flex items-start gap-5">
            <div className="w-16 h-20 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center text-3xl shadow-lg border border-white/10">
              📖
            </div>
            <div>
              <h1 className="text-2xl font-bold mb-1">{book.title}</h1>
              {book.author && <p className="text-slate-300 text-sm">{book.author}</p>}
              <div className="flex items-center gap-4 mt-3">
                <span className="text-xs text-slate-400 bg-white/10 px-2.5 py-1 rounded-full">{book.total_chapters} 章节</span>
                <span className="text-xs text-slate-400 bg-white/10 px-2.5 py-1 rounded-full">{book.total_units} 知识单元</span>
                <span className="text-xs text-slate-400 uppercase bg-white/10 px-2.5 py-1 rounded-full">{book.file_type}</span>
              </div>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2 items-center">
            {!needsSplit && !splitting && (
              <button onClick={() => navigate(`/books/${bookId}/toc`)}
                className="flex items-center gap-1.5 px-4 py-2 bg-white/10 text-white rounded-xl text-sm font-medium hover:bg-white/20 transition-all border border-white/10">
                ✏️ 编辑目录
              </button>
            )}
            {!splitting && (
              <button onClick={() => { setSplitting(true); setSplitError(null); }}
                className={`flex items-center gap-1.5 px-4 py-2 text-white rounded-xl text-sm font-medium transition-all ${
                  needsSplit
                    ? 'bg-amber-500 hover:bg-amber-400 shadow-lg shadow-amber-500/25'
                    : 'bg-white/10 hover:bg-white/20 border border-white/10'
                }`}>
                ⚡ {needsSplit ? '知识拆分' : '重新拆分'}
              </button>
            )}
            <button onClick={() => navigate(`/books/${bookId}/learn`)} disabled={needsSplit}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-500 text-white rounded-xl text-sm font-medium hover:bg-blue-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-blue-500/25 transition-all">
              📚 学习
            </button>
            <button onClick={handleDelete} disabled={deleting}
              className="flex items-center gap-1.5 px-3 py-2 bg-white/10 text-red-300 rounded-xl text-sm font-medium hover:bg-red-500/20 disabled:opacity-50 transition-all border border-white/10">
              🗑️ 删除
            </button>
          </div>
        </div>
        <div className="absolute -right-10 -top-10 w-40 h-40 rounded-full bg-blue-500/10 blur-3xl pointer-events-none" />
        <div className="absolute -left-6 -bottom-6 w-32 h-32 rounded-full bg-purple-500/10 blur-2xl pointer-events-none" />
      </div>

      {/* 学习进度概览 */}
      {progress && progress.total_units > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-6 animate-fade-in">
          <Card gradient>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-lg shadow-md">📊</div>
              <div>
                <p className="text-xs text-gray-400">学习进度</p>
                <p className="text-2xl font-bold text-blue-600">{progress.progress_percent}%</p>
              </div>
            </div>
          </Card>
          <Card gradient>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-500 flex items-center justify-center text-lg shadow-md">✅</div>
              <div>
                <p className="text-xs text-gray-400">已学单元</p>
                <p className="text-2xl font-bold text-emerald-600">{progress.learned_units}/{progress.total_units}</p>
              </div>
            </div>
          </Card>
          <Card gradient>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-violet-500 flex items-center justify-center text-lg shadow-md">
                {progress.status === 'completed' ? '🏆' : progress.status === 'in_progress' ? '📖' : '⏳'}
              </div>
              <div>
                <p className="text-xs text-gray-400">状态</p>
                <p className="text-lg font-bold text-purple-600">
                  {progress.status === 'completed' ? '已完成' : progress.status === 'in_progress' ? '进行中' : '未开始'}
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* 拆分错误提示 */}
      {splitError && !splitting && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3 animate-fade-in">
          <span className="text-red-500 text-lg">⚠️</span>
          <div className="flex-1">
            <p className="text-sm font-medium text-red-700">拆分失败</p>
            <p className="text-sm text-red-500 mt-1">{splitError}</p>
          </div>
          <button onClick={() => { setSplitting(true); setSplitError(null); }}
            className="text-sm text-red-600 hover:text-red-700 font-medium underline">
            重试
          </button>
        </div>
      )}

      {/* 阅读动机 */}
      <Card className="mb-6 animate-fade-in">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-lg">🎯</span>
            <h3 className="text-sm font-semibold text-gray-700">阅读动机</h3>
          </div>
          {!editingMotivation && (
            <button
              onClick={() => { setMotivationText(book.reading_motivation || ''); setEditingMotivation(true); }}
              className="text-xs text-blue-500 hover:text-blue-600 px-2 py-1 rounded hover:bg-blue-50 transition-colors"
            >
              {book.reading_motivation ? '编辑' : '设置'}
            </button>
          )}
        </div>
        {editingMotivation ? (
          <div className="space-y-3">
            <textarea
              value={motivationText}
              onChange={(e) => setMotivationText(e.target.value)}
              placeholder="写下你阅读这本书的动机... 为什么读这本书？想从中获得什么？"
              className="w-full p-3 text-sm text-gray-700 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              rows={3}
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setEditingMotivation(false)}
                className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  setSavingMotivation(true);
                  try {
                    const updated = await updateBookMotivation(bookId!, motivationText || null);
                    setBook(updated);
                    setEditingMotivation(false);
                  } catch {
                    alert('保存失败');
                  } finally {
                    setSavingMotivation(false);
                  }
                }}
                disabled={savingMotivation}
                className="px-4 py-1.5 text-xs text-white bg-blue-500 rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
              >
                {savingMotivation ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500 leading-relaxed">
            {book.reading_motivation || '尚未设置阅读动机。点击"设置"写下你阅读这本书的目的。'}
          </p>
        )}
      </Card>

      {/* 章节列表 */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold text-gray-800">章节列表</h2>
        {!needsSplit && statsText && (
          <span className="text-xs text-gray-400">{statsText}</span>
        )}
      </div>

      {splitting ? (
        <SplitProgress
          key={bookId}
          bookId={bookId!}
          onComplete={handleSplitComplete}
          onError={handleSplitError}
        />
      ) : chapterTree.length === 0 ? (
        <Card className="text-center py-16 animate-fade-in">
          <div className="text-5xl mb-4 animate-float">📂</div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">暂无章节数据</h3>
          <p className="text-sm text-gray-400 mb-6 max-w-sm mx-auto">点击上方"知识拆分"按钮，自动解析书籍内容并生成章节和知识单元</p>
          <button onClick={() => { setSplitting(true); setSplitError(null); }}
            className="px-6 py-3 bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-amber-500/25 transition-all">
            ⚡ 开始知识拆分
          </button>
        </Card>
      ) : (
        <div className="space-y-3">
          {chapterTree.map((chapter, i) => (
            <ChapterNode
              key={chapter.id}
              chapter={chapter}
              depth={0}
              index={i}
              mastery={mastery}
              expandedUnitId={expandedUnitId}
              onUnitClick={handleUnitClick}
              onRelearn={handleRelearn}
              onEnrich={handleEnrich}
            />
          ))}
        </div>
      )}
    </div>
  );
}
