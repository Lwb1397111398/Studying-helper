import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { generatePlan, getCurrentSession, completeSession } from '../api/plans';
import { getBook } from '../api/books';
import type { LearningPlan, PlanSessionItem, Milestone, Book } from '../types';

export default function LearningPlan() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();

  const [book, setBook] = useState<Book | null>(null);
  const [plan, setPlan] = useState<LearningPlan | null>(null);
  const [currentSession, setCurrentSession] = useState<PlanSessionItem | null>(null);
  const [completedCount, setCompletedCount] = useState(0);
  const completedCountRef = useRef(0);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [dailyGoal, setDailyGoal] = useState(30);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'warning' | 'info'; message: string } | null>(null);

  const loadData = useCallback(async () => {
    if (!bookId) return;
    setLoading(true);
    try {
      const [bookData, currentData] = await Promise.allSettled([
        getBook(bookId),
        getCurrentSession(bookId, completedCountRef.current),
      ]);
      if (bookData.status === 'fulfilled') setBook(bookData.value);
      if (currentData.status === 'fulfilled') {
        setCurrentSession(currentData.value.session);
        setCompletedCount(currentData.value.completed_sessions);
        completedCountRef.current = currentData.value.completed_sessions;
      }
    } catch (error) {
      console.error('加载失败:', error);
    } finally {
      setLoading(false);
    }
  }, [bookId]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleGenerate = async () => {
    setGenerating(true);
    setFeedback(null);
    try {
      const result = await generatePlan(bookId!, dailyGoal);
      setPlan(result);
      setCompletedCount(0);
      completedCountRef.current = 0;
      setCurrentSession(result.sessions[0] || null);
      setFeedback({ type: 'success', message: '学习方案已生成！' });
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '生成失败';
      setFeedback({ type: 'warning', message: msg });
    } finally {
      setGenerating(false);
    }
  };

  const handleStartSession = () => {
    if (currentSession && bookId) {
      navigate(`/books/${bookId}/teach?session=${currentSession.id}`);
    }
  };

  const handleCompleteSession = async (session: PlanSessionItem, correctRate: number) => {
    setCompleting(true);
    setFeedback(null);
    try {
      const update = await completeSession(bookId!, session.id, {
        correct_rate: correctRate,
        avg_response_time: 12,
        questions_asked: 3,
        duration_minutes: session.estimated_minutes,
      });

      if (update.milestone_reached) {
        setFeedback({ type: 'success', message: `🎉 ${update.milestone_reached.reward_description}` });
      } else if (update.adjusted) {
        setFeedback({ type: 'warning', message: update.reason || '建议复习' });
      } else {
        setFeedback({ type: 'info', message: '会话已完成' });
      }

      const nextCount = completedCount + 1;
      setCompletedCount(nextCount);
      completedCountRef.current = nextCount;
      setCurrentSession(update.next_session);
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '操作失败';
      setFeedback({ type: 'warning', message: msg });
    } finally {
      setCompleting(false);
    }
  };

  if (loading) return <Loading />;

  const progressPercent = plan ? Math.round((completedCount / plan.sessions.length) * 100) : 0;

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {/* 标题 */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">学习方案</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {book ? book.title : '制定你的学习计划'}
          </p>
        </div>
      </div>

      {/* 反馈消息 */}
      {feedback && (
        <div className={`mb-6 p-4 rounded-xl text-sm font-medium ${
          feedback.type === 'success' ? 'bg-emerald-50 text-emerald-700' :
          feedback.type === 'warning' ? 'bg-amber-50 text-amber-700' :
          'bg-blue-50 text-blue-700'
        }`}>
          {feedback.message}
        </div>
      )}

      {/* 无方案：生成区域 */}
      {!plan && (
        <Card className="text-center py-12">
          <div className="text-5xl mb-4 animate-float">📋</div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">还没有学习方案</h3>
          <p className="text-sm text-gray-400 mb-6">设置每日学习目标，自动生成个性化学习计划</p>

          <div className="max-w-xs mx-auto mb-6">
            <label className="block text-sm font-medium text-gray-600 mb-2">每日目标（分钟）</label>
            <div className="flex items-center gap-3">
              {[15, 30, 45, 60].map((v) => (
                <button key={v} onClick={() => setDailyGoal(v)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                    dailyGoal === v
                      ? 'bg-blue-500 text-white shadow-md shadow-blue-500/20'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}>
                  {v}
                </button>
              ))}
            </div>
          </div>

          <button onClick={handleGenerate} disabled={generating}
            className="px-6 py-2.5 bg-blue-500 text-white rounded-xl text-sm font-medium hover:bg-blue-600 transition-colors disabled:opacity-50 shadow-md shadow-blue-500/20">
            {generating ? '生成中...' : '生成学习方案'}
          </button>
        </Card>
      )}

      {/* 有方案：展示区域 */}
      {plan && (
        <>
          {/* 进度概览 */}
          <Card gradient className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">总体进度</p>
                <p className="text-3xl font-bold text-blue-600 tracking-tight mt-1">{progressPercent}%</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500">{completedCount} / {plan.sessions.length} 个会话</p>
                <p className="text-xs text-gray-400 mt-0.5">预计 {plan.total_estimated_minutes} 分钟</p>
              </div>
            </div>
            <ProgressBar value={completedCount} max={plan.sessions.length} color="blue" size="md" />
          </Card>

          {/* 当前会话 */}
          {currentSession ? (
            <Card className="mb-6 border-2 border-blue-100">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-2 py-0.5 rounded-md bg-blue-500 text-white text-xs font-bold">
                      当前
                    </span>
                    <h3 className="text-base font-bold text-gray-800">
                      第 {currentSession.session_number} 次会话
                    </h3>
                  </div>
                  <p className="text-sm text-gray-500">
                    预计 {currentSession.estimated_minutes} 分钟 · {currentSession.unit_ids.length} 个知识单元
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    教学策略：{currentSession.teaching_strategy === 'example_first' ? '举例优先' :
                      currentSession.teaching_strategy === 'theory_first' ? '理论优先' :
                      currentSession.teaching_strategy === 'problem_based' ? '问题导向' : '均衡'}
                  </p>
                </div>
                <button onClick={handleStartSession}
                  className="px-5 py-2 bg-blue-500 text-white rounded-xl text-sm font-medium hover:bg-blue-600 transition-colors shadow-md shadow-blue-500/20">
                  开始学习 →
                </button>
              </div>
            </Card>
          ) : (
            <Card className="mb-6 text-center py-8">
              <div className="text-4xl mb-3">🎊</div>
              <h3 className="text-lg font-semibold text-gray-700">全部完成！</h3>
              <p className="text-sm text-gray-400 mt-1">恭喜你完成了所有学习会话</p>
            </Card>
          )}

          {/* 里程碑 */}
          {plan.milestones.length > 0 && (
            <Card className="mb-6">
              <h2 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2">
                <span className="text-base">🏆</span> 里程碑
              </h2>
              <div className="space-y-3">
                {plan.milestones.map((milestone: Milestone) => {
                  const isReached = milestone.session_indices.every(
                    (idx: number) => idx < completedCount
                  );
                  const isActive = milestone.session_indices.includes(completedCount);
                  return (
                    <div key={milestone.id}
                      className={`flex items-center gap-3 p-3 rounded-xl transition-all ${
                        isReached ? 'bg-emerald-50' : isActive ? 'bg-blue-50' : 'bg-gray-50'
                      }`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                        isReached ? 'bg-emerald-500 text-white' :
                        isActive ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-400'
                      }`}>
                        {isReached ? '✓' : milestone.session_indices[0] + 1}
                      </div>
                      <div className="flex-1">
                        <p className={`text-sm font-medium ${isReached ? 'text-emerald-700' : 'text-gray-600'}`}>
                          {milestone.title}
                        </p>
                        <p className="text-xs text-gray-400">{milestone.reward_description}</p>
                      </div>
                      {isReached && <span className="text-xs text-emerald-500 font-bold">已完成</span>}
                      {isActive && <span className="text-xs text-blue-500 font-bold">进行中</span>}
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          {/* 会话列表 */}
          <Card>
            <h2 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2">
              <span className="text-base">📝</span> 全部会话
            </h2>
            <div className="space-y-2">
              {plan.sessions.map((session: PlanSessionItem, idx: number) => {
                const isCompleted = idx < completedCount;
                const isCurrent = idx === completedCount;
                return (
                  <div key={session.id}
                    className={`flex items-center gap-3 p-3 rounded-xl transition-all ${
                      isCompleted ? 'bg-emerald-50/50' : isCurrent ? 'bg-blue-50/50 ring-1 ring-blue-200' : 'hover:bg-gray-50'
                    }`}>
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                      isCompleted ? 'bg-emerald-500 text-white' :
                      isCurrent ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'
                    }`}>
                      {isCompleted ? '✓' : session.session_number}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm font-medium truncate ${isCompleted ? 'text-gray-400 line-through' : 'text-gray-700'}`}>
                        第 {session.session_number} 次会话
                      </p>
                      <p className="text-xs text-gray-400">
                        {session.estimated_minutes} 分钟 · {session.unit_ids.length} 单元
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* 重新生成 */}
          <div className="mt-6 text-center">
            <button onClick={handleGenerate} disabled={generating}
              className="text-sm text-gray-400 hover:text-blue-500 transition-colors">
              {generating ? '生成中...' : '🔄 重新生成方案'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
