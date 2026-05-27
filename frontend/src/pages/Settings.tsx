import { useState } from 'react';
import Card from '../components/Card';
import { useAppState, defaultSettings } from '../contexts/AppContext';

export default function Settings() {
  const { settings, settingsLoaded, saveSettings, aiConfig } = useAppState();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // 本地草稿，保存时才提交
  const [draft, setDraft] = useState<Partial<typeof defaultSettings>>({});

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

      {/* 保存按钮 */}
      <div className="flex justify-end mb-8">
        <button onClick={handleSave} disabled={saving}
          className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-medium transition-all ${
            saved
              ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/25'
              : 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-50'
          }`}>
          {saved ? '✓ 已保存' : saving ? '保存中...' : '💾 保存设置'}
        </button>
      </div>

      {/* AI 模型配置（只读） */}
      <Card className="mb-5">
        <h2 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-purple-50 flex items-center justify-center text-sm">🤖</span>
          AI 模型配置
        </h2>
        <p className="text-xs text-gray-400 mb-5">
          不同模块可使用不同 AI 模型。修改配置请编辑 <code className="bg-gray-100 px-1 rounded">.env</code> 文件并重启服务。
        </p>

        {aiConfig ? (
          <>
            {/* 全局默认 */}
            <div className="mb-4 p-3 bg-gray-50 rounded-lg">
              <div className="text-xs font-medium text-gray-500 mb-1">📌 全局默认（保底）</div>
              <div className="text-sm text-gray-700">
                <span className="font-mono">{aiConfig.default_model}</span>
                <span className="text-gray-400 ml-2">{aiConfig.default_base_url}</span>
              </div>
            </div>

            {/* 各模块配置 */}
            <div className="space-y-3">
              {aiConfig.modules.map((mod) => (
                <div key={mod.module} className="flex items-center justify-between p-3 border border-gray-100 rounded-lg">
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-700">{mod.label}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{mod.description}</div>
                  </div>
                  <div className="text-right ml-4">
                    <div className="text-xs font-mono text-gray-600">
                      {mod.model || '继承默认'}
                    </div>
                    <div className={`text-xs mt-0.5 ${
                      mod.strength_hint === '强' ? 'text-red-400' :
                      mod.strength_hint === '弱' ? 'text-green-400' :
                      'text-amber-400'
                    }`}>
                      💡 建议{mod.strength_hint}模型
                    </div>
                    {mod.has_custom_key && (
                      <div className="text-xs text-green-500 mt-0.5">✓ 独立 Key</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="text-sm text-gray-400 text-center py-4">加载中...</div>
        )}
      </Card>
    </div>
  );
}
