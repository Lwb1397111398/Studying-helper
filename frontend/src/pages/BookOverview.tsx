import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { getBook, getBookChapters, deleteBook } from '../api/books';
import SplitProgress from '../components/SplitProgress';
import { getMasteryRecords } from '../api/review';
import { relearnUnit, enrichUnit } from '../api/learning';
import type { Book, Chapter, Section, MasteryRecord } from '../types';

export default function BookOverview() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [book, setBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [mastery, setMastery] = useState<MasteryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [splitting, setSplitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [splitError, setSplitError] = useState<string | null>(null);

  useEffect(() => {
    if (bookId) loadData();
  }, [bookId]);

  const loadData = async () => {
    try {
      const results = await Promise.allSettled([
        getBook(bookId!),
        getBookChapters(bookId!),
        getMasteryRecords(bookId!),
      ]);
      if (results[0].status === 'fulfilled') setBook(results[0].value);
      if (results[2].status === 'fulfilled') setMastery(results[2].value);

      if (results[1].status === 'fulfilled') {
        const allItems: (Chapter | Section)[] = results[1].value;
        // 按 level 分离：level=1 的是小节(Section)，其余是章(Chapter)
        const chs: Chapter[] = [];
        const secs: Section[] = [];
        for (const item of allItems) {
          if ((item as any).level === 1) {
            secs.push(item as Section);
          } else {
            chs.push(item as Chapter);
          }
        }
        setChapters(chs);
        setSections(secs);
      }
    } catch (error) {
      console.error('加载书籍详情失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 按 chapter_id 分组 sections
  const sectionsByChapter = useMemo(() => {
    const map: Record<string, Section[]> = {};
    for (const sec of sections) {
      const parentId = (sec as any).chapter_id || (sec as any).parent_id;
      if (parentId) {
        if (!map[parentId]) map[parentId] = [];
        map[parentId].push(sec);
      }
    }
    // 每组内按 order_index 排序
    for (const key of Object.keys(map)) {
      map[key].sort((a, b) => (a as any).order_index - (b as any).order_index);
    }
    return map;
  }, [sections]);

  const handleSplitComplete = async (result: { chapters_count: number; units_count: number; sections_count?: number }) => {
    setSplitting(false);
    setSplitError(null);
    const results = await Promise.allSettled([getBook(bookId!), getBookChapters(bookId!)]);
    if (results[0].status === 'fulfilled') setBook(results[0].value);
    if (results[1].status === 'fulfilled') {
      const allItems: (Chapter | Section)[] = results[1].value;
      const chs: Chapter[] = [];
      const secs: Section[] = [];
      for (const item of allItems) {
        if ((item as any).level === 1) {
          secs.push(item as Section);
        } else {
          chs.push(item as Chapter);
        }
      }
      setChapters(chs);
      setSections(secs);
    }
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

  const getUnitMastery = (unitId: string) => {
    const record = mastery.find((m) => m.knowledge_unit_id === unitId);
    return Math.round((record?.mastery_score ?? 0) * 100);
  };

  const getMasteryLevelLabel = (level: string) => {
    const map: Record<string, { label: string; color: string }> = {
      mastered:    { label: '已掌握', color: 'bg-emerald-100 text-emerald-700' },
      proficient:  { label: '熟练',   color: 'bg-blue-100 text-blue-700' },
      familiar:    { label: '熟悉',   color: 'bg-amber-100 text-amber-700' },
      beginner:    { label: '初学',   color: 'bg-red-100 text-red-700' },
    };
    return map[level] || { label: '未学习', color: 'bg-gray-100 text-gray-500' };
  };

  // 知识单元行组件
  const UnitItem = ({ unit }: { unit: import('../types').KnowledgeUnit }) => {
    const score = getUnitMastery(unit.id);
    const record = mastery.find((m) => m.knowledge_unit_id === unit.id);
    const levelInfo = getMasteryLevelLabel(record?.mastery_level || '');
    const hasAiContent = !!unit.summary;
    return (
      <div className="flex items-center gap-3 group">
        <div className="flex-1 flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full ${
            score >= 80 ? 'bg-emerald-400' : score >= 50 ? 'bg-amber-400' : score > 0 ? 'bg-red-400' : 'bg-gray-300'
          }`} />
          <p className="text-sm text-gray-600 group-hover:text-gray-800 transition-colors">{unit.title}</p>
          {record?.mastery_level && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${levelInfo.color}`}>
              {levelInfo.label}
            </span>
          )}
        </div>
        <div className="w-24">
          <ProgressBar value={score} size="sm"
            color={score >= 80 ? 'green' : score >= 50 ? 'yellow' : 'red'}
          />
        </div>
        <span className="text-xs text-gray-400 w-10 text-right font-medium">{score}%</span>
        {hasAiContent && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={async (e) => {
                e.stopPropagation();
                try { await relearnUnit(unit.id); alert('重新生成完成，刷新查看'); }
                catch { alert('重新生成失败'); }
              }}
              className="text-[10px] text-purple-500 hover:text-purple-600 px-1.5 py-0.5 rounded hover:bg-purple-50 transition-colors"
              title="重新生成 AI 分析">
              🔄
            </button>
            <button
              onClick={async (e) => {
                e.stopPropagation();
                try { await enrichUnit(unit.id, { focus: 'examples' }); alert('增量更新完成，刷新查看'); }
                catch { alert('增量更新失败'); }
              }}
              className="text-[10px] text-emerald-500 hover:text-emerald-600 px-1.5 py-0.5 rounded hover:bg-emerald-50 transition-colors"
              title="增量更新（补充例子）">
              ✨
            </button>
          </div>
        )}
      </div>
    );
  };

  if (loading) return <Loading />;
  if (!book) return <div className="text-center py-12 text-gray-500">书籍不存在</div>;

  const needsSplit = chapters.length === 0 && sections.length === 0;

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
          <div className="flex gap-2 flex-wrap justify-end max-w-xs">
            {needsSplit && !splitting && (
              <button onClick={() => { setSplitting(true); setSplitError(null); }}
                className="flex items-center gap-1.5 px-4 py-2 bg-amber-500 text-white rounded-xl text-sm font-medium hover:bg-amber-400 shadow-lg shadow-amber-500/25 transition-all">
                ⚡ 知识拆分
              </button>
            )}
            <button onClick={() => navigate(`/books/${bookId}/plan`)} disabled={needsSplit}
              className="flex items-center gap-1.5 px-4 py-2 bg-cyan-500 text-white rounded-xl text-sm font-medium hover:bg-cyan-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-cyan-500/25 transition-all">
              📋 方案
            </button>
            <button onClick={() => navigate(`/books/${bookId}/learn`)} disabled={needsSplit}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-500 text-white rounded-xl text-sm font-medium hover:bg-blue-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-blue-500/25 transition-all">
              📚 学习
            </button>
            <button onClick={() => navigate(`/books/${bookId}/teach`)} disabled={needsSplit}
              className="flex items-center gap-1.5 px-4 py-2 bg-violet-500 text-white rounded-xl text-sm font-medium hover:bg-violet-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-violet-500/25 transition-all">
              🎓 教学
            </button>
            <button onClick={() => navigate(`/books/${bookId}/review`)} disabled={needsSplit}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500 text-white rounded-xl text-sm font-medium hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/25 transition-all">
              🔄 复习
            </button>
            <button onClick={() => navigate(`/books/${bookId}/exam`)} disabled={needsSplit}
              className="flex items-center gap-1.5 px-4 py-2 bg-orange-500 text-white rounded-xl text-sm font-medium hover:bg-orange-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-orange-500/25 transition-all">
              📝 考试
            </button>
            <button onClick={() => navigate(`/books/${bookId}/graph`)} disabled={needsSplit}
              className="flex items-center gap-1.5 px-4 py-2 bg-purple-500 text-white rounded-xl text-sm font-medium hover:bg-purple-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-purple-500/25 transition-all">
              🕸️ 图谱
            </button>
            <button onClick={() => navigate(`/books/${bookId}/export`)} disabled={needsSplit}
              className="flex items-center gap-1.5 px-3 py-2 bg-white/10 text-white/80 rounded-xl text-sm font-medium hover:bg-white/20 transition-all border border-white/10">
              📦 导出
            </button>
            {!needsSplit && !splitting && (
              <>
                <button onClick={() => { setSplitting(true); setSplitError(null); }}
                  className="flex items-center gap-1.5 px-3 py-2 bg-white/10 text-white/80 rounded-xl text-sm font-medium hover:bg-white/20 transition-all border border-white/10">
                  🔁 重新拆分
                </button>
                <button onClick={() => navigate(`/books/${bookId}/toc`)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-white/10 text-white/80 rounded-xl text-sm font-medium hover:bg-white/20 transition-all border border-white/10">
                  📝 编辑目录
                </button>
              </>
            )}
            <button onClick={handleDelete} disabled={deleting}
              className="flex items-center gap-1.5 px-3 py-2 bg-white/10 text-red-300 rounded-xl text-sm font-medium hover:bg-red-500/20 disabled:opacity-50 transition-all border border-white/10">
              🗑️ 删除
            </button>
          </div>
        </div>
        <div className="absolute -right-10 -top-10 w-40 h-40 rounded-full bg-blue-500/10 blur-3xl" />
        <div className="absolute -left-6 -bottom-6 w-32 h-32 rounded-full bg-purple-500/10 blur-2xl" />
      </div>

      {/* 拆分错误提示（非 NoTOCError 的通用错误） */}
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

      {/* 章节列表 */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold text-gray-800">章节列表</h2>
        {!needsSplit && (
          <span className="text-xs text-gray-400">
            {chapters.length} 章节{sections.length > 0 ? ` · ${sections.length} 小节` : ''}
          </span>
        )}
      </div>

      {splitting ? (
        <SplitProgress
          key={bookId}
          bookId={bookId!}
          onComplete={handleSplitComplete}
          onError={handleSplitError}
        />
      ) : chapters.length === 0 ? (
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
          {chapters.map((chapter, i) => {
            const chapterSections = sectionsByChapter[chapter.id] || [];
            return (
              <Card key={chapter.id} className={`animate-fade-in delay-${Math.min((i + 1) * 100, 400)}`}>
                {/* 章标题 */}
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-bold shadow-sm">
                    {i + 1}
                  </div>
                  <h3 className="font-semibold text-gray-800">{chapter.title}</h3>
                  {chapter.knowledge_units && (
                    <span className="text-[10px] text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full ml-auto">
                      {chapter.knowledge_units.length} 单元
                    </span>
                  )}
                </div>

                {/* 三层结构：有小节时展示 章→小节→单元，无小节时直接展示单元 */}
                {chapterSections.length > 0 ? (
                  <div className="space-y-4 pl-11">
                    {chapterSections.map((sec, si) => (
                      <div key={sec.id} className="border-l-2 border-indigo-200 pl-4">
                        {/* 小节标题 */}
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[10px] font-semibold text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded">
                            §{si + 1}
                          </span>
                          <h4 className="text-sm font-medium text-gray-700">{sec.title}</h4>
                          {sec.knowledge_units && (
                            <span className="text-[10px] text-gray-400">
                              {sec.knowledge_units.length} 单元
                            </span>
                          )}
                        </div>
                        {/* 小节下的知识单元 */}
                        {sec.knowledge_units && sec.knowledge_units.length > 0 ? (
                          <div className="space-y-2 pl-2">
                            {sec.knowledge_units.map((unit) => (
                              <UnitItem key={unit.id} unit={unit} />
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-gray-400 pl-2">暂无知识单元</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : chapter.knowledge_units && chapter.knowledge_units.length > 0 ? (
                  <div className="space-y-2 pl-11">
                    {chapter.knowledge_units.map((unit) => (
                      <UnitItem key={unit.id} unit={unit} />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 pl-11">暂无知识单元</p>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
