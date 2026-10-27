import pathlib

# TeachingSession.tsx - refactored with extracted components
content = r'''import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import ProgressBar from '../components/ProgressBar';
import KnowledgeGraphMini from '../components/KnowledgeGraphMini';
import Icon from '../components/ui/Icon';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import MessageBubble from '../components/teaching/MessageBubble';
import LearningPath from '../components/teaching/LearningPath';
import TestPanel from '../components/teaching/TestPanel';
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
  TeachingMessage, TeachingPhase,
} from '../types/teaching';
import { PHASE_CONFIG } from '../types/teaching';
import { getBookChapters } from '../api/books';
import type { Chapter, KnowledgeUnit } from '../types';

type NoteType = 'concept' | 'question' | 'connection' | 'application' | 'important' | 'confusing' | 'note' | 'quote' | 'story' | 'insight' | 'emotion' | 'action';

export default function TeachingSession() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [units, setUnits] = useState<KnowledgeUnit[]>([]);
  const [session, setSession] = useState<TeachingSessionType | null>(null);
  const [messages, setMessages] = useState<TeachingMessage[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string>('activate');
  const [viewingUnitId, setViewingUnitId] = useState<string>('');
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
  const [cornellMode, setCornellMode] = useState(false);
  const [cornellCues, setCornellCues] = useState<string[]>([]);
  const [cornellSummary, setCornellSummary] = useState('');
  const [generatingCues, setGeneratingCues] = useState(false);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [test, setTest] = useState(null);
  const [testAnswers, setTestAnswers] = useState<Record<number, string>>({});
  const [submittingTest, setSubmittingTest] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [interactionData, setInteractionData] = useState({
    questions_asked: 0, confusing_marks: 0, response_times: [] as number[],
  });
  const interactionDataRef = useRef(interactionData);
  useEffect(() => { interactionDataRef.current = interactionData; }, [interactionData]);

  useEffect(() => { if (bookId) loadData(); }, [bookId]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { if (viewingUnitId && cornellMode) loadCornellNotes(viewingUnitId); }, [viewingUnitId, cornellMode]);

  const loadData = async () => {
    try {
      const data = await getBookChapters(bookId!);
      setChapters(data);
      const allUnits = data.flatMap((c) => c.knowledge_units || []);
      setUnits(allUnits);
      if (allUnits.length > 0) {
        try {
          const activeSession = await getActiveTeachingSession(bookId!);
          if (activeSession) {
            setSession(activeSession);
            setCurrentPhase(activeSession.current_phase);
            setViewingUnitId(activeSession.unit_ids[activeSession.current_unit_index] || '');
            const historyMessages = await getTeachingMessages(activeSession.id);
            setMessages(historyMessages);
            localStorage.setItem(`teaching_session_${bookId}`, activeSession.id);
            return;
          }
        } catch { /* 404 表示没有活跃会话 */ }
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
          if (designedUnits.length > 0) { orderedUnits = designedUnits; setUnits(designedUnits); }
        }
      } catch { /* 未生成 AID */ }
      const unitIds = orderedUnits.map((u) => u.id);
      const sess = await startTeachingSession(bookId!, unitIds);
      setSession(sess); setCurrentPhase(sess.current_phase); setViewingUnitId(sess.unit_ids[0] || '');
      localStorage.setItem(`teaching_session_${bookId}`, sess.id);
      await advanceMessage(sess.id);
    } catch (error) { console.error('开始教学会话失败:', error); }
  };

  const advanceMessage = async (sessionId: string) => {
    const data = interactionDataRef.current;
    try {
      if (data.questions_asked > 0 || data.confusing_marks > 0) {
        const avgResponseTime = data.response_times.length > 0
          ? data.response_times.reduce((a, b) => a + b, 0) / data.response_times.length : 0;
        await adaptTeachingStrategy(sessionId, {
          questions_asked: data.questions_asked, confusing_marks: data.confusing_marks, avg_response_time: avgResponseTime,
        });
      }
      const msg = await getNextTeachingMessage(sessionId);
      setMessages((prev) => [...prev, msg]);
      if (msg.unit_id) setViewingUnitId(msg.unit_id);
      if (msg.requires_answer) { setAwaitingAnswer(true); setCurrentPhase(msg.phase); }
      else { setAwaitingAnswer(false); setCurrentPhase(msg.next_phase || msg.phase); }
    } catch (error: unknown) {
      const errMsg = error instanceof Error ? error.message : '';
      if (errMsg.includes('所有单元已学完')) setCompleted(true);
      else console.error('获取消息失败:', error);
    }
  };

  const handleAdvance = async () => {
    if (!session || advancingRef.current) return;
    advancingRef.current = true; setAdvancing(true);
    try {
      const updatedSession = await continueToNextPhase(session.id);
      setSession(updatedSession); setCurrentPhase(updatedSession.current_phase);
      await advanceMessage(session.id);
    } finally { advancingRef.current = false; setAdvancing(false); }
  };

  const handleAskQuestion = async () => {
    if (!session || !questionInput.trim() || asking) return;
    setAsking(true);
    const startTime = Date.now();
    try {
      const result = await askTeachingQuestion(session.id, questionInput.trim());
      const responseTime = (Date.now() - startTime) / 1000;
      setInteractionData((prev) => ({
        ...prev, questions_asked: prev.questions_asked + 1,
        response_times: [...prev.response_times, responseTime],
      }));
      setMessages((prev) => [...prev,
        { id: `q-${result.id}`, session_id: session.id, unit_id: '', phase: currentPhase as TeachingMessage['phase'], content: `❓ ${result.question}`, content_type: 'text', created_at: result.asked_at },
        { id: `a-${result.id}`, session_id: session.id, unit_id: '', phase: currentPhase as TeachingMessage['phase'], content: `💬 ${result.answer}`, content_type: 'text', created_at: result.asked_at },
      ]);
      setQuestionInput('');
    } catch (error) { console.error('提问失败:', error); }
    finally { setAsking(false); }
  };

  const handleSubmitAnswer = async () => {
    if (!session || !answerInput.trim() || submittingAnswer) return;
    setSubmittingAnswer(true);
    try {
      setMessages((prev) => [...prev,
        { id: `user-answer-${Date.now()}`, session_id: session.id, unit_id: '', phase: currentPhase as TeachingMessage['phase'], content: `📝 ${answerInput.trim()}`, content_type: 'text', created_at: new Date().toISOString() },
      ]);
      setAnswerInput('');
      const result = await submitTeachingAnswer(session.id, answerInput.trim());
      setMessages((prev) => [...prev, result]);
      setAwaitingAnswer(false);
      if (result.assessment?.should_advance !== false) setCurrentPhase(result.next_phase || currentPhase);
      else setAwaitingAnswer(true);
    } catch (error) { console.error('提交回答失败:', error); }
    finally { setSubmittingAnswer(false); }
  };

  const handleJumpToUnit = async (unitId: string) => {
    if (!session) return;
    try {
      const updatedSession = await jumpToUnit(session.id, unitId);
      setSession(updatedSession); setCurrentPhase(updatedSession.current_phase);
      setViewingUnitId(unitId); setAwaitingAnswer(false);
      await advanceMessage(updatedSession.id);
    } catch (error) { console.error('跳转失败:', error); }
  };

  const handleClearMessages = async () => {
    if (!session) return;
    try {
      const updatedSession = await clearSessionMessages(session.id);
      setSession(updatedSession); setCurrentPhase(updatedSession.current_phase);
      setMessages([]); setAwaitingAnswer(false);
    } catch (error) { console.error('清空消息失败:', error); }
  };

  const handleSaveNote = async (type: NoteType) => {
    if (!session || !noteInput.trim()) return;
    setSavingNote(true);
    try {
      const currentMsg = messages[messages.length - 1];
      if (currentMsg) await addTeachingAnnotation(currentMsg.unit_id, type, noteInput.trim());
      if (type === 'confusing') setInteractionData((prev) => ({ ...prev, confusing_marks: prev.confusing_marks + 1 }));
      setNoteInput('');
    } catch (error) { console.error('保存笔记失败:', error); }
    finally { setSavingNote(false); }
  };

  const handleGenerateCues = async () => {
    if (!noteInput.trim()) return;
    const unitId = viewingUnitId || messages[messages.length - 1]?.unit_id;
    if (!unitId) return;
    setGeneratingCues(true);
    try { const result = await generateCornellCues(unitId, noteInput.trim()); setCornellCues(result.cues); }
    catch (error) { console.error('生成线索失败:', error); }
    finally { setGeneratingCues(false); }
  };

  const handleGenerateSummary = async () => {
    if (!noteInput.trim()) return;
    const unitId = viewingUnitId || messages[messages.length - 1]?.unit_id;
    if (!unitId) return;
    setGeneratingSummary(true);
    try { const result = await generateCornellSummary(unitId, noteInput.trim()); setCornellSummary(result.summary); }
    catch (error) { console.error('生成总结失败:', error); }
    finally { setGeneratingSummary(false); }
  };

  const handleSaveCornell = async () => {
    if (!session || !noteInput.trim()) return;
    setSavingNote(true);
    try {
      const unitId = viewingUnitId || messages[messages.length - 1]?.unit_id;
      if (unitId) await addTeachingAnnotation(unitId, 'cornell_note', noteInput.trim(), undefined, undefined, cornellCues.length > 0 ? cornellCues : undefined, cornellSummary || undefined);
      setNoteInput(''); setCornellCues([]); setCornellSummary('');
    } catch (error) { console.error('保存康奈尔笔记失败:', error); }
    finally { setSavingNote(false); }
  };

  const loadCornellNotes = async (unitId: string) => {
    try {
      const notes = await getCornellNotes(unitId);
      if (notes && notes.length > 0) {
        const latest = notes[0];
        setCornellCues(latest.cues || []); setCornellSummary(latest.summary || '');
        if (latest.notes) setNoteInput(latest.notes);
      } else { setCornellCues([]); setCornellSummary(''); }
    } catch { /* 笔记不存在 */ }
  };

  const handleRunTest = async () => {
    if (!session) return;
    try { const testResult = await runTeachingTest(session.id); setTest(testResult); setTestAnswers({}); }
    catch (error) { console.error('运行测试失败:', error); }
  };

  const handleSubmitTest = async (answers: Record<number, string>) => {
    if (!test || submittingTest) return;
    setSubmittingTest(true);
    try {
      const answerList = test.questions.map((_, i) => answers[i] || '');
      const result = await submitTeachingAnswers(test.id, answerList);
      setTest(result);
    } catch (error) { console.error('提交测试失败:', error); }
    finally { setSubmittingTest(false); }
  };

  const handleFinishSession = async () => {
    if (!session) return;
    try {
      const testScore = test?.score ?? undefined;
      await completeTeachingSession(session.id, {
        questions_asked: messages.filter((m) => m.content.startsWith('❓')).length, test_score: testScore,
      });
      localStorage.removeItem(`teaching_session_${bookId}`);
      navigate(`/books/${bookId}`);
    } catch (error) { console.error('完成会话失败:', error); }
  };

  const getPhaseLabel = (phase: string) => {
    const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG];
    return config ? `${config.icon} ${config.label}` : phase;
  };

  const totalUnits = units.length;
  const currentUnitIndex = session?.current_unit_index ?? 0;
  const strategyPhases = session?.strategy?.phases || ['activate', 'intro', 'core', 'check', 'reflect', 'connect'];
  const phasesPerUnit = strategyPhases.length;
  const totalSteps = totalUnits * phasesPerUnit;
  const currentPhaseIndex = strategyPhases.indexOf(currentPhase as TeachingPhase);
  const completedSteps = currentUnitIndex * phasesPerUnit + (currentPhaseIndex >= 0 ? currentPhaseIndex : 0);
  const progressPercent = totalSteps > 0 ? Math.min(Math.round((completedSteps / totalSteps) * 100), 100) : 0;
  const unitMessages = viewingUnitId ? messages.filter((m) => m.unit_id === viewingUnitId) : messages;

  if (loading) return <div className="max-w-4xl mx-auto"><div className="h-8 w-48 bg-gray-100 rounded-lg animate-pulse mb-4" /><div className="h-96 bg-gray-100 rounded-2xl animate-pulse" /></div>;

  if (units.length === 0) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card hover={false}>
          <EmptyState icon="academicCap" title="没有可教学的内容" description="请先上传书籍并进行知识拆分"
            action={<Button onClick={() => navigate(`/books/${bookId}`)}>返回书籍详情</Button>} />
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <LearningPath units={units} viewingUnitId={viewingUnitId} currentUnitIndex={currentUnitIndex} onViewUnit={setViewingUnitId} onJumpToUnit={handleJumpToUnit} />

      <div className="flex items-center justify-between mb-6">
        <div><h1 className="text-xl font-bold text-gray-800">🎓 教学模式</h1><p className="text-xs text-gray-400 mt-0.5">单元 {currentUnitIndex + 1} / {totalUnits} · {getPhaseLabel(currentPhase)}</p></div>
        <div className="flex items-center gap-4"><div className="w-40"><ProgressBar value={completedSteps} max={totalSteps} size="sm" color="blue" /></div><span className="text-sm font-semibold text-blue-600">{progressPercent}%</span></div>
      </div>

      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-2">
        {strategyPhases.map((phase) => {
          const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG];
          if (!config) return null;
          const isActive = currentPhase === phase;
          const currentOrder = strategyPhases.indexOf(currentPhase as TeachingPhase);
          const thisOrder = strategyPhases.indexOf(phase);
          const isPast = thisOrder < currentOrder;
          return (
            <div key={phase} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium shrink-0 transition-all ${isActive ? 'bg-blue-500 text-white shadow-md shadow-blue-500/20' : isPast ? 'bg-blue-50 text-blue-600' : 'bg-gray-50 text-gray-400'}`}>
              <span>{config.icon}</span><span>{config.label}</span>
            </div>
          );
        })}
      </div>

      <div className="bg-gray-50/50 rounded-2xl mb-6 border border-gray-100">
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <span className="text-xs font-semibold text-gray-400">{units.find((u) => u.id === viewingUnitId)?.title || `单元 ${units.findIndex((u) => u.id === viewingUnitId) + 1}`}</span>
          <div className="flex items-center gap-3">
            <select value={viewingUnitId} onChange={(e) => setViewingUnitId(e.target.value)} className="text-xs text-gray-500 bg-transparent border-none outline-none cursor-pointer">
              {units.map((u, i) => <option key={u.id} value={u.id}>{u.title || `单元 ${i + 1}`}</option>)}
            </select>
            {unitMessages.length > 0 && <button onClick={handleClearMessages} className="text-xs text-gray-400 hover:text-red-500 transition-colors">清空记录</button>}
          </div>
        </div>
        <div className="px-5 pb-5 min-h-[250px] max-h-[460px] overflow-y-auto">
          {unitMessages.length === 0 ? <div className="flex items-center justify-center h-40 text-gray-400 text-sm">点击"继续"开始学习</div> : <>{unitMessages.map((msg, i) => <MessageBubble key={msg.id || i} msg={msg} />)}<div ref={messagesEndRef} /></>}
        </div>
      </div>

      {!completed && !awaitingAnswer && !(test && test.score !== null) && (
        <div className="flex justify-end mb-4">
          <Button onClick={handleAdvance} disabled={advancing}>{advancing ? '...' : '继续 →'}</Button>
        </div>
      )}

      {completed && !test && (
        <Card hover={false} className="mb-6"><EmptyState icon="checkCircle" title="所有单元已学完" description="完成测试来检验你的理解程度" action={<Button onClick={handleRunTest}>开始测试</Button>} /></Card>
      )}

      {test && <TestPanel test={test} onSubmit={handleSubmitTest} />}

      {!completed && awaitingAnswer && (
        <Card hover={false} className="mb-6 border-2 border-green-200 bg-green-50/30">
          <h3 className="text-sm font-semibold text-green-700 mb-3 flex items-center gap-2"><span>{currentPhase === 'feynman' ? '🧠' : '✍️'}</span>{currentPhase === 'feynman' ? '请用自己的话解释刚才学到的内容' : '请回答问题'}</h3>
          <textarea value={answerInput} onChange={(e) => setAnswerInput(e.target.value)} placeholder={currentPhase === 'feynman' ? '用你自己的话解释这个知识点，不要照搬原文...' : '输入你的回答...'} rows={3} className="w-full p-3 border-2 border-green-200 rounded-xl text-sm text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-100 bg-white resize-none" />
          <div className="flex justify-end mt-3"><Button variant="success" onClick={handleSubmitAnswer} disabled={submittingAnswer || !answerInput.trim()}>{submittingAnswer ? '评估中...' : '提交回答'}</Button></div>
        </Card>
      )}

      {!completed && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          <Card hover={false}>
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2"><Icon name="sparkles" className="w-4 h-4" /> 提问</h3>
            <div className="flex gap-2">
              <input type="text" value={questionInput} onChange={(e) => setQuestionInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()} placeholder="有不明白的地方？..." className="flex-1 p-2.5 border border-gray-100 rounded-xl text-sm text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50" />
              <Button onClick={handleAskQuestion} disabled={asking || !questionInput.trim()}>发送</Button>
            </div>
          </Card>
          <Card hover={false}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2"><Icon name="pencil" className="w-4 h-4" /> {cornellMode ? '康奈尔笔记' : '笔记'}</h3>
              <button onClick={() => setCornellMode(!cornellMode)} className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${cornellMode ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>{cornellMode ? '标准模式' : '康奈尔模式'}</button>
            </div>
            {cornellMode ? (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <div className="flex items-center justify-between mb-1"><span className="text-xs font-semibold text-purple-600">线索栏</span><button onClick={handleGenerateCues} disabled={generatingCues || !noteInput.trim()} className="text-[10px] text-purple-500 hover:text-purple-700 disabled:opacity-40">{generatingCues ? '生成中...' : 'AI 生成'}</button></div>
                    <div className="min-h-[80px] p-2 border border-purple-200 rounded-lg bg-purple-50/50 text-xs text-gray-600">{cornellCues.length > 0 ? cornellCues.map((cue, i) => <p key={i} className="mb-1">- {cue}</p>) : <p className="text-gray-400">点击 AI 生成或手动输入</p>}</div>
                  </div>
                  <div><span className="text-xs font-semibold text-blue-600 mb-1 block">笔记栏</span><textarea value={noteInput} onChange={(e) => setNoteInput(e.target.value)} placeholder="记录笔记..." rows={4} className="w-full p-2 border border-blue-200 rounded-lg text-xs text-gray-600 placeholder:text-gray-300 focus:outline-none focus:border-blue-400 bg-blue-50/50 resize-none" /></div>
                  <div>
                    <div className="flex items-center justify-between mb-1"><span className="text-xs font-semibold text-green-600">总结栏</span><button onClick={handleGenerateSummary} disabled={generatingSummary || !noteInput.trim()} className="text-[10px] text-green-500 hover:text