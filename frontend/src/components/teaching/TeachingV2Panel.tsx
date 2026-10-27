import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../Card';
import Button from '../ui/Button';
import EmptyState from '../ui/EmptyState';
// paths: components/teaching -> components/*
import {
  getActiveUnitAsset,
  getTeachingV2Session,
  prepareAndStartUnitLoop,
  teachingV2Attempt,
  teachingV2Event,
  type TeachingV2Session,
  type UnitAsset,
} from '../../api/learningAssets';
import type { KnowledgeUnit } from '../../types';

const V2_STATE_LABEL: Record<string, string> = {
  prepare: '准备',
  diagnose: '课前诊断',
  activate: '激活旧知',
  explain: '核心讲解',
  guided_practice: '引导练习',
  assess: '正式检测',
  repair: '针对性修复',
  reassess: '再测',
  prerequisite_intervention: '前置补习',
  reflect: '总结',
  schedule_review: '安排复习',
  completed: '已完成',
  paused: '已暂停',
};

type Props = {
  bookId: string;
  unitId: string;
  units: KnowledgeUnit[];
};

/**
 * 单单元闭环最小 UI：绑定 asset，按状态机推进，作答写 Evidence。
 * 不复用旧消息流，避免与 v1 TeachingSession 混用。
 */
export default function TeachingV2Panel({ bookId, unitId, units }: Props) {
  const navigate = useNavigate();
  const [session, setSession] = useState<TeachingV2Session | null>(null);
  const [asset, setAsset] = useState<UnitAsset | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [answer, setAnswer] = useState('');
  const [lastScore, setLastScore] = useState('');
  const unit = units.find((u) => u.id === unitId);

  const pushLog = (line: string) => setLog((prev) => [...prev.slice(-40), line]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const saved = localStorage.getItem(`teaching_v2_session_${bookId}`);
      if (saved) {
        try {
          const s = await getTeachingV2Session(saved);
          if (s && s.status !== 'completed') {
            setSession(s);
            const a = await getActiveUnitAsset(unitId).catch(() => null);
            if (a) setAsset(a);
            setLoading(false);
            return;
          }
        } catch {
          /* create new */
        }
      }
      const { asset: ar, session: s } = await prepareAndStartUnitLoop(bookId, unitId);
      localStorage.setItem(`teaching_v2_session_${bookId}`, s.id);
      setSession(s);
      const full = await getActiveUnitAsset(unitId);
      setAsset(full);
      pushLog(`已分析并开始：readiness=${ar.readiness_status} state=${s.state_v2}`);
    } catch (e) {
      pushLog(`启动失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }, [bookId, unitId]);

  useEffect(() => {
    load();
  }, [load]);

  const payload = (asset?.payload || {}) as {
    assessment_items?: Array<{
      id: string;
      stem: string;
      expected_answer?: string;
      phase_usage?: string[];
    }>;
    learning_objectives?: Array<{ id: string; description: string }>;
    central_question?: string;
    explanation?: string;
    summary?: string;
  };

  const state = session?.state_v2 || 'prepare';
  const items = payload.assessment_items || [];
  const currentItem =
    state === 'reassess'
      ? items.find((i) => (i.phase_usage || []).includes('reassessment')) || items[0]
      : state === 'diagnose'
        ? items.find((i) => (i.phase_usage || []).includes('diagnose')) || items[0]
        : items.find((i) => (i.phase_usage || []).includes('assessment')) || items[0];

  const runEvent = async (event: string, guards: Record<string, unknown> = {}) => {
    if (!session || busy) return;
    setBusy(true);
    try {
      const s = await teachingV2Event(session.id, event, guards);
      setSession(s);
      pushLog(`事件 ${event} → ${s.state_v2} (${s.completion_status || '-'})`);
      if (s.state_v2 === 'completed') {
        localStorage.removeItem(`teaching_v2_session_${bookId}`);
      }
    } catch (e) {
      pushLog(`事件失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const submitCurrent = async () => {
    if (!session || !currentItem || busy) return;
    setBusy(true);
    try {
      const sourceType =
        state === 'reassess'
          ? 'reassessment'
          : state === 'diagnose'
            ? 'diagnose'
            : state === 'guided_practice'
              ? 'practice'
              : 'assessment';
      const res = await teachingV2Attempt(session.id, {
        assessment_item_id: currentItem.id,
        response: { answer: answer.trim() },
        idempotency_key: `${session.id}-${currentItem.id}-${Date.now()}`,
        source_type: sourceType,
      });
      setLastScore(`${res.result || ''} · score=${res.score ?? '-'}`);
      pushLog(`作答 ${res.result} score=${res.score}`);
      setAnswer('');
      const passed = (res.score ?? 0) >= 0.8;
      if (state === 'diagnose') {
        await teachingV2Event(session.id, 'DIAGNOSIS_SUBMITTED', {
          diagnosis_summary: passed ? 'strong' : 'mixed',
        });
      } else if (state === 'guided_practice') {
        await teachingV2Event(session.id, 'PRACTICE_SUBMITTED', {});
      } else if (state === 'assess') {
        await teachingV2Event(session.id, 'ASSESSMENT_SUBMITTED', {
          required_objectives_passed: passed,
          repairable_gaps: !passed,
          repair_rounds: 0,
        });
      } else if (state === 'reassess') {
        await teachingV2Event(session.id, 'REASSESSMENT_SUBMITTED', {
          required_objectives_passed: passed,
          repairable_gaps: !passed,
          repair_rounds: 1,
        });
      }
      const fresh = await getTeachingV2Session(session.id);
      setSession(fresh);
      pushLog(`推进后状态 ${fresh.state_v2} / ${fresh.completion_status || '-'}`);
      if (fresh.state_v2 === 'completed') {
        localStorage.removeItem(`teaching_v2_session_${bookId}`);
      }
    } catch (e) {
      pushLog(`作答失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400 text-sm">
        正在准备单单元闭环…
      </div>
    );
  }

  if (!session) {
    return (
      <EmptyState
        title="无法启动 v2 会话"
        description="请确认单元已拆分，并查看日志。"
        action={<Button onClick={load}>重试</Button>}
      />
    );
  }

  const needsAnswer = ['diagnose', 'guided_practice', 'assess', 'reassess'].includes(state);
  const canAck = ['activate', 'explain', 'repair', 'reflect'].includes(state);

  return (
    <div className="max-w-3xl mx-auto space-y-4 animate-fade-in">
      <Card hover={false} gradient>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-blue-500 font-medium mb-1">单单元闭环 · engine=v2</p>
            <h2 className="text-lg font-bold text-gray-800">{unit?.title || unitId}</h2>
            <p className="text-xs text-gray-400 mt-1">
              状态：{V2_STATE_LABEL[state] || state}
              {session.completion_status ? ` · ${session.completion_status}` : ''}
              {asset ? ` · 资产 ${asset.readiness_status}` : ''}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => navigate(`/books/${bookId}`)}>
            返回书籍
          </Button>
        </div>
      </Card>

      <Card hover={false}>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">本单元材料</h3>
        <p className="text-sm text-gray-600 mb-2">
          {payload.central_question || payload.summary || '（无核心问题）'}
        </p>
        {payload.explanation && (
          <p className="text-sm text-gray-500 whitespace-pre-wrap line-clamp-6">{payload.explanation}</p>
        )}
        {(payload.learning_objectives || []).length > 0 && (
          <ul className="mt-3 space-y-1">
            {payload.learning_objectives!.map((o) => (
              <li key={o.id} className="text-xs text-gray-500">
                · {o.description}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {needsAnswer && currentItem && (
        <Card hover={false}>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">{V2_STATE_LABEL[state] || state}题</h3>
          <p className="text-sm text-gray-800 mb-3">{currentItem.stem}</p>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            className="w-full border border-gray-200 rounded-lg p-3 text-sm min-h-[88px] focus:outline-none focus:ring-2 focus:ring-blue-100"
            placeholder="输入你的回答…"
          />
          {lastScore && <p className="text-xs text-gray-400 mt-2">上次：{lastScore}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button loading={busy} onClick={submitCurrent} disabled={!answer.trim()}>
              提交并推进
            </Button>
            {state === 'assess' && (
              <Button variant="secondary" disabled={busy} onClick={() => runEvent('ASSESSMENT_SKIPPED')}>
                跳过检测（不记掌握）
              </Button>
            )}
          </div>
        </Card>
      )}

      {canAck && (
        <Card hover={false}>
          <p className="text-sm text-gray-600 mb-3">
            当前处于「{V2_STATE_LABEL[state] || state}」。确认后进入下一阶段。
          </p>
          <Button
            loading={busy}
            onClick={() =>
              runEvent(state === 'repair' ? 'REPAIR_COMPLETED' : 'EXPLANATION_ACKNOWLEDGED')
            }
          >
            继续
          </Button>
        </Card>
      )}

      {state === 'completed' && (
        <Card hover={false}>
          <p className="text-sm text-emerald-600 font-medium">
            会话结束：{session.completion_status || 'completed'}
          </p>
          <Button className="mt-3" onClick={() => navigate(`/books/${bookId}`)}>
            回书籍详情
          </Button>
        </Card>
      )}

      <Card hover={false}>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">过程日志</h3>
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {log.length === 0 && <p className="text-xs text-gray-300">暂无</p>}
          {log.map((line, i) => (
            <p key={i} className="text-xs text-gray-500 font-mono">
              {line}
            </p>
          ))}
        </div>
      </Card>
    </div>
  );
}
