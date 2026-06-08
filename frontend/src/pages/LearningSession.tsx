import { useEffect, useState, useCallback, useRef, useLayoutEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { getBookChapters } from '../api/books';
import SplitProgress from '../components/SplitProgress';
import {
  getKnowledgeUnit, startLearningSession, endLearningSession,
  saveNote, markUnit, startLearning, relearnUnit, enrichUnit,
  restoreUnit, getAILearningProgress,
} from '../api/learning';
import type { Chapter, KnowledgeUnit, LearningRecord, KeyPoint } from '../types';

// 增量更新方向配置
const ENRICH_DIRECTIONS = [
  { key: 'examples', label: '补充例子', icon: '📌' },
  { key: 'explanations', label: '深入解释', icon: '💡' },
  { key: 'connections', label: '关联拓展', icon: '🔗' },
  { key: 'applications', label: '实践应用', icon: '🛠️' },
  { key: 'mistakes', label: '易错点', icon: '⚠️' },
  { key: 'simplify', label: '简化总结', icon: '✂️' },
] as const;

type EnrichFocus = typeof ENRICH_DIRECTIONS[number]['key'];

// 概念标签组件（弹出层用 portal 渲染，避免被下方元素遮挡）
function ConceptTag({ concept, index, isExpanded, onToggle, onClose }: {
  concept: string | { name: string; definition?: string; examples?: string[]; related_concepts?: string[] };
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
  onClose: () => void;
}) {
  const isObj = typeof concept !== 'string';
  const btnRef = useRef<HTMLButtonElement>(null);
  const [popupStyle, setPopupStyle] = useState<React.CSSProperties>({});
  const popupRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (isExpanded && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      const popupWidth = 288; // w-72 = 18rem = 288px
      let left = rect.left;
      // 防止超出右边界
      if (left + popupWidth > window.innerWidth - 8) {
        left = window.innerWidth - popupWidth - 8;
      }
      setPopupStyle({
        position: 'fixed',
        left,
        top: rect.bottom + 4,
        zIndex: 9999,
        width: popupWidth,
      });
    }
  }, [isExpanded]);

  // 点击外部关闭
  useEffect(() => {
    if (!isExpanded) return;
    const handler = (e: MouseEvent) => {
      if (btnRef.current?.contains(e.target as Node)) return;
      if (popupRef.current?.contains(e.target as Node)) return;
      onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isExpanded, onClose]);

  return (
    <>
      <button ref={btnRef} onClick={onToggle}
        className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${isObj ? 'bg-blue-50 text-blue-600 border-blue-100 hover:bg-blue-100 cursor-pointer' : 'bg-blue-50 text-blue-600 border-blue-100'}`}>
        {isObj ? concept.name : concept}
        {isObj && <span className="ml-1 text-blue-400">{isExpanded ? '▲' : '▼'}</span>}
      </button>
      {isExpanded && isObj && createPortal(
        <div ref={popupRef} style={popupStyle} className="p-3 bg-white rounded-xl shadow-lg border border-gray-100 text-left animate-scale-in">
          {concept.definition && <p className="text-xs text-gray-700 mb-2"><span className="font-semibold text-gray-500">定义：</span>{concept.definition}</p>}
          {concept.examples && concept.examples.length > 0 && (
            <div className="text-xs text-gray-600">
              <span className="font-semibold text-gray-500">示例：</span>
              <ul className="mt-1 space-y-0.5 list-disc list-inside">{concept.examples.map((ex, j) => <li key={j}>{ex}</li>)}</ul>
            </div>
          )}
          {concept.related_concepts && concept.related_concepts.length > 0 && (
            <p className="text-xs text-gray-600 mt-1"><span className="font-semibold text-gray-500">关联：</span>{concept.related_concepts.join('、')}</p>
          )}
        </div>,
        document.body
      )}
    </>
  );
}

// 时间线风格的章节树节点组件
type ChapterTreeNode = Omit<Chapter, 'children'> & { children?: ChapterTreeNode[] };

function ChapterTimelineNode({
  chapter, depth, isLast, currentUnitId, selectMode, selectedUnitIds,
  collapsedChapters, onToggleCollapse, onLoadUnit, onToggleSelection,
}: {
  chapter: ChapterTreeNode; depth: number; isLast: boolean;
  currentUnitId?: string; selectMode: boolean; selectedUnitIds: Set<string>;
  collapsedChapters: Set<string>; onToggleCollapse: (id: string) => void;
  onLoadUnit: (id: string) => void; onToggleSelection: (id: string) => void;
}) {
  const isContainer = chapter.is_container;
  const units = chapter.knowledge_units || [];
  const learnedCount = units.filter((u) => u.summary).length;
  const isCollapsed = collapsedChapters.has(chapter.id);
  const hasChildren = chapter.children && chapter.children.length > 0;
  // 单单元叶子节点：合并显示，不展开单元列表
  const isMerged = !isContainer && !hasChildren && units.length === 1;
  const showUnits = !isContainer && !isMerged && !isCollapsed && units.length > 0;

  // 时间线圆点样式
  const dotStyles = [
    { size: 'w-2.5 h-2.5', color: 'bg-blue-500', ring: 'ring-2 ring-blue-100' },     // 编
    { size: 'w-2 h-2', color: 'bg-indigo-400', ring: 'ring-2 ring-indigo-50' },        // 章
    { size: 'w-1.5 h-1.5', color: 'bg-violet-400', ring: '' },                         // 节
  ];
  const dot = dotStyles[Math.min(depth, dotStyles.length - 1)];

  // 字体样式
  const fontStyles = [
    'text-[11px] font-bold tracking-wide',      // 编：加粗+字间距
    'text-[11px] font-semibold',                 // 章：半粗
    'text-[10.5px] font-medium text-gray-600',   // 节：中等
  ];
  const fontClass = fontStyles[Math.min(depth, fontStyles.length - 1)];

  return (
    <div>
      {/* 章节标题行 */}
      <div className={`relative flex items-center ${isMerged && currentUnitId === units[0]?.id ? 'bg-blue-50/80 rounded' : ''}`}
        style={{ paddingLeft: depth * 14 + 8 }}>
        {/* 竖线连接（非首层） */}
        {depth > 0 && (
          <div className="absolute top-0 bottom-0 w-px bg-gray-200" style={{ left: (depth - 1) * 14 + 16 }} />
        )}

        {/* 时间线圆点：合并节点显示学习状态，多选模式下显示 checkbox */}
        {isMerged && selectMode ? (
          <input type="checkbox" checked={selectedUnitIds.has(units[0].id)}
            onChange={(e) => { e.stopPropagation(); onToggleSelection(units[0].id); }}
            onClick={(e) => e.stopPropagation()}
            className="rounded border-gray-300 text-blue-500 focus:ring-blue-500 shrink-0 w-3 h-3 mr-2 z-10" />
        ) : (
          <div className={`shrink-0 ${isMerged ? 'w-1.5 h-1.5' : dot.size} rounded-full ${
            isMerged
              ? (units[0]?.summary ? 'bg-green-400' : 'bg-gray-300')
              : `${dot.color} ${dot.ring}`
          } mr-2 z-10`} />
        )}

        {/* 标题 */}
        <button
          onClick={() => {
            if (isMerged && !selectMode) onLoadUnit(units[0].id);
            else if (isContainer || hasChildren) onToggleCollapse(chapter.id);
            else if (units.length > 0 && !selectMode) onLoadUnit(units[0].id);
          }}
          className={`flex-1 flex items-center justify-between py-1.5 pr-2 text-left hover:bg-gray-50/80 transition-colors rounded ${fontClass} ${
            isMerged && currentUnitId === units[0]?.id ? 'text-blue-700' : ''
          } ${units.length === 0 && !isContainer && !hasChildren ? 'text-gray-400' : ''}`}
        >
          <span className="truncate text-gray-700">{chapter.title}</span>
          <div className="flex items-center gap-1.5 shrink-0 ml-1">
            {units.length > 0 && !isContainer && !isMerged && (
              <span className={`text-[9px] font-normal ${learnedCount === units.length ? 'text-green-500' : 'text-gray-400'}`}>
                {learnedCount}/{units.length}
              </span>
            )}
            {(isContainer || hasChildren) && (
              <span className={`text-[9px] text-gray-400 transition-transform ${isCollapsed ? '' : 'rotate-90'}`}>▶</span>
            )}
          </div>
        </button>
      </div>

      {/* 子章节 */}
      {!isCollapsed && hasChildren && chapter.children!.map((child, i) => (
        <ChapterTimelineNode
          key={child.id}
          chapter={child}
          depth={depth + 1}
          isLast={i === chapter.children!.length - 1}
          currentUnitId={currentUnitId}
          selectMode={selectMode}
          selectedUnitIds={selectedUnitIds}
          collapsedChapters={collapsedChapters}
          onToggleCollapse={onToggleCollapse}
          onLoadUnit={onLoadUnit}
          onToggleSelection={onToggleSelection}
        />
      ))}

      {/* 知识单元列表（叶子节点） */}
      {showUnits && (
        <div className="relative" style={{ paddingLeft: depth * 14 + 8 }}>
          {/* 竖线 */}
          <div className="absolute top-0 bottom-0 w-px bg-gray-200" style={{ left: depth * 14 + 16 }} />
          {units.map((unit, i) => {
            const isSelected = currentUnitId === unit.id;
            const isChecked = selectedUnitIds.has(unit.id);
            const isLastUnit = i === units.length - 1;
            return (
              <div key={unit.id}
                className={`relative flex items-center gap-1.5 pl-6 pr-2 py-1 cursor-pointer transition-colors ${
                  isSelected ? 'bg-blue-50/80' : 'hover:bg-gray-50/60'
                }`}
                onClick={() => onLoadUnit(unit.id)}>
                {/* 连接线 */}
                <div className={`absolute w-px bg-gray-200 ${isLastUnit ? 'h-2.5' : 'top-0 bottom-0'}`}
                  style={{ left: depth * 14 + 16 }} />
                {/* 圆点 */}
                <div className={`absolute w-1 h-1 rounded-full ${unit.summary ? 'bg-green-400' : 'bg-gray-300'} z-10`}
                  style={{ left: depth * 14 + 15 }} />
                {selectMode && (
                  <input type="checkbox" checked={isChecked}
                    onChange={(e) => { e.stopPropagation(); onToggleSelection(unit.id); }}
                    onClick={(e) => e.stopPropagation()}
                    className="rounded border-gray-300 text-blue-500 focus:ring-blue-500 shrink-0 w-3 h-3" />
                )}
                <span className={`text-[10px] truncate flex-1 ${isSelected ? 'text-blue-700 font-medium' : 'text-gray-500'}`}>
                  {unit.title}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function LearningSession() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [currentUnit, setCurrentUnit] = useState<KnowledgeUnit | null>(null);
  const [session, setSession] = useState<LearningRecord | null>(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [splitting, setSplitting] = useState(false);

  // 侧边栏
  const [collapsedChapters, setCollapsedChapters] = useState<Set<string>>(new Set());
  // 多选模式
  const [selectMode, setSelectMode] = useState(false);
  const [selectedUnitIds, setSelectedUnitIds] = useState<Set<string>>(new Set());

  // AI 学习状态
  const [aiLearning, setAiLearning] = useState(false);
  const aiLearningRef = useRef(false);
  const [aiProgress, setAiProgress] = useState<{ done: number; total: number; title: string; status?: string }>({ done: 0, total: 0, title: '' });
  const updateAiProgress = useCallback((next: { done: number; total: number; title: string; status?: string }) => {
    setAiProgress((prev) => (
      prev.done === next.done && prev.total === next.total && prev.title === next.title && prev.status === next.status
        ? prev
        : next
    ));
  }, []);
  const [stuckWarning, setStuckWarning] = useState(false);

  // 增量更新状态
  const [enriching, setEnriching] = useState(false);
  const [enrichFocus, setEnrichFocus] = useState<EnrichFocus>('examples');
  const [customInstruction, setCustomInstruction] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [expandedConcepts, setExpandedConcepts] = useState<Set<number>>(new Set());
  const [expandedKeyPoints, setExpandedKeyPoints] = useState<Set<number>>(new Set());

  // 撤销状态
  const [prevSnapshot, setPrevSnapshot] = useState<KnowledgeUnit | null>(null);
  const [showUndo, setShowUndo] = useState(false);
  const undoTimerRef = useRef<number | null>(null);

  const allUnits = chapters.flatMap((c) => c.knowledge_units || []);
  const activeUnits = selectedUnitIds.size > 0
    ? allUnits.filter((u) => selectedUnitIds.has(u.id))
    : allUnits;
  const activeIndex = activeUnits.findIndex((u) => u.id === currentUnit?.id);
  const progress = activeUnits.length > 0 ? Math.round(((activeIndex + 1) / activeUnits.length) * 100) : 0;

  // 构建章节树形结构
  const chapterTree = useMemo(() => {
    const sorted = [...chapters].sort((a, b) => a.order_index - b.order_index);
    const roots: ChapterTreeNode[] = [];
    const map = new Map<string, ChapterTreeNode>();
    for (const ch of sorted) {
      map.set(ch.id, { ...ch, children: [] });
    }
    const levelStack: ChapterTreeNode[] = [];
    for (const ch of sorted) {
      const node = map.get(ch.id)!;
      if (ch.parent_id && map.has(ch.parent_id)) {
        map.get(ch.parent_id)!.children!.push(node);
      } else if (ch.level > 0) {
        const parent = levelStack[ch.level - 1];
        if (parent) parent.children!.push(node);
        else roots.push(node);
      } else {
        roots.push(node);
      }
      levelStack.length = ch.level;
      levelStack[ch.level] = node;
    }
    const markContainers = (nodes: ChapterTreeNode[]) => {
      for (const node of nodes) {
        const children = node.children || [];
        node.is_container = children.length > 0;
        markContainers(children);
      }
    };
    markContainers(roots);
    return roots;
  }, [chapters]);

  useEffect(() => {
    if (!bookId) return;
    loadInitialChapters();
  }, [bookId]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      stopProgressPolling();
      if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    };
  }, []);

  const refreshChapters = async () => {
    const data = await getBookChapters(bookId!);
    setChapters(data);
    return data;
  };

  const loadInitialChapters = async () => {
    try {
      const data = await refreshChapters();
      const units = data.flatMap((c) => c.knowledge_units || []);
      if (units.length > 0 && !currentUnit) {
        loadUnit(units[0].id);
      }
    } catch (error) {
      console.error('加载章节失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadUnit = async (unitId: string) => {
    try {
      const unit = await getKnowledgeUnit(unitId);
      setCurrentUnit(unit);
      setExpandedConcepts(new Set());
      setShowUndo(false);
      if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
      try {
        const sessionData = await startLearningSession(unitId);
        setSession(sessionData);
      } catch { /* 会话创建失败不影响学习 */ }
      setNote('');
    } catch (error) {
      console.error('加载知识单元失败:', error);
    }
  };

  // ── 进度轮询 ──
  const progressTimeoutRef = useRef<number | null>(null);
  const lastProgressRef = useRef<{ time: number; done: number }>({ time: Date.now(), done: 0 });

  const stopProgressPolling = () => {
    if (progressTimeoutRef.current) {
      clearTimeout(progressTimeoutRef.current);
      progressTimeoutRef.current = null;
    }
  };

  const pollLearningProgress = async () => {
    if (!bookId || !aiLearningRef.current) return;
    try {
      const progress = await getAILearningProgress(bookId);
      if (!aiLearningRef.current) return;
      if (progress.status === 'not_started' && lastProgressRef.current.time > 0) {
        const elapsed = Date.now() - lastProgressRef.current.time;
        if (elapsed > 10000) {
          updateAiProgress({ done: 0, total: 0, title: '服务器可能已重启，学习进度已丢失。请重新开始学习。', status: 'error' });
          stopProgressPolling();
          setAiLearning(false);
          aiLearningRef.current = false;
          return;
        }
      }
      if (progress.current !== lastProgressRef.current.done) {
        lastProgressRef.current = { time: Date.now(), done: progress.current };
        setStuckWarning(false);
      }
      const stuckTime = Date.now() - lastProgressRef.current.time;
      if (progress.status === 'in_progress') {
        setStuckWarning((prev) => (stuckTime > 300000 ? true : prev));
        updateAiProgress({ done: progress.current, total: progress.total, title: progress.message, status: 'in_progress' });
        progressTimeoutRef.current = window.setTimeout(pollLearningProgress, 2000);
        return;
      }
      if (progress.status === 'completed') {
        updateAiProgress({ done: progress.current, total: progress.total, title: progress.message || 'AI 学习完成', status: 'completed' });
        stopProgressPolling();
        setAiLearning(false);
        aiLearningRef.current = false;
        await refreshChapters();
        if (currentUnit) {
          const updated = await getKnowledgeUnit(currentUnit.id);
          setCurrentUnit(updated);
        }
      }
      if (progress.status === 'error') {
        updateAiProgress({ done: progress.current, total: progress.total, title: progress.message, status: 'error' });
        stopProgressPolling();
        setAiLearning(false);
        aiLearningRef.current = false;
      }
    } catch (e) {
      console.warn('进度轮询失败:', e);
      if (aiLearningRef.current) {
        progressTimeoutRef.current = window.setTimeout(pollLearningProgress, 2000);
      }
    }
  };

  const startProgressPolling = () => {
    stopProgressPolling();
    lastProgressRef.current = { time: Date.now(), done: 0 };
    setStuckWarning(false);
    progressTimeoutRef.current = window.setTimeout(pollLearningProgress, 2000);
  };

  const handleCancelLearning = () => {
    if (confirm('确定要取消当前学习任务吗？已完成的部分会保留。')) {
      aiLearningRef.current = false;
      stopProgressPolling();
      setAiLearning(false);
      setStuckWarning(false);
    }
  };

  // ── AI 学习 ──
  const handleStartLearning = async () => {
    if (!bookId) return;
    aiLearningRef.current = true;
    setAiLearning(true);
    setAiProgress({ done: 0, total: activeUnits.length, title: '正在启动 AI 学习任务...', status: 'in_progress' });
    setStuckWarning(false);
    try {
      const result = await startLearning(bookId, selectedUnitIds.size > 0 ? Array.from(selectedUnitIds) : undefined);
      updateAiProgress({ done: 0, total: result.total_units, title: result.message, status: 'in_progress' });
      startProgressPolling();
    } catch (error: any) {
      console.error('AI 学习启动失败:', error);
      const message = error?.response?.data?.message || error?.response?.data?.detail || error?.message || '未知错误';
      setAiProgress((prev) => ({ ...prev, title: `启动失败: ${message}`, status: 'error' }));
      aiLearningRef.current = false;
      stopProgressPolling();
      setAiLearning(false);
    }
  };

  // ── 重新生成 ──
  const handleRelearn = async () => {
    if (!currentUnit) return;
    setRegenerating(true);
    try {
      const result = await relearnUnit(currentUnit.id);
      setCurrentUnit((prev) => prev ? { ...prev, summary: result.summary, key_points: result.key_points, concepts: result.concepts, difficulty_level: result.difficulty_level } : prev);
    } catch (error) {
      console.error('重新生成失败:', error);
      alert('重新生成失败，请重试');
    } finally {
      setRegenerating(false);
    }
  };

  // ── 增量更新 ──
  const handleEnrich = async (focus: EnrichFocus) => {
    if (!currentUnit) return;
    // 保存快照用于撤销
    setPrevSnapshot({ ...currentUnit });
    setEnriching(true);
    try {
      const result = await enrichUnit(currentUnit.id, { focus, instruction: customInstruction || undefined });
      setCurrentUnit((prev) => prev ? {
        ...prev,
        summary: result.summary,
        explanation: result.explanation || prev.explanation,
        key_points: result.key_points,
        concepts: result.concepts,
        difficulty_level: result.difficulty_level,
      } : prev);
      setCustomInstruction('');
      // 显示撤销按钮，30秒后隐藏
      setShowUndo(true);
      if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
      undoTimerRef.current = window.setTimeout(() => setShowUndo(false), 30000);
    } catch (error) {
      console.error('增量更新失败:', error);
      alert('增量更新失败，请重试');
      setPrevSnapshot(null);
    } finally {
      setEnriching(false);
    }
  };

  // ── 撤销增量更新 ──
  const handleUndo = async () => {
    if (!prevSnapshot || !currentUnit) return;
    try {
      await restoreUnit(currentUnit.id, {
        summary: prevSnapshot.summary || '',
        explanation: prevSnapshot.explanation || '',
        key_points: prevSnapshot.key_points || [],
        concepts: (prevSnapshot.concepts || []).map((c) =>
          typeof c === 'string' ? { name: c } : c
        ),
        difficulty_level: prevSnapshot.difficulty_level || 3,
        importance_score: prevSnapshot.importance_score || 0.5,
      });
      setCurrentUnit(prevSnapshot);
      setPrevSnapshot(null);
      setShowUndo(false);
    } catch (error) {
      console.error('撤销失败:', error);
      alert('撤销失败，请重试');
    }
  };

  // ── 侧边栏操作 ──
  const toggleChapterCollapse = (chapterId: string) => {
    setCollapsedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(chapterId)) next.delete(chapterId);
      else next.add(chapterId);
      return next;
    });
  };

  const toggleUnitSelection = (unitId: string) => {
    setSelectedUnitIds((prev) => {
      const next = new Set(prev);
      if (next.has(unitId)) next.delete(unitId);
      else next.add(unitId);
      return next;
    });
  };

  const handleSaveNote = async () => {
    if (currentUnit && note.trim()) {
      try { await saveNote(currentUnit.id, note); } catch {}
    }
  };

  const handleMark = async (mark: 'important' | 'confusing') => {
    if (currentUnit) {
      try { await markUnit(currentUnit.id, mark); } catch {}
    }
  };

  if (loading) return <Loading />;

  // 无内容时显示拆分引导
  if (allUnits.length === 0) {
    return (
      <div className="max-w-2xl mx-auto animate-fade-in">
        {splitting ? (
          <SplitProgress key={bookId} bookId={bookId!}
            onComplete={async () => { setSplitting(false); await loadInitialChapters(); }}
            onError={(msg) => { setSplitting(false); alert(msg); }} />
        ) : (
          <div className="text-center py-20">
            <div className="text-6xl mb-5 animate-float">📭</div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">没有可学习的内容</h2>
            <p className="text-sm text-gray-400 mb-8">请先对书籍进行知识拆分，系统将自动生成知识单元</p>
            <div className="flex gap-3 justify-center">
              <button onClick={() => setSplitting(true)}
                className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-amber-500/25 transition-all">
                ⚡ 开始知识拆分
              </button>
              <button onClick={() => navigate(`/books/${bookId}`)}
                className="px-5 py-2.5 bg-gray-100 text-gray-600 rounded-xl text-sm font-medium hover:bg-gray-200 transition-all">
                ← 返回详情
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (!currentUnit) return <div className="text-center py-12 text-gray-500">加载中...</div>;

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      {/* 顶部控制栏 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-800">学习模式</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {selectMode
              ? `已选 ${selectedUnitIds.size} 个单元`
              : `知识单元 ${activeIndex + 1} / ${activeUnits.length}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setSelectMode(!selectMode)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${selectMode ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {selectMode ? '✓ 确认选择' : '📋 选单元'}
          </button>
          <button onClick={handleStartLearning} disabled={aiLearning}
            className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all disabled:opacity-50">
            🤖 {selectedUnitIds.size > 0 ? `AI 学习选中 (${selectedUnitIds.size})` : 'AI 学习全部'}
          </button>
          <button onClick={() => navigate(`/books/${bookId}`)}
            className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-all">
            退出学习
          </button>
        </div>
      </div>

      {/* AI 学习进度 */}
      {(aiLearning || aiProgress.total > 0) && (
        <Card className={`mb-4 border ${
          aiProgress.status === 'error' ? 'bg-red-50 border-red-100'
            : stuckWarning ? 'bg-amber-50 border-amber-100'
            : 'bg-blue-50 border-blue-100'
        }`}>
          <div className="flex items-center gap-3">
            {aiLearning ? (
              <div className={`w-5 h-5 border-2 border-t-transparent rounded-full animate-spin ${stuckWarning ? 'border-amber-500' : 'border-blue-500'}`} />
            ) : aiProgress.status === 'error' ? (
              <span className="text-red-500 text-lg">✗</span>
            ) : (
              <span className="text-blue-500 text-lg">✓</span>
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <p className={`text-sm font-medium ${aiProgress.status === 'error' ? 'text-red-700' : stuckWarning ? 'text-amber-700' : 'text-blue-700'}`}>
                  {aiLearning ? stuckWarning ? '进度似乎卡住了...' : 'AI 正在后台学习...' : aiProgress.status === 'error' ? '学习出错' : 'AI 学习完成'}
                </p>
                <span className={`text-xs font-semibold ${aiProgress.status === 'error' ? 'text-red-600' : 'text-blue-600'}`}>
                  {Math.floor(aiProgress.done)}/{aiProgress.total}
                </span>
              </div>
              <div className={`w-full rounded-full h-2 mb-1 ${aiProgress.status === 'error' ? 'bg-red-100' : 'bg-blue-100'}`}>
                <div className={`h-2 rounded-full transition-all duration-300 ${aiProgress.status === 'error' ? 'bg-red-500' : stuckWarning ? 'bg-amber-500' : 'bg-gradient-to-r from-blue-500 to-blue-600'}`}
                  style={{ width: `${aiProgress.total > 0 ? (aiProgress.done / aiProgress.total) * 100 : 0}%` }} />
              </div>
              {aiProgress.title && <p className={`text-xs truncate ${aiProgress.status === 'error' ? 'text-red-500' : 'text-blue-500'}`}>{aiProgress.title}</p>}
              {aiLearning && !stuckWarning && <p className="text-xs text-blue-500 mt-1">你可以继续浏览当前内容，完成后系统会自动刷新 AI 分析结果。</p>}
              {stuckWarning && aiLearning && <p className="text-xs text-amber-600 mt-1">已超过 5 分钟没有进度更新，你可以继续等待或取消重试。</p>}
            </div>
            {aiLearning && (
              <button onClick={handleCancelLearning}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white rounded-lg hover:bg-gray-50 border border-gray-200 transition-colors shrink-0">
                取消
              </button>
            )}
          </div>
        </Card>
      )}

      {/* 左右分栏 */}
      <div className="flex gap-4">
        {/* ── 左侧：章节浏览树 ── */}
        <div className="w-60 shrink-0">
          <div className="sticky top-4 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            {/* 多选模式下的全选/清空 */}
            {selectMode && (
              <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50">
                <span className="text-[10px] text-gray-400 uppercase tracking-wider">选择单元</span>
                <div className="flex gap-2">
                  <button onClick={() => setSelectedUnitIds(new Set(allUnits.map((u) => u.id)))}
                    className="text-[10px] text-blue-500 hover:text-blue-600">全选</button>
                  <button onClick={() => setSelectedUnitIds(new Set())}
                    className="text-[10px] text-gray-400 hover:text-gray-600">清空</button>
                </div>
              </div>
            )}
            <div className="max-h-[calc(100vh-200px)] overflow-y-auto py-1">
              {chapterTree.map((chapter, i) => (
                <ChapterTimelineNode
                  key={chapter.id}
                  chapter={chapter}
                  depth={0}
                  isLast={i === chapterTree.length - 1}
                  currentUnitId={currentUnit?.id}
                  selectMode={selectMode}
                  selectedUnitIds={selectedUnitIds}
                  collapsedChapters={collapsedChapters}
                  onToggleCollapse={toggleChapterCollapse}
                  onLoadUnit={(id) => { if (!selectMode) loadUnit(id); }}
                  onToggleSelection={toggleUnitSelection}
                />
              ))}
            </div>
          </div>
        </div>

        {/* ── 右侧：内容展示区 ── */}
        <div className="flex-1 min-w-0">
          {/* 单元内容 */}
          <Card className="mb-4 animate-scale-in" gradient>
            <div className="flex items-start gap-3 mb-4">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-md shadow-blue-500/20">
                {activeIndex + 1}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-lg font-bold text-gray-800">{currentUnit.title}</h2>
                {currentUnit.summary && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{currentUnit.summary}</p>}
              </div>
              {currentUnit.summary && (
                <button onClick={handleRelearn} disabled={regenerating}
                  className="text-xs text-purple-500 hover:text-purple-600 disabled:opacity-40 shrink-0" title="重新生成 AI 分析">
                  {regenerating ? <span className="w-3 h-3 border-2 border-purple-500 border-t-transparent rounded-full animate-spin inline-block" /> : '🔄'}
                </button>
              )}
            </div>

            {/* AI 讲解 */}
            {currentUnit.explanation && (
              <div className="mb-4 p-4 bg-blue-50/70 border border-blue-100 rounded-xl">
                <p className="text-xs font-semibold text-blue-600 mb-2 flex items-center gap-1.5">
                  <span>📖</span> AI 讲解
                </p>
                <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{currentUnit.explanation}</div>
              </div>
            )}

            {/* 原文 */}
            <div className="prose prose-sm max-w-none text-gray-600 leading-relaxed">
              {currentUnit.content?.split('\n').map((paragraph, i) => (
                paragraph.trim() && <p key={i} className="mb-2 text-sm leading-6">{paragraph}</p>
              ))}
            </div>

            {/* 要点 */}
            {currentUnit.key_points && currentUnit.key_points.length > 0 && (
              <div className="mt-5 pt-4 border-t border-gray-100">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">🔑 要点</p>
                <div className="space-y-2">
                  {currentUnit.key_points.map((point, i) => {
                    const isObj = typeof point !== 'string';
                    const kp = isObj ? point as KeyPoint : null;
                    const isExpanded = expandedKeyPoints.has(i);
                    const hasDetail = isObj && (kp!.explanation || (kp!.examples && kp!.examples.length > 0));
                    return (
                      <div key={i} className="rounded-lg border border-gray-100 bg-gray-50/50 overflow-hidden">
                        <div
                          className={`flex items-start gap-2 px-3 py-2 ${hasDetail ? 'cursor-pointer hover:bg-blue-50/50' : ''}`}
                          onClick={() => {
                            if (!hasDetail) return;
                            setExpandedKeyPoints(prev => {
                              const next = new Set(prev);
                              next.has(i) ? next.delete(i) : next.add(i);
                              return next;
                            });
                          }}
                        >
                          <span className="w-5 h-5 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">{i + 1}</span>
                          <p className="text-sm text-gray-700 flex-1">{isObj ? kp!.title : point}</p>
                          {hasDetail && (
                            <span className="text-gray-400 text-xs shrink-0 mt-0.5">{isExpanded ? '▲' : '▼'}</span>
                          )}
                        </div>
                        {isExpanded && hasDetail && (
                          <div className="px-3 pb-3 pl-10 space-y-2">
                            {kp!.explanation && (
                              <p className="text-sm text-gray-600 leading-relaxed">{kp!.explanation}</p>
                            )}
                            {kp!.examples && kp!.examples.length > 0 && (
                              <div>
                                <p className="text-xs text-gray-400 mb-1">示例：</p>
                                <ul className="list-disc list-inside space-y-0.5">
                                  {kp!.examples.map((ex, j) => (
                                    <li key={j} className="text-xs text-gray-500">{ex}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 概念 */}
            {currentUnit.concepts && currentUnit.concepts.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">💡 核心概念</p>
                <div className="flex flex-wrap gap-2">
                  {currentUnit.concepts.map((concept, i) => {
                    const isObj = typeof concept !== 'string';
                    const isExpanded = expandedConcepts.has(i);
                    return (
                      <ConceptTag key={i} concept={concept} index={i} isExpanded={isExpanded}
                        onToggle={() => {
                          if (!isObj) return;
                          setExpandedConcepts((prev) => { const next = new Set(prev); if (next.has(i)) next.delete(i); else next.add(i); return next; });
                        }}
                        onClose={() => setExpandedConcepts((prev) => { const next = new Set(prev); next.delete(i); return next; })} />
                    );
                  })}
                </div>
              </div>
            )}
          </Card>

          {/* 增量更新面板 */}
          {currentUnit.summary && (
            <Card className="mb-4" hover={false}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <span>✨</span> 增量更新
                </h3>
                {showUndo && (
                  <button onClick={handleUndo}
                    className="text-xs text-amber-600 hover:text-amber-700 bg-amber-50 px-2.5 py-1 rounded-lg border border-amber-100 transition-colors">
                    ↩ 撤销上次更新
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-2 mb-3">
                {ENRICH_DIRECTIONS.map((dir) => (
                  <button key={dir.key} onClick={() => handleEnrich(dir.key)} disabled={enriching}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all disabled:opacity-40 ${
                      enrichFocus === dir.key
                        ? 'bg-emerald-50 text-emerald-600 border-emerald-200'
                        : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50 hover:border-gray-300'
                    }`}>
                    {enriching && enrichFocus === dir.key ? (
                      <span className="w-3 h-3 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <span>{dir.icon}</span>
                    )}
                    {dir.label}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <input type="text" value={customInstruction} onChange={(e) => setCustomInstruction(e.target.value)}
                  placeholder="自定义补充指令（可选）..."
                  className="flex-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-blue-300 focus:ring-1 focus:ring-blue-100 placeholder:text-gray-300" />
                <button onClick={() => handleEnrich(enrichFocus)} disabled={enriching || !customInstruction.trim()}
                  className="px-3 py-1.5 text-xs font-medium text-emerald-600 bg-emerald-50 rounded-lg border border-emerald-200 hover:bg-emerald-100 transition-colors disabled:opacity-40">
                  执行
                </button>
              </div>
            </Card>
          )}

          {/* 笔记和标记 */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <Card hover={false}>
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>📝</span> 学习笔记</h3>
              <textarea value={note} onChange={(e) => setNote(e.target.value)}
                placeholder="记录你的理解和思考..."
                className="w-full h-24 p-3 border border-gray-100 rounded-xl resize-none text-sm text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
              <button onClick={handleSaveNote}
                className="mt-2 px-4 py-1.5 bg-gray-700 text-white rounded-lg text-xs font-medium hover:bg-gray-600 transition-colors">
                保存笔记
              </button>
            </Card>
            <Card hover={false}>
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🏷️</span> 快速标记</h3>
              <div className="space-y-2">
                <button onClick={() => handleMark('important')}
                  className="w-full px-4 py-2.5 bg-amber-50 text-amber-700 rounded-xl hover:bg-amber-100 text-left text-sm font-medium transition-colors flex items-center gap-2 border border-amber-100">
                  ⭐ 标记为重要
                </button>
                <button onClick={() => handleMark('confusing')}
                  className="w-full px-4 py-2.5 bg-red-50 text-red-600 rounded-xl hover:bg-red-100 text-left text-sm font-medium transition-colors flex items-center gap-2 border border-red-100">
                  ❓ 标记为不懂
                </button>
              </div>
            </Card>
          </div>

          {/* 底部导航 */}
          <div className="flex justify-between items-center">
            <button onClick={() => { if (session) endLearningSession(session.id).catch(() => {}); const prevIdx = activeIndex - 1; if (prevIdx >= 0) loadUnit(activeUnits[prevIdx].id); }}
              disabled={activeIndex <= 0}
              className="px-4 py-2 text-gray-500 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors disabled:opacity-30">
              ← 上一个
            </button>
            <div className="flex items-center gap-3">
              <div className="w-32"><ProgressBar value={activeIndex + 1} max={activeUnits.length} size="sm" color="blue" /></div>
              <span className="text-xs text-gray-400">{activeIndex + 1}/{activeUnits.length}</span>
            </div>
            <button onClick={() => { if (session) endLearningSession(session.id).catch(() => {}); const nextIdx = activeIndex + 1; if (nextIdx < activeUnits.length) loadUnit(activeUnits[nextIdx].id); else navigate(`/books/${bookId}`); }}
              className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all">
              {activeIndex + 1 < activeUnits.length ? '下一个单元 →' : '✓ 完成学习'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
