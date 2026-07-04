import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import KnowledgeGraphMini from '../components/KnowledgeGraphMini';
import {
  startTeachingSession, getNextTeachingMessage, askTeachingQuestion,
  addTeachingAnnotation, runTeachingTest,
  submitTeachingAnswers, completeTeachingSession, adaptTeachingStrategy,
  getActiveTeachingSession, getTeachingMessages,
  submitTeachingAnswer, jumpToUnit, clearSessionMessages,
  generateCornellCues, generateCornellSummary, getCornellNotes,
  continueToNextPhase,
} from '../api/teaching';
import { getAidActiveUnits } from '../api/aid';
import type {
  TeachingSession as TeachingSessionType,
  TeachingMessage, UserQuestion, SessionTest, TeachingPhase,
} from '../types/teaching';
import { PHASE_CONFIG } from '../types/teaching';

// 后端 API 前缀与学习会话相同，复用 books API 加载知识单元
import { getBookChapters } from '../api/books';
import type { Chapter, KnowledgeUnit } from '../types';

// 笔记类型定义
type NoteType = 'concept' | 'question' | 'connection' | 'application' | 'important' | 'confusing' | 'note' | 'quote' | 'story' | 'insight' | 'emotion' | 'action';

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
  const [viewingUnitId, setViewingUnitId] = useState<string>('');

  // UI 状态
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const advancingRef = useRef(false);
  const [questionInput, setQuestionInput] = useState('');
  const [asking, setAsking] = useState(false);
  const [answerInput, setAnswerInput] = useState('');
  const [submittingAnswer, setSubmittingAnswer] = useState(false);
  const [awaitingAnswer, setAwaitingAnswer] = useState(false);
  const [noteInput, setNoteInput] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  // 康奈尔笔记状态
  const [cornellMode, setCornellMode] = useState(false);
  const [cornellCues, setCornellCues] = useState<string[]>([]);
  const [cornellSummary, setCornellSummary] = useState('');
  const [generatingCues, setGeneratingCues] = useState(false);
  const [generatingSummary, setGeneratingSummary] = useState(false);

  // 测试状态
  const [test, setTest] = useState<SessionTest | null>(null);
  const [testAnswers, setTestAnswers] = useState<Record<number, string>>({});
  const [submittingTest, setSubmittingTest] = useState(false);

  // 会话完成
  const [completed, setCompleted] = useState(false);

  // 互动数据收集（用 ref 保持最新值，避免 useCallback 依赖问题）
  const [interactionData, setInteractionData] = useState({
    questions_asked: 0,
    confusing_marks: 0,
    response_times: [] as number[],
  });
  const interactionDataRef = useRef(interactionData);
  useEffect(() => { interactionDataRef.current = interactionData; }, [interactionData]);

  // 初始化：加载书籍章节和知识单元
  useEffect(() => {
    if (bookId) loadData();
  }, [bookId]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 切换单元时加载康奈尔笔记
  useEffect(() => {
    if (viewingUnitId && cornellMode) {
      loadCornellNotes(viewingUnitId);
    }
  }, [viewingUnitId, cornellMode]);

  const loadData = async () => {
    try {
      const data = await getBookChapters(bookId!);
      setChapters(data);
      const allUnits = data.flatMap((c) => c.knowledge_units || []);
      setUnits(allUnits);
      if (allUnits.length > 0) {
        // 优先尝试恢复活跃会话
        try {
          const activeSession = await getActiveTeachingSession(bookId!);
          if (activeSession) {
            setSession(activeSession);
            setCurrentPhase(activeSession.current_phase);
            setViewingUnitId(activeSession.unit_ids[activeSession.current_unit_index] || '');
            // 恢复消息历史
            const historyMessages = await getTeachingMessages(activeSession.id);
            setMessages(historyMessages);
            localStorage.setItem(`teaching_session_${bookId}`, activeSession.id);
            return;
          }
        } catch {
          // 404 表示没有活跃会话，继续创建新会话
        }
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
      let orderedUnits = unitList;
      try {
        const active = await getAidActiveUnits(bookId!);
        if (active.unit_ids.length > 0) {
          const byId = new Map(unitList.map((unit) => [unit.id, unit]));
          const designedUnits = active.unit_ids.map((id) => byId.get(id)).filter(Boolean) as KnowledgeUnit[];
          if (designedUnits.length > 0) {
            orderedUnits = designedUnits;
            setUnits(designedUnits);
          }
        }
      } catch {
        // 未生成 AID 时继续使用原章节顺序。
      }
      const unitIds = orderedUnits.map((u) => u.id);
      const sess = await startTeachingSession(bookId!, unitIds);
      setSession(sess);
      setCurrentPhase(sess.current_phase);
      setViewingUnitId(sess.unit_ids[0] || '');
      localStorage.setItem(`teaching_session_${bookId}`, sess.id);
      // 自动获取第一条消息
      await advanceMessage(sess.id);
    } catch (error) {
      console.error('开始教学会话失败:', error);
    }
  };

  const advanceMessage = async (sessionId: string) => {
    const data = interactionDataRef.current;
    try {
      // 在获取新消息前，根据互动数据调整策略
      if (data.questions_asked > 0 || data.confusing_marks > 0) {
        const avgResponseTime = data.response_times.length > 0
          ? data.response_times.reduce((a, b) => a + b, 0) / data.response_times.length
          : 0;

        await adaptTeachingStrategy(sessionId, {
          questions_asked: data.questions_asked,
          confusing_marks: data.confusing_marks,
          avg_response_time: avgResponseTime,
        });
      }

      const msg = await getNextTeachingMessage(sessionId);
      setMessages((prev) => [...prev, msg]);
      // 切换到新消息所在的单元视图
      if (msg.unit_id) {
        setViewingUnitId(msg.unit_id);
      }

      if (msg.requires_answer) {
        // 交互型阶段：等待学生回答
        setAwaitingAnswer(true);
        setCurrentPhase(msg.phase);
      } else {
        // 展示型阶段：自动推进
        setAwaitingAnswer(false);
        setCurrentPhase(msg.next_phase || msg.phase);
      }
    } catch (error: unknown) {
      const errMsg = error instanceof Error ? error.message : '';
      if (errMsg.includes('所有单元已学完')) {
        setCompleted(true);
      } else {
        console.error('获取消息失败:', error);
      }
    }
  };

  const handleAdvance = async () => {
    if (!session || advancingRef.current) return;
    advancingRef.current = true;
    setAdvancing(true);
    try {
      // 先推进到下一阶段，再获取新阶段的消息
      const updatedSession = await continueToNextPhase(session.id);
      setSession(updatedSession);
      setCurrentPhase(updatedSession.current_phase);
      await advanceMessage(session.id);
    } finally {
      advancingRef.current = false;
      setAdvancing(false);
    }
  };

  const handleAskQuestion = async () => {
    if (!session || !questionInput.trim() || asking) return;
    setAsking(true);
    const startTime = Date.now();
    try {
      const result = await askTeachingQuestion(session.id, questionInput.trim());
      const responseTime = (Date.now() - startTime) / 1000;

      // 更新互动数据
      setInteractionData((prev) => ({
        ...prev,
        questions_asked: prev.questions_asked + 1,
        response_times: [...prev.response_times, responseTime],
      }));

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

  const handleSubmitAnswer = async () => {
    if (!session || !answerInput.trim() || submittingAnswer) return;
    setSubmittingAnswer(true);
    try {
      // 把学生回答加入消息流
      setMessages((prev) => [
        ...prev,
        {
          id: `user-answer-${Date.now()}`,
          session_id: session.id,
          unit_id: '',
          phase: currentPhase as TeachingMessage['phase'],
          content: `📝 ${answerInput.trim()}`,
          content_type: 'text',
          created_at: new Date().toISOString(),
        },
      ]);
      setAnswerInput('');

      // 调用后端评估
      const result = await submitTeachingAnswer(session.id, answerInput.trim());
      setMessages((prev) => [...prev, result]);
      setAwaitingAnswer(false);

      // 如果 AI 评估通过，更新阶段（用户手动点"继续"推进）
      if (result.assessment?.should_advance !== false) {
        setCurrentPhase(result.next_phase || currentPhase);
      } else {
        // 未通过，保持当前阶段等待再次回答
        setAwaitingAnswer(true);
      }
    } catch (error) {
      console.error('提交回答失败:', error);
    } finally {
      setSubmittingAnswer(false);
    }
  };

  const handleJumpToUnit = async (unitId: string) => {
    if (!session) return;
    try {
      const updatedSession = await jumpToUnit(session.id, unitId);
      setSession(updatedSession);
      setCurrentPhase(updatedSession.current_phase);
      setViewingUnitId(unitId);
      setAwaitingAnswer(false);
      // 获取跳转后的消息
      await advanceMessage(updatedSession.id);
    } catch (error) {
      console.error('跳转失败:', error);
    }
  };

  const handleClearMessages = async () => {
    if (!session) return;
    try {
      const updatedSession = await clearSessionMessages(session.id);
      setSession(updatedSession);
      setCurrentPhase(updatedSession.current_phase);
      setMessages([]);
      setAwaitingAnswer(false);
    } catch (error) {
      console.error('清空消息失败:', error);
    }
  };

  const handleSaveNote = async (type: NoteType) => {
    if (!session || !noteInput.trim()) return;
    setSavingNote(true);
    try {
      // 找到当前消息对应的 unit_id
      const currentMsg = messages[messages.length - 1];
      if (currentMsg) {
        await addTeachingAnnotation(
          currentMsg.unit_id, type, noteInput.trim(),
        );
      }

      // 如果是"不懂"标记，更新互动数据
      if (type === 'confusing') {
        setInteractionData((prev) => ({
          ...prev,
          confusing_marks: prev.confusing_marks + 1,
        }));
      }

      setNoteInput('');
    } catch (error) {
      console.error('保存笔记失败:', error);
    } finally {
      setSavingNote(false);
    }
  };

  const handleGenerateCues = async () => {
    if (!noteInput.trim()) return;
    const unitId = viewingUnitId || messages[messages.length - 1]?.unit_id;
    if (!unitId) return;
    setGeneratingCues(true);
    try {
      const result = await generateCornellCues(unitId, noteInput.trim());
      setCornellCues(result.cues);
    } catch (error) {
      console.error('生成线索失败:', error);
    } finally {
      setGeneratingCues(false);
    }
  };

  const handleGenerateSummary = async () => {
    if (!noteInput.trim()) return;
    const unitId = viewingUnitId || messages[messages.length - 1]?.unit_id;
    if (!unitId) return;
    setGeneratingSummary(true);
    try {
      const result = await generateCornellSummary(unitId, noteInput.trim());
      setCornellSummary(result.summary);
    } catch (error) {
      console.error('生成总结失败:', error);
    } finally {
      setGeneratingSummary(false);
    }
  };

  const handleSaveCornell = async () => {
    if (!session || !noteInput.trim()) return;
    setSavingNote(true);
    try {
      const unitId = viewingUnitId || messages[messages.length - 1]?.unit_id;
      if (unitId) {
        await addTeachingAnnotation(
          unitId, 'cornell_note', noteInput.trim(),
          undefined, undefined,
          cornellCues.length > 0 ? cornellCues : undefined,
          cornellSummary || undefined,
        );
      }
      setNoteInput('');
      setCornellCues([]);
      setCornellSummary('');
    } catch (error) {
      console.error('保存康奈尔笔记失败:', error);
    } finally {
      setSavingNote(false);
    }
  };

  const loadCornellNotes = async (unitId: string) => {
    try {
      const notes = await getCornellNotes(unitId);
      if (notes && notes.length > 0) {
        const latest = notes[0];
        setCornellCues(latest.cues || []);
        setCornellSummary(latest.summary || '');
        if (latest.notes) setNoteInput(latest.notes);
      } else {
        setCornellCues([]);
        setCornellSummary('');
      }
    } catch {
      // 笔记不存在，忽略
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
      localStorage.removeItem(`teaching_session_${bookId}`);
      navigate(`/books/${bookId}`);
    } catch (error) {
      console.error('完成会话失败:', error);
    }
  };

  // ---- 渲染辅助 ----

  // 学习路径可视化
  const renderLearningPath = () => {
    if (units.length <= 1) return null;

    return (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">学习路径</h3>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {units.map((unit, index) => {
            const isCompleted = index < currentUnitIndex;
            const isCurrent = index === currentUnitIndex;
            const isViewing = unit.id === viewingUnitId;

            return (
              <div key={unit.id} className="flex items-center">
                <button
                  onClick={() => {
                    setViewingUnitId(unit.id);
                    if (index !== currentUnitIndex) handleJumpToUnit(unit.id);
                  }}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium shrink-0 cursor-pointer hover:ring-2 hover:ring-blue-200 transition-all ${
                    isViewing
                      ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-300'
                      : isCompleted
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  <span className="w-5 h-5 flex items-center justify-center rounded-full bg-white text-xs font-bold">
                    {isCompleted ? '✓' : index + 1}
                  </span>
                  <span className="max-w-[100px] truncate">{unit.title || `单元${index + 1}`}</span>
                </button>
                {index < units.length - 1 && (
                  <div className={`w-6 h-0.5 ${isCompleted ? 'bg-green-300' : 'bg-gray-200'}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const getPhaseColor = (phase: string) => {
    const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG];
    if (!config) return 'gray';
    return config.color;
  };

  const getPhaseLabel = (phase: string) => {
    const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG];
    return config ? `${config.icon} ${config.label}` : phase;
  };

  // 计算进度（基于阶段推进而非消息数量）
  const totalUnits = units.length;
  const currentUnitIndex = session?.current_unit_index ?? 0;
  const strategyPhases = session?.strategy?.phases || ['activate', 'intro', 'core', 'check', 'reflect', 'connect'];
  const phasesPerUnit = strategyPhases.length;
  const totalSteps = totalUnits * phasesPerUnit;
  // 已完成的步骤 = 已完成的单元数 * 每单元阶段数 + 当前单元中已完成的阶段数
  const currentPhaseIndex = strategyPhases.indexOf(currentPhase as TeachingPhase);
  const completedSteps = currentUnitIndex * phasesPerUnit + (currentPhaseIndex >= 0 ? currentPhaseIndex : 0);
  const progressPercent = totalSteps > 0 ? Math.min(Math.round((completedSteps / totalSteps) * 100), 100) : 0;

  // 按当前查看的单元过滤消息
  const unitMessages = viewingUnitId
    ? messages.filter((m) => m.unit_id === viewingUnitId)
    : messages;

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
    const isStudentAnswer = msg.content.startsWith('📝');

    if (isQuestion) {
      return (
        <div key={msg.id} className="flex justify-end mb-4 animate-fade-in">
          <div className="max-w-[70%] bg-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-3 shadow-sm">
            <p className="text-sm leading-relaxed">{msg.content.slice(2)}</p>
          </div>
        </div>
      );
    }

    if (isStudentAnswer) {
      return (
        <div key={msg.id} className="flex justify-end mb-4 animate-fade-in">
          <div className="max-w-[70%] bg-green-500 text-white rounded-2xl rounded-br-sm px-4 py-3 shadow-sm">
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
      {/* 学习路径 */}
      {renderLearningPath()}

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

      {/* 阶段进度指示器（只显示策略中包含的阶段） */}
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-2">
        {strategyPhases.map((phase) => {
          const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG];
          if (!config) return null;
          const isActive = currentPhase === phase;
          const currentOrder = strategyPhases.indexOf(currentPhase as TeachingPhase);
          const thisOrder = strategyPhases.indexOf(phase);
          const isPast = thisOrder < currentOrder;

          return (
            <div
              key={phase}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium shrink-0 transition-all ${isActive
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

      {/* 消息流区域（按当前查看的单元过滤） */}
      <div className="bg-gray-50/50 rounded-2xl mb-6 border border-gray-100">
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <span className="text-xs font-semibold text-gray-400">
            {(() => {
              const viewingUnit = units.find((u) => u.id === viewingUnitId);
              return viewingUnit?.title || `单元 ${units.findIndex((u) => u.id === viewingUnitId) + 1}`;
            })()}
          </span>
          <div className="flex items-center gap-3">
            {/* 单元切换下拉 */}
            <select
              value={viewingUnitId}
              onChange={(e) => setViewingUnitId(e.target.value)}
              className="text-xs text-gray-500 bg-transparent border-none outline-none cursor-pointer"
            >
              {units.map((u, i) => (
                <option key={u.id} value={u.id}>
                  {u.title || `单元 ${i + 1}`}
                </option>
              ))}
            </select>
            {unitMessages.length > 0 && (
              <button
                onClick={handleClearMessages}
                className="text-xs text-gray-400 hover:text-red-500 transition-colors"
              >
                清空记录
              </button>
            )}
          </div>
        </div>
        <div className="px-5 pb-5 min-h-[250px] max-h-[460px] overflow-y-auto">
          {unitMessages.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
              点击"继续"开始学习
            </div>
          ) : (
            <>
              {unitMessages.map((msg, i) => renderMessage(msg, i))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </div>

      {/* 浮动"继续"按钮（消息区域下方，交互区域上方，右对齐） */}
      {!completed && !awaitingAnswer && !(test && test.score !== null) && (
        <div className="flex justify-end mb-4">
          <button
            onClick={handleAdvance}
            disabled={advancing}
            className="flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-full text-sm font-medium shadow-lg shadow-blue-500/30 hover:shadow-xl hover:shadow-blue-500/40 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 transition-all"
          >
            {advancing ? '...' : '继续 →'}
          </button>
        </div>
      )}

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
                          className={`w-full p-3 text-left rounded-xl border-2 transition-all text-sm ${testAnswers[i] === opt
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
                  ) : q.question_type === 'true_false' ? (
                    /* 判断题 */
                    <div>
                      {q.statement && (
                        <div className="mb-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
                          <p className="text-sm text-gray-700">{q.statement}</p>
                        </div>
                      )}
                      <div className="flex gap-3">
                        {(q.options || ['正确', '错误']).map((opt, j) => (
                          <button
                            key={j}
                            onClick={() => setTestAnswers((prev) => ({ ...prev, [i]: opt }))}
                            className={`flex-1 p-3 text-center rounded-xl border-2 transition-all text-sm font-medium ${testAnswers[i] === opt
                                ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100'
                                : 'border-gray-100 hover:border-blue-200 hover:bg-blue-50/30'
                              }`}
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : q.question_type === 'matching' && q.pairs ? (
                    /* 连线题 */
                    <div className="space-y-2">
                      <p className="text-xs text-gray-500 mb-2">请将左侧概念与右侧定义对应（输入配对编号，如 1A 2B 3C）</p>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <p className="text-xs font-semibold text-gray-500 mb-2">概念</p>
                          {q.pairs.map((pair, j) => (
                            <div key={j} className="p-2 bg-blue-50 rounded-lg text-sm text-blue-700 mb-1.5">
                              {j + 1}. {pair.left}
                            </div>
                          ))}
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-gray-500 mb-2">定义</p>
                          {q.pairs.map((pair, j) => (
                            <div key={j} className="p-2 bg-purple-50 rounded-lg text-sm text-purple-700 mb-1.5">
                              {String.fromCharCode(65 + j)}. {pair.right}
                            </div>
                          ))}
                        </div>
                      </div>
                      <input
                        type="text"
                        value={testAnswers[i] || ''}
                        onChange={(e) => setTestAnswers((prev) => ({ ...prev, [i]: e.target.value }))}
                        placeholder="输入配对结果，如：1B 2A 3C 4D"
                        className="w-full p-3 border-2 border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50"
                      />
                    </div>
                  ) : q.question_type === 'ordering' && q.options ? (
                    /* 排序题 */
                    <div className="space-y-2">
                      <p className="text-xs text-gray-500 mb-2">请将以下步骤排列为正确顺序（点击上下箭头调整）</p>
                      {(() => {
                        const currentOrder: string[] = testAnswers[i]
                          ? JSON.parse(testAnswers[i])
                          : q.options || [];
                        const moveItem = (fromIdx: number, direction: -1 | 1) => {
                          const toIdx = fromIdx + direction;
                          if (toIdx < 0 || toIdx >= currentOrder.length) return;
                          const newOrder = [...currentOrder];
                          [newOrder[fromIdx], newOrder[toIdx]] = [newOrder[toIdx], newOrder[fromIdx]];
                          setTestAnswers((prev) => ({ ...prev, [i]: JSON.stringify(newOrder) }));
                        };
                        return currentOrder.map((step, j) => (
                          <div key={j} className="flex items-center gap-2 p-2.5 bg-gray-50 rounded-xl border border-gray-100">
                            <span className="text-xs font-bold text-blue-500 w-6 text-center">{j + 1}</span>
                            <span className="flex-1 text-sm text-gray-700">{step}</span>
                            <div className="flex gap-1">
                              <button
                                onClick={() => moveItem(j, -1)}
                                disabled={j === 0}
                                className="w-6 h-6 flex items-center justify-center rounded text-xs text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-30"
                              >
                                ▲
                              </button>
                              <button
                                onClick={() => moveItem(j, 1)}
                                disabled={j === currentOrder.length - 1}
                                className="w-6 h-6 flex items-center justify-center rounded text-xs text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-30"
                              >
                                ▼
                              </button>
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
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

      {/* 回答区域（交互型阶段显示） */}
      {!completed && awaitingAnswer && (
        <Card className="mb-6 border-2 border-green-200 bg-green-50/30">
          <h3 className="text-sm font-semibold text-green-700 mb-3 flex items-center gap-2">
            <span>{currentPhase === 'feynman' ? '🧠' : '✍️'}</span>
            {currentPhase === 'feynman' ? '请用自己的话解释刚才学到的内容' : '请回答问题'}
          </h3>
          <textarea
            value={answerInput}
            onChange={(e) => setAnswerInput(e.target.value)}
            placeholder={currentPhase === 'feynman' ? '用你自己的话解释这个知识点，不要照搬原文...' : '输入你的回答...'}
            rows={3}
            className="w-full p-3 border-2 border-green-200 rounded-xl text-sm text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-100 bg-white resize-none"
          />
          <div className="flex justify-end mt-3">
            <button
              onClick={handleSubmitAnswer}
              disabled={submittingAnswer || !answerInput.trim()}
              className="px-6 py-2 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-green-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {submittingAnswer ? '评估中...' : '提交回答'}
            </button>
          </div>
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
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <span>📝</span> {cornellMode ? '康奈尔笔记' : '笔记'}
              </h3>
              <button
                onClick={() => setCornellMode(!cornellMode)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                  cornellMode
                    ? 'bg-purple-100 text-purple-700'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                {cornellMode ? '标准模式' : '康奈尔模式'}
              </button>
            </div>

            {cornellMode ? (
              /* 康奈尔笔记三栏布局 */
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  {/* 线索栏 */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-purple-600">线索栏</span>
                      <button
                        onClick={handleGenerateCues}
                        disabled={generatingCues || !noteInput.trim()}
                        className="text-[10px] text-purple-500 hover:text-purple-700 disabled:opacity-40"
                      >
                        {generatingCues ? '生成中...' : 'AI 生成'}
                      </button>
                    </div>
                    <div className="min-h-[80px] p-2 border border-purple-200 rounded-lg bg-purple-50/50 text-xs text-gray-600">
                      {cornellCues.length > 0 ? (
                        cornellCues.map((cue, i) => (
                          <p key={i} className="mb-1">- {cue}</p>
                        ))
                      ) : (
                        <p className="text-gray-400">点击 AI 生成或手动输入</p>
                      )}
                    </div>
                  </div>

                  {/* 笔记栏 */}
                  <div>
                    <span className="text-xs font-semibold text-blue-600 mb-1 block">笔记栏</span>
                    <textarea
                      value={noteInput}
                      onChange={(e) => setNoteInput(e.target.value)}
                      placeholder="记录笔记..."
                      rows={4}
                      className="w-full p-2 border border-blue-200 rounded-lg text-xs text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-400 bg-blue-50/50 resize-none"
                    />
                  </div>

                  {/* 总结栏 */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-green-600">总结栏</span>
                      <button
                        onClick={handleGenerateSummary}
                        disabled={generatingSummary || !noteInput.trim()}
                        className="text-[10px] text-green-500 hover:text-green-700 disabled:opacity-40"
                      >
                        {generatingSummary ? '生成中...' : 'AI 生成'}
                      </button>
                    </div>
                    <div className="min-h-[80px] p-2 border border-green-200 rounded-lg bg-green-50/50 text-xs text-gray-600">
                      {cornellSummary || <span className="text-gray-400">点击 AI 生成或手动输入</span>}
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleSaveCornell}
                  disabled={savingNote || !noteInput.trim()}
                  className="w-full py-2 bg-gradient-to-r from-purple-500 to-violet-500 text-white rounded-lg text-xs font-medium hover:shadow-lg hover:shadow-purple-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  {savingNote ? '保存中...' : '保存康奈尔笔记'}
                </button>
              </div>
            ) : (
              /* 标准笔记模式 */
              <>
                <textarea
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="记录你的理解和思考..."
                  rows={2}
                  className="w-full p-2.5 border border-gray-100 rounded-xl text-sm text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 resize-none"
                />
                <div className="grid grid-cols-5 gap-2 mt-2">
                  <button onClick={() => handleSaveNote('concept')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium hover:bg-blue-100 disabled:opacity-40 transition-colors">概念</button>
                  <button onClick={() => handleSaveNote('quote')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-pink-50 text-pink-700 rounded-lg text-xs font-medium hover:bg-pink-100 disabled:opacity-40 transition-colors">金句</button>
                  <button onClick={() => handleSaveNote('story')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-teal-50 text-teal-700 rounded-lg text-xs font-medium hover:bg-teal-100 disabled:opacity-40 transition-colors">故事</button>
                  <button onClick={() => handleSaveNote('insight')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-violet-50 text-violet-700 rounded-lg text-xs font-medium hover:bg-violet-100 disabled:opacity-40 transition-colors">洞见</button>
                  <button onClick={() => handleSaveNote('action')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-cyan-50 text-cyan-700 rounded-lg text-xs font-medium hover:bg-cyan-100 disabled:opacity-40 transition-colors">行动</button>
                </div>
                <div className="grid grid-cols-5 gap-2 mt-2">
                  <button onClick={() => handleSaveNote('question')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-purple-50 text-purple-700 rounded-lg text-xs font-medium hover:bg-purple-100 disabled:opacity-40 transition-colors">问题</button>
                  <button onClick={() => handleSaveNote('connection')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-green-50 text-green-700 rounded-lg text-xs font-medium hover:bg-green-100 disabled:opacity-40 transition-colors">联系</button>
                  <button onClick={() => handleSaveNote('application')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-orange-50 text-orange-700 rounded-lg text-xs font-medium hover:bg-orange-100 disabled:opacity-40 transition-colors">应用</button>
                  <button onClick={() => handleSaveNote('important')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-amber-50 text-amber-700 rounded-lg text-xs font-medium hover:bg-amber-100 disabled:opacity-40 transition-colors">重要</button>
                  <button onClick={() => handleSaveNote('confusing')} disabled={savingNote || !noteInput.trim()}
                    className="px-2 py-1.5 bg-red-50 text-red-600 rounded-lg text-xs font-medium hover:bg-red-100 disabled:opacity-40 transition-colors">不懂</button>
                </div>
              </>
            )}
          </Card>
        </div>
      )}

      {/* 知识图谱迷你视图（底部） */}
      {!completed && bookId && messages.length > 0 && (
        <div className="mb-6">
          <KnowledgeGraphMini
            bookId={bookId}
            highlightUnitId={messages[messages.length - 1]?.unit_id}
            showRelated={true}
          />
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

        {test && test.score !== null ? (
          <button
            onClick={handleFinishSession}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-green-500/25 transition-all"
          >
            ✓ 完成教学
          </button>
        ) : !completed ? (
          <button
            onClick={handleAdvance}
            disabled={advancing || awaitingAnswer}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-50 transition-all"
          >
            {awaitingAnswer ? '请先回答问题' : advancing ? '加载中...' : '继续 →'}
          </button>
        ) : null}
      </div>
    </div>
  );
}
