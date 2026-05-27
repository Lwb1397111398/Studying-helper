import { useEffect, useState } from 'react';
import Card from '../components/Card';
import Loading from '../components/Loading';
import { useAppState } from '../contexts/AppContext';
import client from '../api/client';
import type { AuthUser, LearningStyle } from '../types';

interface ProfileData {
  user: AuthUser;
  total_books: number;
  total_learning_minutes: number;
  total_units_learned: number;
  current_streak: number;
}

export default function Profile() {
  const { isLoggedIn } = useAppState();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isLoggedIn) {
      loadProfile();
    } else {
      setLoading(false);
    }
  }, [isLoggedIn]);

  const loadProfile = async () => {
    try {
      const res: any = await client.get('/v1/users/profile');
      setProfile(res);
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="max-w-lg mx-auto text-center py-20 animate-fade-in">
        <div className="text-6xl mb-5">🔐</div>
        <h2 className="text-xl font-bold text-gray-800 mb-2">请先登录</h2>
        <p className="text-sm text-gray-400">登录后即可查看你的学习画像</p>
      </div>
    );
  }

  if (loading) return <Loading />;
  if (error) return <div className="text-center py-12 text-red-500">{error}</div>;
  if (!profile) return null;

  const { user, total_books, total_learning_minutes, total_units_learned, current_streak } = profile;

  // 解析学习风格（API 可能返回额外字段）
  let style: LearningStyle | null = null;
  const extra = user as any;
  if (extra.learning_style_json) {
    try { style = JSON.parse(extra.learning_style_json); } catch {}
  }

  const hours = Math.floor(total_learning_minutes / 60);
  const mins = total_learning_minutes % 60;

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      {/* 用户卡片 */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-blue-600 via-blue-500 to-purple-600 p-8 mb-8 text-white shadow-xl shadow-blue-500/15">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PHBhdGggZD0iTTM2IDM0djItSDI0di0yaDEyem0wLTRWMjhIMjR2Mmgxem0tMi0ydi0ySDI2djJoOHptMC00di0ySDI2djJoOHoiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-30" />
        <div className="relative flex items-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center text-2xl font-bold border border-white/20">
            {user.username.charAt(0).toUpperCase()}
          </div>
          <div>
            <h1 className="text-2xl font-bold">{user.username}</h1>
            {user.email && <p className="text-blue-100 text-sm mt-0.5">{user.email}</p>}
            <p className="text-blue-200 text-xs mt-1">
              {user.preferred_language === 'zh' ? '中文用户' : user.preferred_language} · 每日目标 {user.daily_goal_minutes} 分钟
            </p>
          </div>
        </div>
        <div className="absolute -right-6 -top-6 w-32 h-32 rounded-full bg-white/10 blur-2xl" />
      </div>

      {/* 统计数据 */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: '书籍', value: total_books, unit: '本', color: 'blue', icon: '📚' },
          { label: '学习时长', value: hours > 0 ? `${hours}h${mins}m` : `${mins}m`, unit: '', color: 'green', icon: '⏱️' },
          { label: '知识单元', value: total_units_learned, unit: '个', color: 'purple', icon: '🧩' },
          { label: '连续学习', value: current_streak, unit: '天', color: 'amber', icon: '🔥' },
        ].map((s, i) => (
          <Card key={s.label} className={`animate-fade-in delay-${(i + 1) * 100}`}>
            <div className="flex items-start justify-between mb-3">
              <span className="text-2xl">{s.icon}</span>
              <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                s.color === 'blue' ? 'bg-blue-50 text-blue-600' :
                s.color === 'green' ? 'bg-emerald-50 text-emerald-600' :
                s.color === 'purple' ? 'bg-purple-50 text-purple-600' :
                'bg-amber-50 text-amber-600'
              }`}>{s.label}</span>
            </div>
            <p className={`text-3xl font-bold tracking-tight ${
              s.color === 'blue' ? 'text-blue-600' :
              s.color === 'green' ? 'text-emerald-600' :
              s.color === 'purple' ? 'text-purple-600' :
              'text-amber-600'
            }`}>{s.value}</p>
            {s.unit && <p className="text-xs text-gray-400 mt-0.5">{s.unit}</p>}
          </Card>
        ))}
      </div>

      {/* 学习风格 */}
      {style && (
        <Card>
          <h2 className="text-sm font-bold text-gray-700 mb-5 flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-purple-50 flex items-center justify-center text-sm">🧠</span>
            学习风格偏好
          </h2>
          <div className="space-y-4">
            {[
              { key: 'visual_score', label: '视觉偏好', desc: '图表、思维导图、颜色标记', color: 'blue' },
              { key: 'verbal_score', label: '文字偏好', desc: '阅读、写作、文字说明', color: 'green' },
              { key: 'active_score', label: '主动偏好', desc: '练习、实践、动手操作', color: 'purple' },
              { key: 'sequential_score', label: '顺序偏好', desc: '按步骤学习 vs 跳跃式', color: 'amber' },
            ].map((item) => {
              const value = (style as any)?.[item.key] ?? 0.5;
              const pct = Math.round(value * 100);
              return (
                <div key={item.key}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div>
                      <span className="text-sm font-medium text-gray-700">{item.label}</span>
                      <span className="text-xs text-gray-400 ml-2">{item.desc}</span>
                    </div>
                    <span className="text-sm font-semibold text-gray-600">{pct}%</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        item.color === 'blue' ? 'bg-blue-500' :
                        item.color === 'green' ? 'bg-emerald-500' :
                        item.color === 'purple' ? 'bg-purple-500' :
                        'bg-amber-500'
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
