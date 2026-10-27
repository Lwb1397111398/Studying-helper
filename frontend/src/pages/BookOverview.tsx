import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Icon from '../components/ui/Icon';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import EmptyState from '../components/ui/EmptyState';
import { BookOverviewSkeleton } from '../components/ui/Skeleton';
import { ConfirmDialog } from '../components/ui/Modal';
import { useToast } from '../components/ui/Toast';
import { getBook, getBookChapters, deleteBook, updateBookInfo, updateBookMotivation } from '../api/books';
import SplitProgress from '../components/SplitProgress';
import ChapterNode from '../components/book/ChapterNode';
import { getMasteryRecords } from '../api/review';
import { relearnUnit, enrichUnit, getLearningProgress, getDeepOverview, generateDeepOverview, getBookConcepts } from '../api/learning';
import { prepareAndStartUnitLoop } from '../api/learningAssets';
import { saveLastBook } from '../utils/lastBook';
import type { Book, Chapter, MasteryRecord, LearningProgress, BookDeepOverview } from '../types';

// 章节基本信息编辑模态框
function BookInfoDialog({
  open, initialTitle, initialAuthor, loading, onClose, onSave,
}: {
  open: boolean; initialTitle: string; initialAuthor: string | null;
  loading: boolean; onClose: () => void;
  onSave: (data: { title: string; author: string }) => void;
}) {
  const [title, setTitle] = useState(initialTitle);
  const [author, setAuthor] = useState(initialAuthor ?? '');

  useEffect(() => {
    if (open) { setTitle(initialTitle); setAuthor(initialAuthor ?? ''); }
  }, [open, initialTitle, initialAuthor]);

  return (
    <ConfirmDialog
      open={open}
      title="编辑书籍信息"
      message={
        <div className="space-y-3 text-left">
          <label className="block">
            <span className="block text-xs font-medium text-gray-500 mb-1">书名</span>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm
                focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-gray-500 mb-1">作者（可留空）</span>
            <input
              value={author}
              onChange={e => setAuthor(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm
                focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
        </div>
      }
      confirmText="保存"
      loading={loading}
      onConfirm={() => onSave({ title, author })}
      onCancel={onClose}
    />
  );
}

export default function BookOverview() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [book, setBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [mastery, setMastery] = useState<MasteryRecord[]>([]);
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [splitting, setSplitting] = useState(false);
  const [splitError, setSplitError] = useState<string | null>(null);
  const [expandedUnitId, setExpandedUnitId] = useState<string | null>(null);
  const [editingMotivation, setEditingMotivation] = useState(false);
  const [motivationText, setMotivationText] = useState('');
  const [savingMotivation, setSavingMotivation] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showInfoEdit, setShowInfoEdit] = useState(false);
  const [savingInfo, setSavingInfo] = useState(false);
  const [unitLoopLoading, setUnitLoopLoading] = useState(false);
  const [deepOverview, setDeepOverview] = useState<BookDeepOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewGenerating, setOverviewGenerating] = useState(false);
  const [bookConcepts, setBookConcepts] = useState<Array<{
    id: string; name: string; definition?: string | null;
    first_chapter_id?: string | null; source: string;
  }>>([]);

  const loadDeepOverview = async () => {
    if (!bookId) return;
    try {
      const res = await getDeepOverview(bookId);
      setDeepOverview(res.overview ?? null);
    } catch {
      setDeepOverview(null);
    }
  };

  const loadBookConcepts = async () => {
    if (!bookId) return;
    try {
      const res = await getBookConcepts(bookId);
      setBookConcepts(res.concepts ?? []);
    } catch {
      setBookConcepts([]);
    }
  };

  const loadData = async () => {
    if (!bookId) return;
    const results = await Promise.allSettled([
      getBook(bookId),
      getBookChapters(bookId),
      getMasteryRecords(bookId),
      getLearningProgress(bookId),
      getDeepOverview(bookId),
      getBookConcepts(bookId),
    ]);
    if (results[0].status === 'fulfilled') setBook(results[0].value);
    if (results[1].status === 'fulfilled') setChapters(results[1].value);
    if (results[2].status === 'fulfilled') setMastery(results[2].value);
    if (results[3].status === 'fulfilled') setProgress(results[3].value);
    if (results[4].status === 'fulfilled') setDeepOverview(results[4].value.overview ?? null);
    if (results[5].status === 'fulfilled') setBookConcepts(results[5].value.concepts ?? []);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadData();
      } catch (err) {
        if (!cancelled) console.error('加载书籍详情失败:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [bookId]);

  // 进入页面时记录"最近打开的书籍"，供首页继续学习入口使用
  useEffect(() => {
    if (book) saveLastBook({ id: book.id, title: book.title });
  }, [book?.id, book?.title]);

  // 构建树形结构（支持 parent_id 缺失时按 level 推断层级）
  const chapterTree = useMemo(() => {
    const sorted = [...chapters].sort((a, b) => a.order_index - b.order_index || a.level - b.level);
    const roots: Chapter[] = [];
    const map = new Map<string, Chapter>();
    for (const ch of sorted) map.set(ch.id, { ...ch, children: [] });

    const levelStack: Chapter[] = [];
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
    for (const ch of chapters) stats[ch.level] = (stats[ch.level] || 0) + 1;
    return stats;
  }, [chapters]);

  const handleSplitComplete = async () => {
    setSplitting(false);
    setSplitError(null);
    await loadData();
  };

  const handleDelete = async () => {
    if (!bookId) return;
    setDeleting(true);
    try {
      await deleteBook(bookId);
      toast('书籍已删除', 'success');
      navigate('/');
    } catch {
      toast('删除失败，请重试', 'error');
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
      toast('已重新生成 AI 分析', 'success');
    } catch {
      toast('重新生成失败', 'error');
    }
  };

  const handleEnrich = async (unitId: string) => {
    try {
      await enrichUnit(unitId, { focus: 'examples' });
      await loadData();
      toast('已补充示例', 'success');
    } catch {
      toast('增量更新失败', 'error');
    }
  };

  const handleUnitLoop = async (unitId: string) => {
    if (!bookId || unitLoopLoading) return;
    setUnitLoopLoading(true);
    try {
      const { asset, session } = await prepareAndStartUnitLoop(bookId, unitId);
      localStorage.setItem(`teaching_v2_session_${bookId}`, session.id);
      localStorage.setItem(`teaching_v2_unit_${bookId}`, unitId);
      localStorage.setItem(`teaching_v2_asset_${bookId}`, asset.asset_id);
      toast(
        `单单元闭环已启动（${asset.readiness_status}）· 状态 ${session.state_v2 || 'diagnose'}`,
        'success',
      );
      navigate(`/books/${bookId}/teach?engine=v2&unitId=${encodeURIComponent(unitId)}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '启动失败';
      toast(typeof msg === 'string' ? msg : '启动单单元闭环失败', 'error');
    } finally {
      setUnitLoopLoading(false);
    }
  };

  const handleGenerateOverview = async () => {
    if (!bookId || overviewGenerating) return;
    setOverviewGenerating(true);
    try {
      await generateDeepOverview(bookId, true);
      toast('全书鸟瞰生成中，稍后自动刷新', 'success');
      // 简单轮询 3 次
      for (let i = 0; i < 6; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        setOverviewLoading(true);
        await loadDeepOverview();
        setOverviewLoading(false);
        // 有数据就停
        // loadDeepOverview 写 state，下一轮 render 才有 deepOverview；这里再拉一次判断
        const res = await getDeepOverview(bookId);
        if (res.overview) {
          setDeepOverview(res.overview);
          toast(res.overview.degraded ? '已生成降级鸟瞰' : '全书鸟瞰已就绪', 'success');
          break;
        }
      }
    } catch {
      toast('生成鸟瞰失败', 'error');
    } finally {
      setOverviewGenerating(false);
      setOverviewLoading(false);
    }
  };

  const handleSaveInfo = async (data: { title: string; author: string }) => {
    if (!bookId) return;
    setSavingInfo(true);
    try {
      const updated = await updateBookInfo(bookId, {
        title: data.title,
        author: data.author || undefined,
      });
      setBook(updated);
      setShowInfoEdit(false);
      toast('已更新书籍信息', 'success');
    } catch {
      toast('保存失败', 'error');
    } finally {
      setSavingInfo(false);
    }
  };

  if (loading) return <BookOverviewSkeleton />;
  if (!book) {
    return (
      <div className="max-w-4xl mx-auto">
        <Card hover={false}>
          <EmptyState icon="alert" title="书籍不存在" description="该书籍可能已被删除或链接有误" />
        </Card>
      </div>
    );
  }

  const needsSplit = chapters.length === 0;
  const statsText = Object.entries(levelStats)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([level, count]) => `${count} L${level}`)
    .join(' · ');

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {/* 书籍头部 */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-800 via-slate-700 to-slate-800 p-8 mb-8 text-white shadow-xl">
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-5">
            <div className="w-14 h-18 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center shrink-0 border border-white/10">
              <Icon name="bookOpen" className="w-7 h-7" />
            </div>
            <div className="min-w-0">
              <h1 className="text-2xl font-bold mb-1 break-words">{book.title}</h1>
              {book.author && <p className="text-slate-300 text-sm break-words">{book.author}</p>}
              <div className="flex flex-wrap items-center gap-2 mt-3">
                <Badge tone="gray" className="!bg-white/15 !text-slate-200">{book.total_chapters} 章节</Badge>
                <Badge tone="gray" className="!bg-white/15 !text-slate-200">{book.total_units} 知识单元</Badge>
                <Badge tone="gray" className="!bg-white/15 !text-slate-200 uppercase">{book.file_type}</Badge>
              </div>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex flex-wrap gap-2 items-center">
            <Button variant="secondary" size="sm" icon="pencil" onClick={() => setShowInfoEdit(true)}
              className="!bg-white/10 !text-white !border-white/10 hover:!bg-white/20">
              编辑
            </Button>
            {!needsSplit && !splitting && (
              <Button variant="secondary" size="sm" icon="listBullet" onClick={() => navigate(`/books/${bookId}/toc`)}
                className="!bg-white/10 !text-white !border-white/10 hover:!bg-white/20">
                编辑目录
              </Button>
            )}
            {!splitting && (
              <Button variant={needsSplit ? 'warning' : 'secondary'} size="sm" icon="bolt"
                onClick={() => { setSplitting(true); setSplitError(null); }}
                className={!needsSplit ? '!bg-white/10 !text-white !border-white/10 hover:!bg-white/20' : ''}>
                {needsSplit ? '知识拆分' : '重新拆分'}
              </Button>
            )}
            <Button variant="primary" size="sm" icon="bookOpen" disabled={needsSplit}
              onClick={() => navigate(`/books/${bookId}/learn`)}>
              学习
            </Button>
            <Button variant="success" size="sm" icon="map" disabled={needsSplit}
              onClick={() => navigate(`/books/${bookId}/design`)}>
              教学设计
            </Button>
            <Button variant="primary" size="sm" icon="bolt" disabled={needsSplit}
              onClick={() => navigate(`/books/${bookId}/teach`)}>
              开始教学
            </Button>
            <Button variant="secondary" size="sm" icon="map" onClick={handleGenerateOverview} disabled={overviewGenerating || needsSplit}
              className="!bg-white/10 !text-white !border-white/10 hover:!bg-white/20">
              {overviewGenerating ? '生成中...' : '生成鸟瞰'}
            </Button>
            <Button variant="danger" size="sm" icon="trash" onClick={() => setShowDelete(true)}>
              删除
            </Button>
          </div>
        </div>
<div className="absolute -right-10 -top-10 w-40 h-40 rounded-full bg-blue-500/10 blur-3xl pointer-events-none" />
        <div className="absolute -left-6 -bottom-6 w-32 h-32 rounded-full bg-purple-500/10 blur-2xl pointer-events-none" />
      </div>

      {/* 全书鸟瞰（深度精读层 Step1）—— 无数据不渲染主体，仅可手动生成 */}
      {(deepOverview || overviewGenerating || overviewLoading) && (
        <Card hover={false} className="mb-6 animate-fade-in">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <Icon name="map" className="w-5 h-5 text-emerald-600" />
                全书鸟瞰
                {deepOverview?.degraded && (
                  <Badge tone="amber">降级版</Badge>
                )}
              </h2>
              <p className="text-xs text-gray-400 mt-1">AI 对全书核心论点、章节角色与关键概念的全局理解</p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleGenerateOverview}
              disabled={overviewGenerating || needsSplit}
            >
              {overviewGenerating ? '生成中…' : '重新生成'}
            </Button>
          </div>

          {deepOverview ? (
            <div className="space-y-4 text-sm text-gray-700">
              <div>
                <p className="text-xs font-medium text-gray-400 mb-1">核心论点</p>
                <p className="leading-relaxed">{deepOverview.core_thesis}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-400 mb-1">论证主线</p>
                <p className="leading-relaxed whitespace-pre-wrap">{deepOverview.main_thread}</p>
              </div>
              {deepOverview.reading_guide && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-1">导读</p>
                  <p className="leading-relaxed whitespace-pre-wrap">{deepOverview.reading_guide}</p>
                </div>
              )}
              {deepOverview.key_concepts?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-2">关键概念</p>
                  <div className="flex flex-wrap gap-2">
                    {deepOverview.key_concepts.map((c) => (
                      <span
                        key={c.name}
                        className="inline-flex flex-col max-w-xs rounded-lg border border-emerald-100 bg-emerald-50/60 px-3 py-2"
                        title={c.definition}
                      >
                        <span className="font-medium text-emerald-800 text-xs">{c.name}</span>
                        {c.definition && (
                          <span className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{c.definition}</span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {deepOverview.chapter_roles?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-2">章节角色</p>
                  <ul className="space-y-1.5">
                    {deepOverview.chapter_roles.map((r) => {
                      const ch = chapters.find((c) => c.id === r.chapter_id);
                      return (
                        <li key={r.chapter_id} className="flex items-start gap-2 text-xs">
                          <Badge tone="gray">{r.role || '其他'}</Badge>
                          <span className="text-gray-700">
                            <span className="font-medium">{ch?.title || r.chapter_id}</span>
                            {r.one_liner ? ` — ${r.one_liner}` : ''}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">{overviewGenerating || overviewLoading ? '正在生成全书鸟瞰…' : '暂无鸟瞰数据'}</p>
          )}
        </Card>
      )}

      {/* 概念词典（Step4）—— 无数据不渲染 */}
      {bookConcepts.length > 0 && (
        <Card hover={false} className="mb-6 animate-fade-in">
          <h2 className="text-lg font-semibold text-gray-800 mb-1 flex items-center gap-2">
            <Icon name="bookOpen" className="w-5 h-5 text-indigo-600" />
            概念词典
          </h2>
          <p className="text-xs text-gray-400 mb-3">全书统一概念清单（overview + 单元收编，只读）</p>
          <div className="flex flex-wrap gap-2">
            {bookConcepts.map((c) => {
              const ch = c.first_chapter_id
                ? chapters.find((x) => x.id === c.first_chapter_id)
                : undefined;
              return (
                <span
                  key={c.id}
                  className="inline-flex flex-col max-w-xs rounded-lg border border-indigo-100 bg-indigo-50/50 px-3 py-2"
                  title={c.definition || c.name}
                >
                  <span className="font-medium text-indigo-800 text-xs">
                    {c.name}
                    {c.source === 'unit_harvest' && (
                      <span className="ml-1 text-[10px] text-indigo-400">单元</span>
                    )}
                  </span>
                  {c.definition && (
                    <span className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{c.definition}</span>
                  )}
                  {ch && (
                    <span className="text-[10px] text-gray-400 mt-0.5">首次：{ch.title}</span>
                  )}
                </span>
              );
            })}
          </div>
        </Card>
      )}

      {/* 学习进度概览 */}
      {progress && progress.total_units > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6 animate-fade-in">
          <Card hover={false} gradient>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                <Icon name="chart" className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="text-xs text-gray-400">学习进度</p>
                <p className="text-2xl font-bold text-blue-600">{progress.progress_percent}%</p>
              </div>
            </div>
          </Card>
          <Card hover={false} gradient>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-500 flex items-center justify-center shadow-md">
                <Icon name="checkCircle" className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="text-xs text-gray-400">已学单元</p>
                <p className="text-2xl font-bold text-emerald-600">{progress.learned_units}/{progress.total_units}</p>
              </div>
            </div>
          </Card>
          <Card hover={false} gradient>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-violet-500 flex items-center justify-center shadow-md">
                <Icon name={progress.status === 'completed' ? 'flag' : progress.status === 'in_progress' ? 'play' : 'clock'} className="w-5 h-5 text-white" />
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
          <Icon name="alert" className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-700">拆分失败</p>
            <p className="text-sm text-red-500 mt-1">{splitError}</p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => { setSplitting(true); setSplitError(null); }}>
            重试
          </Button>
        </div>
      )}

      {/* 阅读动机 */}
      <Card hover={false} className="mb-6 animate-fade-in">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Icon name="flag" className="w-4 h-4 text-gray-400" />
            <h3 className="text-sm font-semibold text-gray-700">阅读动机</h3>
          </div>
          {!editingMotivation && (
            <Button variant="ghost" size="sm" onClick={() => { setMotivationText(book.reading_motivation || ''); setEditingMotivation(true); }}>
              {book.reading_motivation ? '编辑' : '设置'}
            </Button>
          )}
        </div>
        {editingMotivation ? (
          <div className="space-y-3">
            <textarea
              value={motivationText}
              onChange={(e) => setMotivationText(e.target.value)}
              placeholder="写下你阅读这本书的动机..."
              className="w-full p-3 text-sm text-gray-700 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              rows={3}
            />
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setEditingMotivation(false)}>取消</Button>
              <Button size="sm" loading={savingMotivation} onClick={async () => {
                setSavingMotivation(true);
                try {
                  const updated = await updateBookMotivation(bookId!, motivationText || null);
                  setBook(updated);
                  setEditingMotivation(false);
                  toast('已保存阅读动机', 'success');
                } catch {
                  toast('保存失败', 'error');
                } finally {
                  setSavingMotivation(false);
                }
              }}>
                保存
              </Button>
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
        {!needsSplit && statsText && <span className="text-xs text-gray-400">{statsText}</span>}
      </div>

      {splitting ? (
        <SplitProgress key={bookId} bookId={bookId!} onComplete={handleSplitComplete} onError={(msg) => setSplitError(msg)} />
      ) : chapterTree.length === 0 ? (
        <Card hover={false}>
          <EmptyState
            icon="documentText"
            title="暂无章节数据"
            description={'点击上方「知识拆分」按钮，自动解析书籍内容并生成章节和知识单元'}
            action={<Button icon="bolt" onClick={() => { setSplitting(true); setSplitError(null); }}>开始知识拆分</Button>}
          />
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
              onUnitLoop={handleUnitLoop}
              unitLoopLoading={unitLoopLoading}
            />
          ))}
        </div>
      )}

      {/* 确认删除弹窗 */}
      <ConfirmDialog
        open={showDelete}
        title="删除书籍"
        message={`确定要删除《${book.title}》吗？此操作将同时删除章节、学习记录、知识图谱等所有关联数据，且不可恢复。`}
        confirmText="确认删除"
        danger
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setShowDelete(false)}
      />

      {/* 编辑书籍信息弹窗 */}
      <BookInfoDialog
        open={showInfoEdit}
        initialTitle={book.title}
        initialAuthor={book.author ?? null}
        loading={savingInfo}
        onClose={() => setShowInfoEdit(false)}
        onSave={handleSaveInfo}
      />
    </div>
  );
}
