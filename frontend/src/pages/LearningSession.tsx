import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import ProgressBar from '../components/ProgressBar';
import Icon from '../components/ui/Icon';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import { ConfirmDialog } from '../components/ui/Modal';
import { useToast } from '../components/ui/Toast';
import ChapterTimelineNode from '../components/learning/ChapterTimeline';
import ConceptTag from '../components/learning/ConceptTag';
import { getBookChapters } from '../api/books';
import SplitProgress from '../components/SplitProgress';
import { getKnowledgeUnit, startLearningSession, endLearningSession, saveNote, markUnit, startLearning, relearnUnit, enrichUnit, restoreUnit, getAILearningProgress } from '../api/learning';
import type { Chapter, KnowledgeUnit, LearningRecord, KeyPoint } from '../types';

const ENRICH_DIRECTIONS = [
  { key: 'examples', label: '补充例子', icon: 'sparkles' },
  { key: 'explanations', label: '深入解释', icon: 'bookOpen' },
  { key: 'connections', label: '关联拓展', icon: 'refresh' },
  { key: 'applications', label: '实践应用', icon: 'bolt' },
  { key: 'mistakes', label: '易错点', icon: 'alert' },
  { key: 'simplify', label: '简化总结', icon: 'check' },
] as const;

type EnrichFocus = (typeof ENRICH_DIRECTIONS)[number]['key'];
type ChapterTreeNode = Omit<Chapter, 'children'> & { children?: ChapterTreeNode[] };

export default function LearningSession() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [currentUnit, setCurrentUnit] = useState<KnowledgeUnit | null>(null);
  const [session, setSession] = useState<LearningRecord | null>(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [splitting, setSplitting] = useState(false);
  const [collapsedChapters, setCollapsedChapters] = useState<Set<string>>(new Set());
  const [selectMode, setSelectMode] = useState(false);
  const [selectedUnitIds, setSelectedUnitIds] = useState<Set<string>>(new Set());
  const [aiLearning, setAiLearning] = useState(false);
  const aiLearningRef = useRef(false);
  const [aiProgress, setAiProgress] = useState({ done: 0, total: 0, title: '' });
  const updateAiProgress = useCallback((n: typeof aiProgress) => setAiProgress(p => p.done === n.done && p.total === n.total && p.title === n.title ? p : n), []);
  const [stuckWarning, setStuckWarning] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [enrichFocus, setEnrichFocus] = useState<EnrichFocus>('examples');
  const [customInstruction, setCustomInstruction] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [expandedConcepts, setExpandedConcepts] = useState<Set<number>>(new Set());
  const [expandedKeyPoints, setExpandedKeyPoints] = useState<Set<number>>(new Set());
  const [prevSnapshot, setPrevSnapshot] = useState<KnowledgeUnit | null>(null);
  const [showUndo, setShowUndo] = useState(false);
  const undoTimerRef = useRef<number | null>(null);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const allUnits = chapters.flatMap(c => c.knowledge_units || []);
  const activeUnits = selectedUnitIds.size > 0 ? allUnits.filter(u => selectedUnitIds.has(u.id)) : allUnits;
  const activeIndex = activeUnits.findIndex(u => u.id === currentUnit?.id);  const chapterTree = useMemo(() => {
    const sorted = [...chapters].sort((a, b) => a.order_index - b.order_index);
    const roots: ChapterTreeNode[] = [];
    const map = new Map<string, ChapterTreeNode>();
    for (const ch of sorted) map.set(ch.id, { ...ch, children: [] });
    const stack: ChapterTreeNode[] = [];
    for (const ch of sorted) {
      const node = map.get(ch.id)!;
      if (ch.parent_id && map.has(ch.parent_id)) map.get(ch.parent_id)!.children!.push(node);
      else if (ch.level > 0) { const p = stack[ch.level - 1]; if (p) p.children!.push(node); else roots.push(node); }
      else roots.push(node);
      stack.length = ch.level; stack[ch.level] = node;
    }
    (function mark(n: ChapterTreeNode[]) { for (const node of n) { node.is_container = (node.children || []).length > 0; mark(node.children || []); } })(roots);
    return roots;
  }, [chapters]);
  useEffect(() => { if (bookId) loadInitialChapters(); }, [bookId]);
  useEffect(() => () => { stopProgressPolling(); if (undoTimerRef.current) clearTimeout(undoTimerRef.current); }, []);
  const refreshChapters = async () => { const d = await getBookChapters(bookId!); setChapters(d); return d; };
  const loadInitialChapters = async () => { try { const d = await refreshChapters(); const u = d.flatMap(c => c.knowledge_units || []); if (u.length && !currentUnit) loadUnit(u[0].id); } catch (e) { console.error(e); } finally { setLoading(false); } };
  const loadUnit = async (id: string) => { try { const u = await getKnowledgeUnit(id); setCurrentUnit(u); setExpandedConcepts(new Set()); setShowUndo(false); if (undoTimerRef.current) clearTimeout(undoTimerRef.current); try { setSession(await startLearningSession(id)); } catch { } setNote(''); } catch (e) { console.error(e); } };
  const progressTimeoutRef = useRef<number | null>(null);
  const lastProgressRef = useRef({ time: Date.now(), done: 0 });
  const stopProgressPolling = () => { if (progressTimeoutRef.current) { clearTimeout(progressTimeoutRef.current); progressTimeoutRef.current = null; } };
  const poll = async () => {
    if (!bookId || !aiLearningRef.current) return;
    try {
      const p = await getAILearningProgress(bookId); if (!aiLearningRef.current) return;
      if (p.status === 'not_started' && lastProgressRef.current.time > 0 && Date.now() - lastProgressRef.current.time > 10000) { updateAiProgress({ done: 0, total: 0, title: '服务器可能已重启，学习进度已丢失。请重新开始学习。' }); stopProgressPolling(); setAiLearning(false); aiLearningRef.current = false; return; }
      if (p.current !== lastProgressRef.current.done) { lastProgressRef.current = { time: Date.now(), done: p.current }; setStuckWarning(false); }
      const stuck = Date.now() - lastProgressRef.current.time;
      if (p.status === 'in_progress') { setStuckWarning(s => stuck > 300000 ? true : s); updateAiProgress({ done: p.current, total: p.total, title: p.message }); progressTimeoutRef.current = window.setTimeout(poll, 2000); return; }
      if (p.status === 'completed') { updateAiProgress({ done: p.current, total: p.total, title: p.message || 'AI 学习完成' }); stopProgressPolling(); setAiLearning(false); aiLearningRef.current = false; await refreshChapters(); if (currentUnit) setCurrentUnit(await getKnowledgeUnit(currentUnit.id)); }
      if (p.status === 'error') { updateAiProgress({ done: p.current, total: p.total, title: p.message }); stopProgressPolling(); setAiLearning(false); aiLearningRef.current = false; }
    } catch { if (aiLearningRef.current) progressTimeoutRef.current = window.setTimeout(poll, 2000); }
  };
  const startPolling = () => { stopProgressPolling(); lastProgressRef.current = { time: Date.now(), done: 0 }; setStuckWarning(false); progressTimeoutRef.current = window.setTimeout(poll, 2000); };
  const handleCancelLearning = () => setShowCancelConfirm(true);
  const confirmCancel = () => { aiLearningRef.current = false; stopProgressPolling(); setAiLearning(false); setStuckWarning(false); setShowCancelConfirm(false); };
  const handleStartLearning = async () => { if (!bookId) return; aiLearningRef.current = true; setAiLearning(true); setAiProgress({ done: 0, total: activeUnits.length, title: '正在启动 AI 学习任务...' }); setStuckWarning(false); try { const r = await startLearning(bookId, selectedUnitIds.size > 0 ? Array.from(selectedUnitIds) : undefined); updateAiProgress({ done: 0, total: r.total_units, title: r.message }); startPolling(); } catch (e: any) { setAiProgress(p => ({ ...p, title: `启动失败: ${e?.response?.data?.message || e?.response?.data?.detail || e?.message || '未知错误'}` })); aiLearningRef.current = false; stopProgressPolling(); setAiLearning(false); } };
  const handleRelearn = async () => { if (!currentUnit) return; setRegenerating(true); try { const r = await relearnUnit(currentUnit.id); setCurrentUnit(p => p ? { ...p, summary: r.summary, key_points: r.key_points, concepts: r.concepts, difficulty_level: r.difficulty_level } : p); toast('已重新生成 AI 分析', 'success'); } catch { toast('重新生成失败，请重试', 'error'); } finally { setRegenerating(false); } };
  const handleEnrich = async (f: EnrichFocus) => { if (!currentUnit) return; setPrevSnapshot({ ...currentUnit }); setEnriching(true); try { const r = await enrichUnit(currentUnit.id, { focus: f, instruction: customInstruction || undefined }); setCurrentUnit(p => p ? { ...p, summary: r.summary, explanation: r.explanation || p.explanation, key_points: r.key_points, concepts: r.concepts, difficulty_level: r.difficulty_level } : p); setCustomInstruction(''); setShowUndo(true); if (undoTimerRef.current) clearTimeout(undoTimerRef.current); undoTimerRef.current = window.setTimeout(() => setShowUndo(false), 30000); toast('已补充内容', 'success'); } catch { toast('增量更新失败，请重试', 'error'); setPrevSnapshot(null); } finally { setEnriching(false); } };
  const handleUndo = async () => { if (!prevSnapshot || !currentUnit) return; try { await restoreUnit(currentUnit.id, { summary: prevSnapshot.summary || '', explanation: prevSnapshot.explanation || '', key_points: prevSnapshot.key_points || [], concepts: (prevSnapshot.concepts || []).map(c => typeof c === 'string' ? { name: c } : c), difficulty_level: prevSnapshot.difficulty_level || 3, importance_score: prevSnapshot.importance_score || 0.5 }); setCurrentUnit(prevSnapshot); setPrevSnapshot(null); setShowUndo(false); toast('已撤销上次更新', 'success'); } catch { toast('撤销失败，请重试', 'error'); } };
  const toggleChapterCollapse = (id: string) => setCollapsedChapters(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleUnitSelection = (id: string) => setSelectedUnitIds(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const handleSaveNote = async () => { if (currentUnit && note.trim()) { try { await saveNote(currentUnit.id, note); toast('笔记已保存', 'success'); } catch { toast('保存失败', 'error'); } } };
  const handleMark = async (m: 'important' | 'confusing') => { if (currentUnit) { try { await markUnit(currentUnit.id, m); toast(m === 'important' ? '已标记为重要' : '已标记为不懂', 'success'); } catch { toast('标记失败', 'error'); } } };  if (loading) return <div className="max-w-6xl mx-auto"><div className="h-8 w-48 bg-gray-100 rounded-lg animate-pulse mb-4" /><div className="flex gap-4"><div className="w-60 shrink-0 h-96 bg-gray-100 rounded-xl animate-pulse" /><div className="flex-1 space-y-4"><div className="h-64 bg-gray-100 rounded-2xl animate-pulse" /><div className="h-32 bg-gray-100 rounded-2xl animate-pulse" /></div></div></div>;
  if (allUnits.length === 0) return <div className="max-w-2xl mx-auto animate-fade-in">{splitting ? <SplitProgress key={bookId} bookId={bookId!} onComplete={async () => { setSplitting(false); await loadInitialChapters(); }} onError={m => { setSplitting(false); toast(m, 'error'); }} /> : <Card hover={false}><EmptyState icon="documentText" title="没有可学习的内容" description="请先对书籍进行知识拆分，系统将自动生成知识单元" action={<div className="flex gap-3 justify-center"><Button icon="bolt" onClick={() => setSplitting(true)}>开始知识拆分</Button><Button variant="secondary" onClick={() => navigate(`/books/${bookId}`)}>返回详情</Button></div>} /></Card>}</div>;
  if (!currentUnit) return <div className="text-center py-12 text-gray-500">加载中...</div>;
  return (<div className="max-w-6xl mx-auto animate-fade-in">
    <div className="flex flex-wrap items-center justify-between gap-3 mb-4"><div><h1 className="text-xl font-bold text-gray-800">学习模式</h1><p className="text-xs text-gray-400 mt-0.5">{selectMode ? `已选 ${selectedUnitIds.size} 个单元` : `知识单元 ${activeIndex + 1} / ${activeUnits.length}`}</p></div><div className="flex items-center gap-2"><Button variant={selectMode ? 'primary' : 'secondary'} size="sm" onClick={() => setSelectMode(!selectMode)}>{selectMode ? '✓ 确认选择' : '选单元'}</Button><Button icon="sparkles" onClick={handleStartLearning} disabled={aiLearning}>{selectedUnitIds.size > 0 ? `AI 学习选中 (${selectedUnitIds.size})` : 'AI 学习全部'}</Button><Button variant="ghost" size="sm" onClick={() => navigate(`/books/${bookId}`)}>退出学习</Button></div></div>
    {(aiLearning || aiProgress.total > 0) && <Card hover={false} className={`mb-4 border ${aiProgress.title?.includes('失败') || aiProgress.title?.includes('出错') ? 'bg-red-50 border-red-100' : stuckWarning ? 'bg-amber-50 border-amber-100' : 'bg-blue-50 border-blue-100'}`}><div className="flex items-center gap-3">{aiLearning ? <div className={`w-5 h-5 border-2 border-t-transparent rounded-full animate-spin ${stuckWarning ? 'border-amber-500' : 'border-blue-500'}`} /> : aiProgress.title?.includes('失败') ? <Icon name="alert" className="w-5 h-5 text-red-500" /> : <Icon name="checkCircle" className="w-5 h-5 text-blue-500" />}<div className="flex-1 min-w-0"><div className="flex items-center justify-between mb-1"><p className={`text-sm font-medium ${aiProgress.title?.includes('失败') ? 'text-red-700' : stuckWarning ? 'text-amber-700' : 'text-blue-700'}`}>{aiLearning ? stuckWarning ? '进度似乎卡住了...' : 'AI 正在后台学习...' : aiProgress.title?.includes('失败') ? '学习出错' : 'AI 学习完成'}</p><span className="text-xs font-semibold text-blue-600">{Math.floor(aiProgress.done)}/{aiProgress.total}</span></div><div className="w-full rounded-full h-2 mb-1 bg-blue-100"><div className={`h-2 rounded-full transition-all duration-300 ${stuckWarning ? 'bg-amber-500' : 'bg-gradient-to-r from-blue-500 to-blue-600'}`} style={{ width: `${aiProgress.total > 0 ? (aiProgress.done / aiProgress.total) * 100 : 0}%` }} /></div>{aiProgress.title && <p className="text-xs truncate text-blue-500">{aiProgress.title}</p>}{aiLearning && !stuckWarning && <p className="text-xs text-blue-500 mt-1">你可以继续浏览当前内容，完成后系统会自动刷新 AI 分析结果。</p>}{stuckWarning && aiLearning && <p className="text-xs text-amber-600 mt-1">已超过 5 分钟没有进度更新，你可以继续等待或取消重试。</p>}</div>{aiLearning && <Button variant="secondary" size="sm" onClick={handleCancelLearning}>取消</Button>}</div></Card>}
    <div className="flex gap-4"><div className="w-60 shrink-0"><div className="sticky top-4 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">{selectMode && <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50"><span className="text-[10px] text-gray-400 uppercase tracking-wider">选择单元</span><div className="flex gap-2"><button onClick={() => setSelectedUnitIds(new Set(allUnits.map(u => u.id)))} className="text-[10px] text-blue-500 hover:text-blue-600">全选</button><button onClick={() => setSelectedUnitIds(new Set())} className="text-[10px] text-gray-400 hover:text-gray-600">清空</button></div></div>}<div className="max-h-[calc(100vh-200px)] overflow-y-auto py-1">{chapterTree.map((c, i) => <ChapterTimelineNode key={c.id} chapter={c} depth={0} isLast={i === chapterTree.length - 1} currentUnitId={currentUnit?.id} selectMode={selectMode} selectedUnitIds={selectedUnitIds} collapsedChapters={collapsedChapters} onToggleCollapse={toggleChapterCollapse} onLoadUnit={id => { if (!selectMode) loadUnit(id); }} onToggleSelection={toggleUnitSelection} />)}</div></div></div>    <div className="flex-1 min-w-0"><Card hover={false} className="mb-4 animate-scale-in" gradient><div className="flex items-start gap-3 mb-4"><div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-md shadow-blue-500/20">{activeIndex + 1}</div><div className="flex-1 min-w-0"><h2 className="text-lg font-bold text-gray-800">{currentUnit.title}</h2>{currentUnit.summary && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{currentUnit.summary}</p>}</div>{currentUnit.summary && <Button variant="ghost" size="sm" icon="refresh" loading={regenerating} onClick={handleRelearn} title="重新生成 AI 分析" />}</div>
    {currentUnit.explanation && <div className="mb-4 p-4 bg-blue-50/70 border border-blue-100 rounded-xl"><p className="text-xs font-semibold text-blue-600 mb-2 flex items-center gap-1.5"><Icon name="bookOpen" className="w-3.5 h-3.5" /> AI 讲解</p><div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{currentUnit.explanation}</div></div>}
    <div className="prose prose-sm max-w-none text-gray-600 leading-relaxed">{currentUnit.content?.split('\n').map((para, i) => para.trim() && <p key={i} className="mb-2 text-sm leading-6">{para}</p>)}</div>
    {currentUnit.key_points && currentUnit.key_points.length > 0 && <div className="mt-5 pt-4 border-t border-gray-100"><p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5"><Icon name="check" className="w-3.5 h-3.5" /> 要点</p><div className="space-y-2">{currentUnit.key_points.map((pt, i) => { const isObj = typeof pt !== 'string'; const kp = isObj ? pt as KeyPoint : null; const ex = expandedKeyPoints.has(i); const det = isObj && (kp!.explanation || (kp!.examples && kp!.examples.length > 0)); return <div key={i} className="rounded-lg border border-gray-100 bg-gray-50/50 overflow-hidden"><div className={`flex items-start gap-2 px-3 py-2 ${det ? 'cursor-pointer hover:bg-blue-50/50' : ''}`} onClick={() => { if (!det) return; setExpandedKeyPoints(p => { const n = new Set(p); n.has(i) ? n.delete(i) : n.add(i); return n; }); }}><span className="w-5 h-5 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">{i + 1}</span><p className="text-sm text-gray-700 flex-1">{isObj ? kp!.title : pt}</p>{det && <span className="text-gray-400 text-xs shrink-0 mt-0.5">{ex ? '▲' : '▼'}</span>}</div>{ex && det && <div className="px-3 pb-3 pl-10 space-y-2">{kp!.explanation && <p className="text-sm text-gray-600 leading-relaxed">{kp!.explanation}</p>}{kp!.examples && kp!.examples.length > 0 && <div><p className="text-xs text-gray-400 mb-1">示例：</p><ul className="list-disc list-inside space-y-0.5">{kp!.examples.map((e, j) => <li key={j} className="text-xs text-gray-500">{e}</li>)}</ul></div>}</div>}</div>; })}</div></div>}
    {currentUnit.concepts && currentUnit.concepts.length > 0 && <div className="mt-4 space-y-2"><p className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5"><Icon name="sparkles" className="w-3.5 h-3.5" /> 核心概念</p><div className="flex flex-wrap gap-2">{currentUnit.concepts.map((c, i) => { const isObj = typeof c !== 'string'; const ex = expandedConcepts.has(i); return <ConceptTag key={i} concept={c} index={i} isExpanded={ex} onToggle={() => { if (!isObj) return; setExpandedConcepts(p => { const n = new Set(p); n.has(i) ? n.delete(i) : n.add(i); return n; }); }} onClose={() => setExpandedConcepts(p => { const n = new Set(p); n.delete(i); return n; })} />; })}</div></div>}
    </Card>
    {currentUnit.summary && <Card hover={false} className="mb-4"><div className="flex items-center justify-between mb-3"><h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2"><Icon name="sparkles" className="w-4 h-4 text-emerald-500" /> 增量更新</h3>{showUndo && <Button variant="secondary" size="sm" onClick={handleUndo}>↩ 撤销上次更新</Button>}</div><div className="flex flex-wrap gap-2 mb-3">{ENRICH_DIRECTIONS.map(d => <button key={d.key} onClick={() => handleEnrich(d.key)} disabled={enriching} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all disabled:opacity-40 ${enrichFocus === d.key ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50 hover:border-gray-300'}`}>{enriching && enrichFocus === d.key ? <span className="w-3 h-3 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" /> : <Icon name={d.icon} className="w-3 h-3" />}{d.label}</button>)}</div><div className="flex gap-2"><input type="text" value={customInstruction} onChange={e => setCustomInstruction(e.target.value)} placeholder="自定义补充指令（可选）..." className="flex-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-blue-300 focus:ring-1 focus:ring-blue-100 placeholder:text-gray-300" /><Button variant="secondary" size="sm" onClick={() => handleEnrich(enrichFocus)} disabled={enriching || !customInstruction.trim()}>执行</Button></div></Card>}
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4"><Card hover={false}><h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2"><Icon name="pencil" className="w-4 h-4 text-gray-400" /> 学习笔记</h3><textarea value={note} onChange={e => setNote(e.target.value)} placeholder="记录你的理解和思考..." className="w-full h-24 p-3 border border-gray-100 rounded-xl resize-none text-sm text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" /><Button className="mt-2" size="sm" onClick={handleSaveNote}>保存笔记</Button></Card><Card hover={false}><h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2"><Icon name="flag" className="w-4 h-4 text-gray-400" /> 快速标记</h3><div className="space-y-2"><Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => handleMark('important')}>⭐ 标记为重要</Button><Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => handleMark('confusing')}>❓ 标记为不懂</Button></div></Card></div>
    <div className="flex justify-between items-center"><Button variant="secondary" size="sm" onClick={() => { if (session) endLearningSession(session.id).catch(() => {}); const prevIdx = activeIndex - 1; if (prevIdx >= 0) loadUnit(activeUnits[prevIdx].id); }} disabled={activeIndex <= 0}>← 上一个</Button><div className="flex items-center gap-3"><div className="w-32"><ProgressBar value={activeIndex + 1} max={activeUnits.length} size="sm" color="blue" /></div><span className="text-xs text-gray-400">{activeIndex + 1}/{activeUnits.length}</span></div><Button size="sm" onClick={() => { if (session) endLearningSession(session.id).catch(() => {}); const nextIdx = activeIndex + 1; if (nextIdx < activeUnits.length) loadUnit(activeUnits[nextIdx].id); else navigate(`/books/${bookId}`); }}>{activeIndex + 1 < activeUnits.length ? '下一个单元 →' : '✓ 完成学习'}</Button></div>
    </div></div>
    <ConfirmDialog open={showCancelConfirm} title="取消学习任务" message="确定要取消当前学习任务吗？已完成的部分会保留。" confirmText="确认取消" onConfirm={confirmCancel} onCancel={() => setShowCancelConfirm(false)} />
    </div>);
}