import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { getBookChapters } from '../api/books';
import SplitProgress from '../components/SplitProgress';
import {
  getKnowledgeUnit, startLearningSession, endLearningSession,
  saveNote, markUnit, startLearning, relearnUnit, enrichUnit,
} from '../api/learning';
import type { Chapter, KnowledgeUnit, LearningRecord } from '../types';

export default function LearningSession() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [currentUnit, setCurrentUnit] = useState<KnowledgeUnit | null>(null);
  const [session, setSession] = useState<LearningRecord | null>(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [splitting, setSplitting] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  // 选单元学
  const [selectedUnitIds, setSelectedUnitIds] = useState<Set<string>>(new Set());
  const [selectMode, setSelectMode] = useState(false);
  // AI 学习状态
  const [aiLearning, setAiLearning] = useState(false);
  const [aiProgress, setAiProgress] = useState({ done: 0, total: 0, title: '' });
  // 重新生成 / 增量更新状态
  const [regenerating, setRegenerating] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [enrichFocus, setEnrichFocus] = useState<'examples' | 'explanations' | 'connections'>('examples');
  const [showEnrichMenu, setShowEnrichMenu] = useState(false);

  const allUnits = chapters.flatMap((c) => c.knowledge_units || []);
  const activeUnits = selectedUnitIds.size > 0
    ? allUnits.filter((u) => selectedUnitIds.has(u.id))
    : allUnits;
  const activeIndex = activeUnits.findIndex((u) => u.id === currentUnit?.id);
  const progress = activeUnits.length > 0 ? Math.round(((activeIndex + 1) / activeUnits.length) * 100) : 0;

  useEffect(() => {
    if (bookId) loadChapters();
  }, [bookId]);

  const loadChapters = async () => {
    try {
      const data = await getBookChapters(bookId!);
      setChapters(data);
      const units = data.flatMap((c) => c.knowledge_units || []);
      if (units.length > 0) {
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
      try {
        const sessionData = await startLearningSession(unitId);
        setSession(sessionData);
      } catch { /* 会话创建失败不影响学习 */ }
      setNote('');
    } catch (error) {
      console.error('加载知识单元失败:', error);
    }
  };

  // 开始 AI 学习（整本或选中的单元）
  const handleStartLearning = async () => {
    if (!bookId) return;
    setAiLearning(true);
    setAiProgress({ done: 0, total: activeUnits.length, title: '' });
    try {
      const result = await startLearning(
        bookId,
        selectedUnitIds.size > 0 ? Array.from(selectedUnitIds) : undefined,
      );
      setAiProgress({ done: result.learned_count, total: result.total_units, title: '完成' });
      // 刷新当前单元（可能已被 AI 更新）
      if (currentUnit) {
        const updated = await getKnowledgeUnit(currentUnit.id);
        setCurrentUnit(updated);
      }
    } catch (error) {
      console.error('AI 学习失败:', error);
      alert('AI 学习失败，请重试');
    } finally {
      setAiLearning(false);
    }
  };

  // 重新生成当前单元
  const handleRelearn = async () => {
    if (!currentUnit) return;
    setRegenerating(true);
    try {
      const result = await relearnUnit(currentUnit.id);
      setCurrentUnit((prev) => prev ? {
        ...prev,
        summary: result.summary,
        key_points: result.key_points,
        concepts: result.concepts.map((c) => c.name),
        difficulty_level: result.difficulty_level,
      } : prev);
    } catch (error) {
      console.error('重新生成失败:', error);
      alert('重新生成失败，请重试');
    } finally {
      setRegenerating(false);
    }
  };

  // 增量更新当前单元
  const handleEnrich = async () => {
    if (!currentUnit) return;
    setEnriching(true);
    setShowEnrichMenu(false);
    try {
      const result = await enrichUnit(currentUnit.id, { focus: enrichFocus });
      setCurrentUnit((prev) => prev ? {
        ...prev,
        summary: result.summary,
        key_points: result.key_points,
        concepts: result.concepts.map((c) => c.name),
        difficulty_level: result.difficulty_level,
      } : prev);
    } catch (error) {
      console.error('增量更新失败:', error);
      alert('增量更新失败，请重试');
    } finally {
      setEnriching(false);
    }
  };

  const handleNext = async () => {
    if (session) {
      try { await endLearningSession(session.id); } catch {}
    }
    const nextIndex = activeIndex + 1;
    if (nextIndex < activeUnits.length) {
      setCurrentIndex(allUnits.indexOf(activeUnits[nextIndex]));
      loadUnit(activeUnits[nextIndex].id);
    } else {
      navigate(`/books/${bookId}`);
    }
  };

  const handlePrev = async () => {
    if (session) {
      try { await endLearningSession(session.id); } catch {}
    }
    const prevIndex = activeIndex - 1;
    if (prevIndex >= 0) {
      setCurrentIndex(allUnits.indexOf(activeUnits[prevIndex]));
      loadUnit(activeUnits[prevIndex].id);
    }
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

  const toggleUnitSelection = (unitId: string) => {
    setSelectedUnitIds((prev) => {
      const next = new Set(prev);
      if (next.has(unitId)) next.delete(unitId);
      else next.add(unitId);
      return next;
    });
  };

  if (loading) return <Loading />;

  if (allUnits.length === 0) {
    return (
      <div className="max-w-2xl mx-auto animate-fade-in">
        {splitting ? (
          <SplitProgress
            key={bookId}
            bookId={bookId!}
            onComplete={async () => {
              setSplitting(false);
              await loadChapters();
            }}
            onError={(msg) => {
              setSplitting(false);
              alert(msg);
            }}
          />
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
    <div className="max-w-4xl mx-auto animate-fade-in">
      {/* 顶部控制栏 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-800">学习模式</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {selectedUnitIds.size > 0
              ? `已选 ${selectedUnitIds.size} 个单元`
              : `知识单元 ${activeIndex + 1} / ${activeUnits.length}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* 选单元切换 */}
          <button onClick={() => setSelectMode(!selectMode)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              selectMode ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}>
            {selectMode ? '✓ 确认选择' : '📋 选单元'}
          </button>
          {/* 进度 */}
          {!selectMode && (
            <div className="flex items-center gap-2">
              <div className="w-32">
                <ProgressBar value={activeIndex + 1} max={activeUnits.length} size="sm" color="blue" />
              </div>
              <span className="text-sm font-semibold text-blue-600">{progress}%</span>
            </div>
          )}
        </div>
      </div>

      {/* 选单元模式：展示所有单元供选择 */}
      {selectMode && (
        <Card className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-700">选择要学习的单元</h3>
            <div className="flex gap-2">
              <button onClick={() => setSelectedUnitIds(new Set(allUnits.map((u) => u.id)))}
                className="text-xs text-blue-500 hover:text-blue-600">全选</button>
              <button onClick={() => setSelectedUnitIds(new Set())}
                className="text-xs text-gray-400 hover:text-gray-600">清空</button>
            </div>
          </div>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {chapters.map((chapter) => (
              <div key={chapter.id}>
                <p className="text-xs font-semibold text-gray-500 mb-1">{chapter.title}</p>
                {(chapter.knowledge_units || []).map((unit) => (
                  <label key={unit.id} className="flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedUnitIds.has(unit.id)}
                      onChange={() => toggleUnitSelection(unit.id)}
                      className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-600">{unit.title}</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* AI 学习进度 */}
      {(aiLearning || aiProgress.total > 0) && (
        <Card className="mb-6 bg-blue-50 border border-blue-100">
          <div className="flex items-center gap-3">
            {aiLearning ? (
              <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            ) : (
              <span className="text-blue-500 text-lg">✓</span>
            )}
            <div className="flex-1">
              <p className="text-sm font-medium text-blue-700">
                {aiLearning ? 'AI 正在学习...' : `AI 学习完成：${aiProgress.done}/${aiProgress.total} 个单元`}
              </p>
              {aiProgress.title && (
                <p className="text-xs text-blue-500 mt-0.5">{aiProgress.title}</p>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* 操作按钮行 */}
      <div className="flex items-center gap-2 mb-6 flex-wrap">
        <button onClick={handleStartLearning} disabled={aiLearning}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all disabled:opacity-50">
          🤖 {selectedUnitIds.size > 0 ? `AI 学习选中 (${selectedUnitIds.size})` : 'AI 学习全部'}
        </button>
        <button onClick={handleRelearn} disabled={regenerating || !currentUnit.summary}
          className="flex items-center gap-1.5 px-3 py-2 bg-purple-50 text-purple-600 rounded-xl text-sm font-medium hover:bg-purple-100 transition-all disabled:opacity-40 border border-purple-100">
          {regenerating ? <span className="w-3 h-3 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" /> : '🔄'}
          重新生成
        </button>
        <div className="relative">
          <button onClick={() => setShowEnrichMenu(!showEnrichMenu)} disabled={enriching || !currentUnit.summary}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-50 text-emerald-600 rounded-xl text-sm font-medium hover:bg-emerald-100 transition-all disabled:opacity-40 border border-emerald-100">
            {enriching ? <span className="w-3 h-3 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" /> : '✨'}
            增量更新
          </button>
          {showEnrichMenu && (
            <div className="absolute top-full left-0 mt-1 bg-white rounded-xl shadow-lg border border-gray-100 py-2 z-10 min-w-[160px]">
              <p className="text-[10px] text-gray-400 px-3 py-1 uppercase tracking-wider">补充方向</p>
              {([
                { key: 'examples', label: '📌 补充例子' },
                { key: 'explanations', label: '💡 深入解释' },
                { key: 'connections', label: '🔗 关联拓展' },
              ] as const).map((opt) => (
                <button key={opt.key} onClick={() => { setEnrichFocus(opt.key); handleEnrich(); }}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${
                    enrichFocus === opt.key ? 'text-emerald-600 font-medium bg-emerald-50' : 'text-gray-600'
                  }`}>
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 知识单元内容 */}
      <Card className="mb-6 animate-scale-in" gradient>
        <div className="flex items-start gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-md shadow-blue-500/20">
            {activeIndex + 1}
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-bold text-gray-800">{currentUnit.title}</h2>
            {currentUnit.summary && (
              <p className="text-xs text-gray-400 mt-1">{currentUnit.summary}</p>
            )}
          </div>
          {/* 重新生成 / 增量更新快捷按钮 */}
          {currentUnit.summary && (
            <button onClick={handleRelearn} disabled={regenerating}
              className="text-xs text-purple-500 hover:text-purple-600 disabled:opacity-40 shrink-0"
              title="重新生成 AI 分析">
              🔄
            </button>
          )}
        </div>

        <div className="prose prose-sm max-w-none text-gray-600 leading-relaxed">
          {currentUnit.content?.split('\n').map((paragraph, i) => (
            paragraph.trim() && <p key={i} className="mb-3 text-[15px] leading-7">{paragraph}</p>
          ))}
        </div>

        {currentUnit.key_points && currentUnit.key_points.length > 0 && (
          <div className="mt-6 pt-5 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">🔑 要点</p>
            <div className="space-y-2">
              {currentUnit.key_points.map((point, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">{i + 1}</span>
                  <p className="text-sm text-gray-600">{point}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {currentUnit.concepts && currentUnit.concepts.length > 0 && (
          <div className="mt-5 flex flex-wrap gap-2">
            {currentUnit.concepts.map((concept, i) => (
              <span key={i} className="px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-xs font-medium border border-blue-100">
                {concept}
              </span>
            ))}
          </div>
        )}
      </Card>

      {/* 笔记和标记 */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card hover={false}>
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <span>📝</span> 学习笔记
          </h3>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="记录你的理解和思考..."
            className="w-full h-28 p-3 border border-gray-100 rounded-xl resize-none text-sm text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all"
          />
          <button onClick={handleSaveNote}
            className="mt-2 px-4 py-1.5 bg-gray-700 text-white rounded-lg text-xs font-medium hover:bg-gray-600 transition-colors">
            保存笔记
          </button>
        </Card>
        <Card hover={false}>
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <span>🏷️</span> 快速标记
          </h3>
          <div className="space-y-2">
            <button onClick={() => handleMark('important')}
              className="w-full px-4 py-3 bg-amber-50 text-amber-700 rounded-xl hover:bg-amber-100 text-left text-sm font-medium transition-colors flex items-center gap-2 border border-amber-100">
              ⭐ 标记为重要
            </button>
            <button onClick={() => handleMark('confusing')}
              className="w-full px-4 py-3 bg-red-50 text-red-600 rounded-xl hover:bg-red-100 text-left text-sm font-medium transition-colors flex items-center gap-2 border border-red-100">
              ❓ 标记为不懂
            </button>
          </div>
        </Card>
      </div>

      {/* 导航按钮 */}
      <div className="flex justify-between items-center">
        <div className="flex gap-2">
          <button onClick={handlePrev} disabled={activeIndex <= 0}
            className="px-4 py-2.5 text-gray-500 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors disabled:opacity-30">
            ← 上一个
          </button>
          <button onClick={() => navigate(`/books/${bookId}`)}
            className="px-4 py-2.5 text-gray-500 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors">
            退出学习
          </button>
        </div>
        <button onClick={handleNext}
          className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all">
          {activeIndex + 1 < activeUnits.length ? '下一个单元 →' : '✓ 完成学习'}
        </button>
      </div>
    </div>
  );
}
