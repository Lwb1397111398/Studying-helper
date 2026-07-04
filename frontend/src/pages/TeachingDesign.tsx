import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import { getBook } from '../api/books';
import {
  activateAidDesign,
  confirmAidProfile,
  generateAidMacro,
  generateAidMicro,
  getAidDesign,
  getAidMicro,
  getAidProfile,
  updateAidProfile,
  type CognitivePref,
  type GoalDepth,
  type IdentityBackground,
  type LearnerIntentProfile,
  type MicroPlan,
  type RestructureTolerance,
  type TeachingDesign as TeachingDesignType,
} from '../api/aid';
import type { Book } from '../types';

const identityOptions: Array<[IdentityBackground, string]> = [
  ['unknown', '未知'],
  ['expert', '专业背景'],
  ['related', '相关背景'],
  ['unrelated', '新手入门'],
];

const goalOptions: Array<[GoalDepth, string]> = [
  ['apply_understand', '理解应用'],
  ['exam_memorize', '考试记忆'],
  ['general_interest', '兴趣了解'],
];

const prefOptions: Array<[CognitivePref, string]> = [
  ['rigorous_system', '系统严谨'],
  ['vivid_analogy', '生动类比'],
  ['problem_driven', '问题驱动'],
];

const toleranceOptions: Array<[RestructureTolerance, string]> = [
  ['moderate', '适度重组'],
  ['keep_book_order', '保留书序'],
  ['aggressive', '大胆重组'],
];

export default function TeachingDesign() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [book, setBook] = useState<Book | null>(null);
  const [profile, setProfile] = useState<LearnerIntentProfile | null>(null);
  const [design, setDesign] = useState<TeachingDesignType | null>(null);
  const [microPlans, setMicroPlans] = useState<Record<number, MicroPlan>>({});
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [identity, setIdentity] = useState<IdentityBackground>('unknown');
  const [goal, setGoal] = useState<GoalDepth>('apply_understand');
  const [pref, setPref] = useState<CognitivePref>('rigorous_system');
  const [tolerance, setTolerance] = useState<RestructureTolerance>('moderate');
  const [minutes, setMinutes] = useState('');

  const modules = design?.macro_design?.modules ?? [];
  const allMicroGenerated = modules.length > 0 && modules.every((m) => microPlans[m.index]);

  const load = async () => {
    if (!bookId) return;
    setLoading(true);
    setError(null);
    try {
      const [bookData, profileData, designData] = await Promise.all([
        getBook(bookId),
        getAidProfile(bookId),
        getAidDesign(bookId),
      ]);
      setBook(bookData);
      setProfile(profileData);
      setDesign(designData);
      syncForm(profileData);
      if (designData?.macro_design?.modules) {
        const plans: Record<number, MicroPlan> = {};
        await Promise.all(designData.macro_design.modules.map(async (module) => {
          const plan = await getAidMicro(bookId, module.index).catch(() => null);
          if (plan) plans[module.index] = plan;
        }));
        setMicroPlans(plans);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载教学设计失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [bookId]);

  const syncForm = (nextProfile: LearnerIntentProfile) => {
    setIdentity(nextProfile.identity_background);
    setGoal(nextProfile.goal_depth);
    setPref(nextProfile.cognitive_pref);
    setTolerance(nextProfile.restructure_tolerance);
    setMinutes(nextProfile.time_budget_minutes?.toString() ?? '');
  };

  const saveProfile = async () => {
    if (!bookId) return;
    setWorking(true);
    setError(null);
    try {
      const next = await updateAidProfile(bookId, {
        identity_background: identity,
        goal_depth: goal,
        cognitive_pref: pref,
        restructure_tolerance: tolerance,
        time_budget_minutes: minutes.trim() ? Number(minutes) : null,
      });
      setProfile(next);
      syncForm(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存画像失败');
    } finally {
      setWorking(false);
    }
  };

  const confirmProfile = async () => {
    if (!bookId) return;
    setWorking(true);
    setError(null);
    try {
      const next = await confirmAidProfile(bookId);
      setProfile(next);
      syncForm(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : '确认画像失败');
    } finally {
      setWorking(false);
    }
  };

  const generateDesign = async () => {
    if (!bookId) return;
    setWorking(true);
    setError(null);
    try {
      await generateAidMacro(bookId);
      const next = await getAidDesign(bookId);
      setDesign(next);
      setMicroPlans({});
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成宏观设计失败');
    } finally {
      setWorking(false);
    }
  };

  const generateAllMicro = async () => {
    if (!bookId || modules.length === 0) return;
    setWorking(true);
    setError(null);
    try {
      const plans: Record<number, MicroPlan> = { ...microPlans };
      for (const module of modules) {
        plans[module.index] = await generateAidMicro(bookId, module.index);
        setMicroPlans({ ...plans });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成微观编排失败');
    } finally {
      setWorking(false);
    }
  };

  const startTeaching = async () => {
    if (!bookId) return;
    setWorking(true);
    setError(null);
    try {
      await activateAidDesign(bookId);
      navigate(`/books/${bookId}/teach`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '激活教学设计失败');
    } finally {
      setWorking(false);
    }
  };

  const unitCount = useMemo(() => modules.reduce((sum, item) => sum + item.unit_ids.length, 0), [modules]);

  if (loading) return <Loading />;

  return (
    <div className="max-w-5xl mx-auto animate-fade-in">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <button onClick={() => navigate(`/books/${bookId}`)} className="text-sm text-gray-400 hover:text-gray-600 mb-3">
            ← 返回书籍
          </button>
          <h1 className="text-2xl font-bold text-gray-900">教学设计</h1>
          <p className="text-sm text-gray-500 mt-1">{book?.title ?? '当前书籍'}</p>
        </div>
        <button
          onClick={startTeaching}
          disabled={working || !allMicroGenerated}
          className="px-5 py-2.5 bg-emerald-500 text-white rounded-xl text-sm font-medium hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          开始教学
        </button>
      </div>

      {error && (
        <div className="mb-5 p-4 rounded-xl bg-red-50 border border-red-100 text-sm text-red-600">
          {error}
        </div>
      )}

      {working && <div className="mb-5 h-1 bg-blue-100 rounded-full overflow-hidden"><div className="h-full w-1/2 bg-blue-500 animate-pulse" /></div>}

      <div className="grid grid-cols-1 lg:grid-cols-[360px,1fr] gap-5">
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-800">学习者画像</h2>
            <span className={`text-xs px-2 py-1 rounded-full ${profile?.status === 'confirmed' ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'}`}>
              {profile?.status === 'confirmed' ? '已确认' : '草稿'}
            </span>
          </div>
          <ProfileField title="背景" options={identityOptions} value={identity} onChange={setIdentity} />
          <ProfileField title="目标" options={goalOptions} value={goal} onChange={setGoal} />
          <ProfileField title="认知偏好" options={prefOptions} value={pref} onChange={setPref} />
          <ProfileField title="重组强度" options={toleranceOptions} value={tolerance} onChange={setTolerance} />
          <label className="block mt-4">
            <span className="text-xs font-semibold text-gray-500">时间预算（分钟，可空）</span>
            <input
              value={minutes}
              onChange={(event) => setMinutes(event.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300"
              placeholder="30"
            />
          </label>
          <div className="grid grid-cols-2 gap-2 mt-5">
            <button onClick={saveProfile} disabled={working} className="px-3 py-2 rounded-xl text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-40">
              保存画像
            </button>
            <button onClick={confirmProfile} disabled={working} className="px-3 py-2 rounded-xl text-sm bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-40">
              确认画像
            </button>
          </div>
        </Card>

        <div className="space-y-5">
          <Card>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-gray-800">宏观模块</h2>
                <p className="text-sm text-gray-500 mt-1">
                  {design?.macro_design?.global_strategy || '确认画像后生成跨章节模块。'}
                </p>
                {modules.length > 0 && (
                  <p className="text-xs text-gray-400 mt-2">{modules.length} 个模块 · 覆盖 {unitCount} 个知识单元</p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={generateDesign}
                  disabled={working || profile?.status !== 'confirmed'}
                  className="px-4 py-2 rounded-xl text-sm bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  生成 Macro
                </button>
                <button
                  onClick={generateAllMicro}
                  disabled={working || modules.length === 0}
                  className="px-4 py-2 rounded-xl text-sm bg-purple-500 text-white hover:bg-purple-600 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  生成 Micro
                </button>
              </div>
            </div>
          </Card>

          {modules.length === 0 ? (
            <Card className="text-center py-12">
              <p className="text-sm text-gray-400">还没有教学模块。请先确认画像并生成 Macro。</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {modules.map((module) => (
                <ModuleCard key={module.index} module={module} micro={microPlans[module.index]} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProfileField<T extends string>({
  title,
  options,
  value,
  onChange,
}: {
  title: string;
  options: Array<[T, string]>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="mb-4">
      <p className="text-xs font-semibold text-gray-500 mb-2">{title}</p>
      <div className="flex flex-wrap gap-2">
        {options.map(([option, label]) => (
          <button
            key={option}
            onClick={() => onChange(option)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              value === option ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ModuleCard({
  module,
  micro,
}: {
  module: { index: number; title: string; unit_ids: string[]; concept_ids: string[]; strategy_tags: string[]; rationale: string };
  micro?: MicroPlan;
}) {
  return (
    <Card>
      <div className="flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-sm font-bold">
          {module.index + 1}
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-gray-800">{module.title}</h3>
            <span className={`text-xs px-2 py-1 rounded-full ${micro ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-500'}`}>
              {micro ? micro.module_status : '未生成 Micro'}
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-2">{module.rationale}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            {module.strategy_tags.map((tag) => (
              <span key={tag} className="text-[11px] px-2 py-1 rounded-full bg-purple-50 text-purple-600">
                {tag}
              </span>
            ))}
            <span className="text-[11px] px-2 py-1 rounded-full bg-gray-100 text-gray-500">
              {module.unit_ids.length} 单元
            </span>
          </div>
          {micro?.module_intro && (
            <p className="text-sm text-gray-600 mt-3 bg-gray-50 rounded-xl p-3">{micro.module_intro}</p>
          )}
        </div>
      </div>
    </Card>
  );
}
