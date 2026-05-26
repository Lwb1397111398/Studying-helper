import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import {
  startTeachingSession, getNextTeachingMessage, askTeachingQuestion,
  getTeachingMessages, addTeachingAnnotation, runTeachingTest,
  submitTeachingAnswers, completeTeachingSession,
} from '../api/teaching';
import type {
  TeachingSession as TeachingSessionType,
  TeachingMessage, UserQuestion, SessionTest,
} from '../types/teaching';
import { PHASE_CONFIG } from '../types/teaching';

// 后端 API 前缀与学习会话相同，复用 books API 加载知识单元
import { getBookChapters } from '../api/books';
import type { Chapter, KnowledgeUnit } from '../types';

const CURRENT_USER_ID = 'anonymous';

export default function TeachingSession() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 数据状态
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [units, setUnits] = useState<KnowledgeUnit[]>([]);
  const [session, setSession] = useState<TeachingSessionType | null>(null);

  // 消息流
  const [messages, setMessages] = useState<TeachingMessage[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string>('activate');

  // UI 状态
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const [questionInput, setQuestionInput] = useState('');
  const [asking, setAsking] = useState(false);
  const [noteInput, setNoteInput] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  // 测试状态
  const [test, setTest] = useState<SessionTest | null>(null);
  const [testAnswers, setTestAnswers] = useState<Record<number, string>>({});
  const [submittingTest, setSubmittingTest] = useState(false);

  // 会话完成
  const [completed, setCompleted] = useState(false);

  // 初始化：加载书籍章节和知识单元
  useEffect(() => {
    if (bookId) loadData();
  }, [bookId]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadData = async () => {
    try {
      const data = await getBookChapters(bookId!);
      setChapters(data);
      const allUnits = data.flatMap((c) => c.knowledge_units || []);
      setUnits(allUnits);
      if (allUnits.length > 0) {
        await startNewSession(allUnits);
      }
    } catch (error) {
      console.error('加载数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const startNewSession = async (unitList: KnowledgeUnit[]) => {
    try {
      const unitIds = unitList.map((u) => u.id);
      const sess = await startTeachingSession(CURRENT_USER_ID, bookId!, unitIds);
      setSession(sess);
      setCurrentPhase(sess.current_phase);
      // 自动获取第一条消息
      await advanceMessage(sess.id);
    } catch (error) {
      console.error('开始教学会话失败:', error);
    }
  };

  const advanceMessage = useCallback(async (sessionId: string) => {
    setAdvancing(true);
    try {
      const msg = await getNextTeachingMessage(sessionId);
      setMessages((prev) => [...prev, msg]);
      setCurrentPhase(msg.phase);

      // 检查是否所有单元已完成
      if (session && msg.phase === 'connect') {
        const dbSession = await getTeachingMessages(sessionId).then(() => null);
        // 如果是最后一个单元的 CONNECT，提示可以测试
      }
    } catch (error: unknown) {
      const errMsg = error instanceof Error ? error.message : '';
      if (errMsg.includes('所有单元已学完')) {
        setCompleted(true);
      } else {
        console.error('获取消息失败:', error);
      }
    } finally {
      setAdvancing(false);
    }
  }, [session]);

  const handleAdvance = async () => {
    if (!session || advancing) return;
    await advanceMessage(session.id);
  };

  const handleAskQuestion = async () => {
    if (!session || !questionInput.trim() || asking) return;
    setAsking(true);
    try {
      const result = await askTeachingQuestion(session.id, questionInput.trim());
      // 把问答加入消息流展示
      setMessages((prev) => [
        ...prev,
        {
          id: `q-${result.id}`,
          session_id: session.id,
          unit_id: '',
          phase: currentPhase as TeachingMessage['phase'],
          content: `❓ ${result.question}`,
          content_type: 'text',
          created_at: result.asked_at,
        },
        {
          id: `a-${result.id}`,
          session_id: session.id,
          unit_id: '',
          phase: currentPhase as TeachingMessage['phase'],
          content: `💬 ${result.answer}`,
          content_type: 'text',
          created_at: result.asked_at,
        },
      ]);
      setQuestionInput('');
    } catch (error) {
      console.error('提问失败:', error);
    } finally {
      setAsking(false);
    }
  };

  const handleSaveNote = async (type: 'important' | 'confusing' | 'note') => {
    if (!session || !noteInput.trim()) return;
    setSavingNote(true);
    try {
      // 找到当前消息对应的 unit_id
      const currentMsg = messages[messages.length - 1];
      if (currentMsg) {
        await addTeachingAnnotation(
          CURRENT_USER_ID, currentMsg.unit_id, type, noteInput.trim(),
        );
      }
      setNoteInput('');
    } catch (error) {
      console.error('保存笔记失败:', error);
    } finally {
      setSavingNote(false);
    }
  };

  const handleRunTest = async () => {
    if (!session) return;
    try {
      const testResult = await runTeachingTest(session.id);
      setTest(testResult);
      setTestAnswers({});
    } catch (error) {
      console.error('运行测试失败:', error);
    }
  };

  const handleSubmitTest = async () => {
    if (!test || submittingTest) return;
    setSubmittingTest(true);
    try {
      const answers = test.questions.map((_, i) => testAnswers[i] || '');
      const result = await submitTeachingAnswers(test.id, answers);
      setTest(result);
    } catch (error) {
      console.error('提交测试失败:', error);
    } finally {
      setSubmittingTest(false);
    }
  };

  const handleFinishSession = async () => {
    if (!session) return;
    try {
      const testScore = test?.score ?? undefined;
      await completeTeachingSession(session.id, {
        questions_asked: messages.filter((m) => m.content.startsWith('❓')).length,
        test_score: testScore,
      });
      navigate(`/books/${bookId}`);
    } catch (error) {
      console.error('完成会话失败:', error);
    }
  };

  // ---- 渲染辅助 ----

  const getPhaseColor = (phase: string) => {
    const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG];
    if (!config) return 'gray';
    return config.color;
  };

  const getPhaseLabel = (phase: string) => {
    const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG];
    return config ? `${config.icon} ${config.label}` : phase;
  };

  // 计算进度
  const totalUnits = units.length;
  const currentUnitIndex = session?.current_unit_index ?? 0;
  const phasesPerUnit = 6;
  const totalSteps = totalUnits * phasesPerUnit;
  const completedSteps = messages.length;
  const progressPercent = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  if (loading) return <Loading />;

  if (units.length === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center py-20 animate-fade-in">
        <div className="text-6xl mb-5 animate-float">📚</div>
        <h2 className="text-xl font-bold text-gray-800 mb-2">没有可教学的内容</h2>
        <p className="text-sm text-gray-400 mb-8">请先上传书籍并进行知识拆分</p>
        <button
          onClick={() => navigate(`/books/${bookId}`)}
          className="px-5 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all"
        >
          返回书籍详情
        </button>
      </div>
    );
  }

  // 渲染消息气泡
  const renderMessage = (msg: TeachingMessage, index: number) => {
    const isQuestion = msg.content.startsWith('❓');
    const isAnswer = msg.content.startsWith('💬');

    if (isQuestion) {
      return (
        <div key={msg.id} className="flex justify-end mb-4 animate-fade-in">
          <div className="max-w-[70%] bg-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-3 shadow-sm">
            <p className="text-sm leading-relaxed">{msg.content.slice(2)}</p>
          </div>
        </div>
      );
    }

    if (isAnswer) {
      return (
        <div key={msg.id} className="flex justify-start mb-4 animate-fade-in">
          <div className="max-w-[70%] bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
            <p className="text-sm text-gray-700 leading-relaxed">{msg.content.slice(2)}</p>
          </div>
        </div>
      );
    }

    // 系统教学消息
    const phaseColor = getPhaseColor(msg.phase);
    const colorMap: Record<string, string> = {
      amber: 'from-amber-50 to-orange-50 border-amber-100',
      blue: 'from-blue-50 to-indigo-50 border-blue-100',
      purple: 'from-purple-50 to-violet-50 border-purple-100',
      green: 'from-green-50 to-emerald-50 border-green-100',
      orange: 'from-orange-50 to-yellow-50 border-orange-100',
      indigo: 'from-indigo-50 to-blue-50 border-indigo-100',
    };
    const bgClass = colorMap[phaseColor] || 'from-gray-50 to-slate-50 border-gray-100';

    return (
      <div key={msg.id || index} className="mb-5 animate-fade-in">
        <div className={`bg-gradient-to-r ${bgClass} border rounded-2xl p-5 shadow-sm`}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base">{getPhaseLabel(msg.phase).split(' ')[0]}</span>
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {getPhaseLabel(msg.phase).split(' ').slice(1).join(' ')}
            </span>
          </div>
          <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
            {msg.content}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {/* 顶部进度栏 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-800">🎓 教学模式</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            单元 {currentUnitIndex + 1} / {totalUnits} · {getPhaseLabel(currentPhase)}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="w-40">
            <ProgressBar value={completedSteps} max={totalSteps} size="sm" color="blue" />
          </div>
          <span className="text-sm font-semibold text-blue-600">{progressPercent}%</span>
        </div>
      </div>

      {/* 阶段进度指示器 */}
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-2">
        {Object.entries(PHASE_CONFIG).map(([phase, config]) => {
          const isActive = currentPhase === phase;
          const phaseOrder = Object.keys(PHASE_CONFIG);
          const currentOrder = phaseOrder.indexOf(currentPhase);
          const thisOrder = phaseOrder.indexOf(phase);
          const isPast = thisOrder < currentOrder;

          return (
            <div
              key={phase}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium shrink-0 transition-all ${
                isActive
                  ? 'bg-blue-500 text-white shadow-md shadow-blue-500/20'
                  : isPast
                  ? 'bg-blue-50 text-blue-600'
                  : 'bg-gray-50 text-gray-400'
              }`}
            >
              <span>{config.icon}</span>
              <span>{config.label}</span>
            </div>
          );
        })}
      </div>

      {/* 消息流区域 */}
      <div className="bg-gray-50/50 rounded-2xl p-5 mb-6 min-h-[300px] max-h-[500px] overflow-y-auto border border-gray-100">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-gray-400">
            <Loading />
          </div>
        ) : (
          <>
            {messages.map((msg, i) => renderMessage(msg, i))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* 测试区域 */}
      {completed && !test && (
        <Card className="mb-6 text-center">
          <div className="text-4xl mb-3">📝</div>
          <h3 className="text-lg font-bold text-gray-800 mb-2">所有单元已学完</h3>
          <p className="text-sm text-gray-500 mb-4">完成测试来检验你的理解程度</p>
          <button
            onClick={handleRunTest}
            className="px-6 py-2.5 bg-gradient-to-r from-purple-500 to-violet-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-purple-500/25 transition-all"
          >
            开始测试
          </button>
        </Card>
      )}

      {test && (
        <Card className="mb-6">
          <h3 className="text-lg font-bold text-gray-800 mb-4">📝 理解测试</h3>

          {test.score !== null ? (
            /* 测试结果 */
            <div className="text-center py-6">
              <div className="text-5xl mb-3">
                {test.score >= 80 ? '🎉' : test.score >= 60 ? '👍' : '💪'}
              </div>
              <p className="text-3xl font-bold text-gray-800 mb-1">{test.score.toFixed(0)}分</p>
              <p className="text-sm text-gray-500 mb-4">
                {test.score >= 80 ? '优秀！你已经掌握了核心概念' : test.score >= 60 ? '不错！还有一些细节需要加强' : '继续努力！建议复习标记为不懂的内容'}
              </p>
              {test.weak_points.length > 0 && (
                <div className="text-left bg-amber-50 rounded-xl p-4 border border-amber-100">
                  <p className="text-xs font-semibold text-amber-600 mb-2">📌 薄弱点</p>
                  {test.weak_points.map((wp, i) => (
                    <p key={i} className="text-sm text-amber-700">{wp}</p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* 答题中 */
            <>
              {test.questions.map((q, i) => (
                <div key={i} className="mb-5 pb-5 border-b border-gray-100 last:border-0">
                  <p className="text-sm font-medium text-gray-800 mb-3">
                    <span className="text-blue-500 font-bold mr-1">{i + 1}.</span>
                    {q.question}
                  </p>

                  {q.question_type === 'choice' && q.options ? (
                    <div className="space-y-2">
                      {q.options.map((opt, j) => (
                        <button
                          key={j}
                          onClick={() => setTestAnswers((prev) => ({ ...prev, [i]: opt }))}
                          className={`w-full p-3 text-left rounded-xl border-2 transition-all text-sm ${
                            testAnswers[i] === opt
                              ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100'
                              : 'border-gray-100 hover:border-blue-200 hover:bg-blue-50/30'
                          }`}
                        >
                          <span className="font-medium text-gray-500 mr-2">
                            {String.fromCharCode(65 + j)}.
                          </span>
                          {opt}
                        </button>
                      ))}
                    </div>
                  ) : q.question_type === 'fill_blank' ? (
                    <input
                      type="text"
                      value={testAnswers[i] || ''}
                      onChange={(e) => setTestAnswers((prev) => ({ ...prev, [i]: e.target.value }))}
                      placeholder="请补充完整..."
                      className="w-full p-3 border-2 border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50"
                    />
                  ) : (
                    <textarea
                      value={testAnswers[i] || ''}
                      onChange={(e) => setTestAnswers((prev) => ({ ...prev, [i]: e.target.value }))}
                      placeholder="输入你的答案..."
                      rows={3}
                      className="w-full p-3 border-2 border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 resize-none"
                    />
                  )}
                </div>
              ))}

              <button
                onClick={handleSubmitTest}
                disabled={submittingTest || Object.keys(testAnswers).length < test.questions.length}
                className="w-full py-3 bg-gradient-to-r from-purple-500 to-violet-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-purple-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                {submittingTest ? '评分中...' : '提交答案'}
              </button>
            </>
          )}
        </Card>
      )}

      {/* 交互区域 */}
      {!completed && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          {/* 提问 */}
          <Card hover={false}>
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <span>❓</span> 提问
            </h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={questionInput}
                onChange={(e) => setQuestionInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()}
                placeholder="有不明白的地方？..."
                className="flex-1 p-2.5 border border-gray-100 rounded-xl text-sm text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50"
              />
              <button
                onClick={handleAskQuestion}
                disabled={asking || !questionInput.trim()}
                className="px-4 py-2 bg-blue-500 text-white rounded-xl text-xs font-medium hover:bg-blue-600 disabled:opacity-40 transition-colors"
              >
                发送
              </button>
            </div>
          </Card>

          {/* 笔记 */}
          <Card hover={false}>
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <span>📝</span> 笔记
            </h3>
            <textarea
              value={noteInput}
              onChange={(e) => setNoteInput(e.target.value)}
              placeholder="记录你的理解和思考..."
              rows={2}
              className="w-full p-2.5 border border-gray-100 rounded-xl text-sm text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 resize-none"
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={() => handleSaveNote('important')}
                disabled={savingNote || !noteInput.trim()}
                className="flex-1 px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg text-xs font-medium hover:bg-amber-100 disabled:opacity-40 transition-colors"
              >
                ⭐ 重要
              </button>
              <button
                onClick={() => handleSaveNote('confusing')}
                disabled={savingNote || !noteInput.trim()}
                className="flex-1 px-3 py-1.5 bg-red-50 text-red-600 rounded-lg text-xs font-medium hover:bg-red-100 disabled:opacity-40 transition-colors"
              >
                ❓ 不懂
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* 底部操作栏 */}
      <div className="flex justify-between items-center">
        <button
          onClick={() => navigate(`/books/${bookId}`)}
          className="px-4 py-2.5 text-gray-500 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors"
        >
          ← 退出教学
        </button>

        {test?.score !== null ? (
          <button
            onClick={handleFinishSession}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-green-500/25 transition-all"
          >
            ✓ 完成教学
          </button>
        ) : !completed ? (
          <button
            onClick={handleAdvance}
            disabled={advancing}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-50 transition-all"
          >
            {advancing ? '加载中...' : '继续 →'}
          </button>
        ) : null}
      </div>
    </div>
  );
}
