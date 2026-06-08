import { useState } from 'react';
import Card from '../components/Card';
import { useAppState, defaultSettings } from '../contexts/AppContext';
import type { AIConfigUpdate } from '../types';

export default function Settings() {
  const { settings, settingsLoaded, saveSettings, aiConfig, saveAIConfig } = useAppState();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // 本地草稿，保存时才提交
  const [draft, setDraft] = useState<Partial<typeof defaultSettings>>({});
  // AI 配置草稿
  const [aiDraft, setAiDraft] = useState<AIConfigUpdate>({});
  const [aiSaving, setAiSaving] = useState(false);
  const [aiSaved, setAiSaved] = useState(false);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  // 用 settings 或默认值，合并本地草稿
  const s = { ...(settings ?? defaultSettings), ...draft };

  const update = <K extends keyof typeof defaultSettings>(
    key: K,
    value: (typeof defaultSettings)[K],
  ) => {
    setDraft(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveSettings({ ...(settings ?? defaultSettings), ...draft });
      setDraft({});
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      alert('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleAISave = async () => {
    setAiSaving(true);
    try {
      await saveAIConfig(aiDraft);
      setAiDraft({});
      setAiSaved(true);
      setTimeout(() => setAiSaved(false), 2000);
    } catch {
      alert('AI 配置保存失败');
    } finally {
      setAiSaving(false);
    }
  };

  const updateAIDefault = (field: string, value: string) => {
    setAiDraft(prev => ({ ...prev, [`default_${field}`]: value }));
  };

  const updateAIModule = (module: string, field: string, value: string) => {
    setAiDraft(prev => ({
      ...prev,
      modules: { ...prev.modules, [module]: { ...(prev.modules?.[module] ?? {}), [field]: value } },
    }));
  };

  // 获取模块的当前值（草稿优先，否则用 aiConfig 的值）
  const getModuleValue = (module: string, field: string): string => {
    const draftVal = aiDraft.modules?.[module]?.[field as keyof typeof aiDraft.modules[typeof module]];
    if (draftVal !== undefined && draftVal !== null) return draftVal as string;
    if (!aiConfig) return '';
    const mod = aiConfig.modules.find(m => m.module === module);
    if (!mod) return '';
    return (mod as any)[field] ?? '';
  };

  const getDefaultValue = (field: string): string => {
    const draftVal = (aiDraft as any)[`default_${field}`];
    if (draftVal !== undefined && draftVal !== null) return draftVal;
    if (!aiConfig) return '';
    return (aiConfig as any)[`default_${field}`] ?? '';
  };

  if (!settingsLoaded) {
    return <div className="max-w-2xl mx-auto p-10 text-center text-gray-400">加载中...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-800">设置</h1>
        <p className="text-sm text-gray-400 mt-0.5">配置学习目标和模型参数</p>
      </div>

      {/* 学习目标 */}
      <Card className="mb-5">
        <h2 className="text-sm font-bold text-gray-700 mb-5 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-blue-50 flex items-center justify-center text-sm">🎯</span>
          学习目标
        </h2>
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">每日学习时长（分钟）</label>
            <input type="number" min={1} max={1440} value={s.daily_goal_minutes}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                update('daily_goal_minutes', isNaN(val) ? 1 : Math.max(1, val));
              }}
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">每日完成单元数</label>
            <input type="number" min={1} max={100} value={s.daily_goal_units}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                update('daily_goal_units', isNaN(val) ? 1 : Math.max(1, val));
              }}
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
        </div>
      </Card>

      {/* 复习提醒 */}
      <Card className="mb-5">
        <h2 className="text-sm font-bold text-gray-700 mb-5 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-amber-50 flex items-center justify-center text-sm">🔔</span>
          复习提醒
        </h2>
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm text-gray-700 font-medium">开启复习提醒</span>
              <p className="text-xs text-gray-400 mt-0.5">每天定时提醒你复习</p>
            </div>
            <button onClick={() => update('review_reminder', !s.review_reminder)}
              className={`w-11 h-6 rounded-full transition-colors relative ${s.review_reminder ? 'bg-blue-500' : 'bg-gray-200'
                }`}>
              <div className={`w-5 h-5 bg-white rounded-full shadow-sm absolute top-0.5 transition-transform ${s.review_reminder ? 'translate-x-[1.375rem]' : 'translate-x-0.5'
                }`} />
            </button>
          </div>
          {s.review_reminder && (
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-2">提醒时间</label>
              <input type="time" value={s.reminder_time}
                onChange={(e) => update('reminder_time', e.target.value)}
                className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
            </div>
          )}
        </div>
      </Card>

      {/* 保存按钮 */}
      <div className="flex justify-end mb-8">
        <button onClick={handleSave} disabled={saving}
          className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-medium transition-all ${saved
              ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/25'
              : 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-50'
            }`}>
          {saved ? '✓ 已保存' : saving ? '保存中...' : '💾 保存设置'}
        </button>
      </div>

      {/* 并发控制 */}
      <Card className="mb-5">
        <h2 className="text-sm font-bold text-gray-700 mb-5 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-cyan-50 flex items-center justify-center text-sm">⚡</span>
          并发控制
        </h2>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-2">同时进行的 LLM 请求数</label>
          <input type="number" min={1} max={20} value={s.llm_max_concurrent}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              update('llm_max_concurrent', isNaN(val) ? 1 : Math.max(1, Math.min(20, val)));
            }}
            className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          <p className="text-xs text-gray-400 mt-1.5">数值越高学习速度越快，但过高可能导致 API 限流。推荐 3-5。</p>
        </div>
      </Card>

      {/* AI 模型配置（可编辑） */}
      <Card className="mb-5">
        <h2 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-purple-50 flex items-center justify-center text-sm">🤖</span>
          AI 模型配置
        </h2>
        <p className="text-xs text-gray-400 mb-5">
          不同模块可使用不同 AI 模型。保存后立即生效，无需重启。
        </p>

        {aiConfig ? (
          <>
            {/* 全局默认 */}
            <div className="mb-4 p-4 bg-gray-50 rounded-lg space-y-3">
              <div className="text-xs font-medium text-gray-500">📌 全局默认（保底）</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">模型名称</label>
                  <input type="text" value={getDefaultValue('model')}
                    onChange={(e) => updateAIDefault('model', e.target.value)}
                    placeholder={aiConfig.default_model}
                    className="w-full p-2 border border-gray-100 rounded-lg text-xs font-mono focus:outline-none focus:border-blue-200 bg-white transition-all" />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Base URL</label>
                  <input type="text" value={getDefaultValue('base_url')}
                    onChange={(e) => updateAIDefault('base_url', e.target.value)}
                    placeholder={aiConfig.default_base_url}
                    className="w-full p-2 border border-gray-100 rounded-lg text-xs font-mono focus:outline-none focus:border-blue-200 bg-white transition-all" />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">API Key</label>
                <div className="relative">
                  <input type={showKeys['default'] ? 'text' : 'password'} value={aiDraft.default_api_key ?? ''}
                    onChange={(e) => updateAIDefault('api_key', e.target.value)}
                    placeholder="留空表示不修改"
                    className="w-full p-2 pr-10 border border-gray-100 rounded-lg text-xs font-mono focus:outline-none focus:border-blue-200 bg-white transition-all" />
                  <button onClick={() => setShowKeys(prev => ({ ...prev, default: !prev.default }))}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs">
                    {showKeys['default'] ? '🙈' : '👁️'}
                  </button>
                </div>
              </div>
            </div>

            {/* 各模块配置 */}
            <div className="space-y-4">
              {aiConfig.modules.map((mod) => (
                <div key={mod.module} className="p-4 border border-gray-100 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-sm font-medium text-gray-700">{mod.label}</div>
                      <div className="text-xs text-gray-400 mt-0.5">{mod.description}</div>
                    </div>
                    <div className={`text-xs px-2 py-0.5 rounded-full ${mod.strength_hint === '强' ? 'bg-red-50 text-red-500' :
                        mod.strength_hint === '弱' ? 'bg-green-50 text-green-500' :
                          'bg-amber-50 text-amber-500'
                      }`}>
                      💡 建议{mod.strength_hint}模型
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">模型名称</label>
                      <input type="text" value={getModuleValue(mod.module, 'model')}
                        onChange={(e) => updateAIModule(mod.module, 'model', e.target.value)}
                        placeholder={mod.model || '继承默认'}
                        className="w-full p-2 border border-gray-100 rounded-lg text-xs font-mono focus:outline-none focus:border-blue-200 bg-white transition-all" />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Base URL</label>
                      <input type="text" value={getModuleValue(mod.module, 'base_url')}
                        onChange={(e) => updateAIModule(mod.module, 'base_url', e.target.value)}
                        placeholder={mod.base_url || '继承默认'}
                        className="w-full p-2 border border-gray-100 rounded-lg text-xs font-mono focus:outline-none focus:border-blue-200 bg-white transition-all" />
                    </div>
                  </div>
                  <div className="mt-3">
                    <label className="block text-xs text-gray-400 mb-1">API Key {mod.has_custom_key && <span className="text-green-500">✓ 已配置</span>}</label>
                    <div className="relative">
                      <input type={showKeys[mod.module] ? 'text' : 'password'} value={getModuleValue(mod.module, 'api_key')}
                        onChange={(e) => updateAIModule(mod.module, 'api_key', e.target.value)}
                        placeholder="留空表示不修改"
                        className="w-full p-2 pr-10 border border-gray-100 rounded-lg text-xs font-mono focus:outline-none focus:border-blue-200 bg-white transition-all" />
                      <button onClick={() => setShowKeys(prev => ({ ...prev, [mod.module]: !prev[mod.module] }))}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs">
                        {showKeys[mod.module] ? '🙈' : '👁️'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* AI 配置保存按钮 */}
            <div className="flex justify-end mt-5">
              <button onClick={handleAISave} disabled={aiSaving}
                className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-medium transition-all ${aiSaved
                    ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/25'
                    : 'bg-gradient-to-r from-purple-500 to-purple-600 text-white hover:shadow-lg hover:shadow-purple-500/25 disabled:opacity-50'
                  }`}>
                {aiSaved ? '✓ 已保存' : aiSaving ? '保存中...' : '💾 保存 AI 配置'}
              </button>
            </div>
          </>
        ) : (
          <div className="text-sm text-gray-400 text-center py-4">加载中...</div>
        )}
      </Card>
    </div>
  );
}
