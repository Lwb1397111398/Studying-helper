import { useState } from 'react';
import Card from '../components/Card';
import { useAppState, defaultSettings } from '../contexts/AppContext';

export default function Settings() {
  const { settings, settingsLoaded, saveSettings } = useAppState();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // 用 settings 或默认值
  const s = settings ?? defaultSettings;

  const update = <K extends keyof typeof defaultSettings>(key: K, value: (typeof defaultSettings)[K]) => {
    // 本地立即更新（通过 saveSettings 会触发 context 更新）
    saveSettings({ [key]: value } as Partial<typeof defaultSettings>).catch(() => {});
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveSettings(s);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      alert('保存失败');
    } finally {
      setSaving(false);
    }
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
              onChange={(e) => update('daily_goal_minutes', Math.max(1, Number(e.target.value)))}
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">每日完成单元数</label>
            <input type="number" min={1} max={100} value={s.daily_goal_units}
              onChange={(e) => update('daily_goal_units', Math.max(1, Number(e.target.value)))}
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
              className={`w-11 h-6 rounded-full transition-colors relative ${
                s.review_reminder ? 'bg-blue-500' : 'bg-gray-200'
              }`}>
              <div className={`w-5 h-5 bg-white rounded-full shadow-sm absolute top-0.5 transition-transform ${
                s.review_reminder ? 'translate-x-5.5' : 'translate-x-0.5'
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

      {/* LLM 配置 */}
      <Card className="mb-8">
        <h2 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-purple-50 flex items-center justify-center text-sm">🤖</span>
          LLM 配置
        </h2>
        <p className="text-xs text-gray-400 mb-5">支持所有 OpenAI 兼容接口</p>
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">API Provider</label>
            <input type="text" value={s.llm_provider}
              onChange={(e) => update('llm_provider', e.target.value)}
              placeholder="openai"
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">API Base URL</label>
            <input type="text" value={s.llm_api_base}
              onChange={(e) => update('llm_api_base', e.target.value)}
              placeholder="https://api.openai.com/v1"
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">API Key</label>
            <input type="password" value={s.llm_api_key}
              onChange={(e) => update('llm_api_key', e.target.value)}
              placeholder="sk-..."
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">Model</label>
            <input type="text" value={s.llm_model}
              onChange={(e) => update('llm_model', e.target.value)}
              placeholder="gpt-4"
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
        </div>
      </Card>

      {/* 保存按钮 */}
      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving}
          className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-medium transition-all ${
            saved
              ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/25'
              : 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-50'
          }`}>
          {saved ? '✓ 已保存' : saving ? '保存中...' : '💾 保存设置'}
        </button>
      </div>
    </div>
  );
}
