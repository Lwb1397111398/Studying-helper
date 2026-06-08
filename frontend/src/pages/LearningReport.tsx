import { useEffect, useState } from 'react';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { getLearningReport } from '../api/learning';
import { getTeachingStats } from '../api/teaching';
import type { LearningReport as ReportType } from '../types';

const PERIOD_OPTIONS = [
  { value: 'week', label: '本周', icon: '📅' },
  { value: 'month', label: '本月', icon: '🗓️' },
  { value: 'year', label: '本年', icon: '📊' },
];

interface TeachingStats {
  total_sessions: number;
  total_minutes: number;
  questions_asked: number;
  avg_test_score: number;
  units_covered: number;
}

export default function LearningReport() {
  const [report, setReport] = useState<ReportType | null>(null);
  const [period, setPeriod] = useState('week');
  const [loading, setLoading] = useState(true);
  const [teachingStats, setTeachingStats] = useState<TeachingStats>({
    total_sessions: 0,
    total_minutes: 0,
    questions_asked: 0,
    avg_test_score: 0,
    units_covered: 0,
  });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const days = period === 'week' ? 7 : (period === 'month' ? 30 : 365);

    Promise.all([
      getLearningReport(period),
      getTeachingStats(undefined, days).catch(() => ({
        total_sessions: 0,
        total_minutes: 0,
        questions_asked: 0,
        avg_test_score: 0,
        units_covered: 0,
      })),
    ])
      .then(([reportData, stats]) => {
        if (!cancelled) {
          setReport(reportData);
          setTeachingStats(stats);
        }
      })
      .catch((error) => {
        if (!cancelled) console.error('加载学习报告失败:', error);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [period]);

  if (loading) return <Loading />;

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {/* 标题 */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">学习报告</h1>
          <p className="text-sm text-gray-400 mt-0.5">查看你的学习数据和进度</p>
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {PERIOD_OPTIONS.map((p) => (
            <button key={p.value} onClick={() => setPeriod(p.value)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                period === p.value
                  ? 'bg-white text-gray-800 shadow-sm'
                  : 'text-gray-400 hover:text-gray-600'
              }`}>
              <span>{p.icon}</span>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {report ? (
        <>
          {/* 统计概览 */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <Card gradient>
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-2xl shadow-lg shadow-blue-500/20">
                  ⏱️
                </div>
                <div>
                  <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">学习时长</p>
                  <p className="text-3xl font-bold text-blue-600 tracking-tight">{report.total_minutes}</p>
                  <p className="text-xs text-gray-400">分钟</p>
                </div>
              </div>
            </Card>
            <Card gradient>
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-500 flex items-center justify-center text-2xl shadow-lg shadow-emerald-500/20">
                  ✅
                </div>
                <div>
                  <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">完成单元</p>
                  <p className="text-3xl font-bold text-emerald-600 tracking-tight">{report.units_completed}</p>
                  <p className="text-xs text-gray-400">个知识单元</p>
                </div>
              </div>
            </Card>
          </div>

          {/* 教学统计 */}
          <Card className="mb-6">
            <h3 className="text-lg font-bold text-gray-800 mb-4">📚 教学统计</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-4 bg-blue-50 rounded-xl">
                <p className="text-2xl font-bold text-blue-600">{teachingStats.total_sessions}</p>
                <p className="text-sm text-gray-500">教学会话</p>
              </div>
              <div className="text-center p-4 bg-green-50 rounded-xl">
                <p className="text-2xl font-bold text-green-600">{teachingStats.total_minutes}</p>
                <p className="text-sm text-gray-500">学习分钟</p>
              </div>
              <div className="text-center p-4 bg-purple-50 rounded-xl">
                <p className="text-2xl font-bold text-purple-600">{teachingStats.questions_asked}</p>
                <p className="text-sm text-gray-500">提问次数</p>
              </div>
              <div className="text-center p-4 bg-amber-50 rounded-xl">
                <p className="text-2xl font-bold text-amber-600">{teachingStats.avg_test_score}</p>
                <p className="text-sm text-gray-500">平均测试分</p>
              </div>
            </div>
          </Card>

          {/* 掌握度分布 */}
          {report.mastery_distribution && Object.keys(report.mastery_distribution).length > 0 && (
            <Card className="mb-6">
              <h2 className="text-sm font-bold text-gray-700 mb-5 flex items-center gap-2">
                <span className="text-base">📈</span> 掌握度分布
              </h2>
              <div className="space-y-4">
                {Object.entries(report.mastery_distribution).map(([level, count]) => {
                  const color = level === '优秀' ? 'green' : level === '良好' ? 'blue' : level === '一般' ? 'yellow' : 'red';
                  const maxCount = report.units_completed || 1;
                  return (
                    <div key={level} className="flex items-center gap-4">
                      <span className="w-12 text-sm font-medium text-gray-600">{level}</span>
                      <div className="flex-1">
                        <ProgressBar value={count as number} max={maxCount} color={color} size="md" />
                      </div>
                      <span className="text-sm font-semibold text-gray-500 w-10 text-right">{count as number}</span>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          <div className="grid grid-cols-2 gap-4">
            {/* 薄弱知识点 */}
            {report.weak_points && report.weak_points.length > 0 && (
              <Card>
                <h2 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2">
                  <span className="text-base">🎯</span> 薄弱知识点
                </h2>
                <ul className="space-y-2.5">
                  {report.weak_points.map((point, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-gray-600">
                      <span className="w-5 h-5 rounded-full bg-red-50 text-red-400 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">!</span>
                      <span className="leading-relaxed">{point}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {/* 学习建议 */}
            {report.suggestions && report.suggestions.length > 0 && (
              <Card>
                <h2 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2">
                  <span className="text-base">💡</span> 学习建议
                </h2>
                <ul className="space-y-2.5">
                  {report.suggestions.map((suggestion, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-gray-600">
                      <span className="w-5 h-5 rounded-full bg-blue-50 text-blue-400 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">→</span>
                      <span className="leading-relaxed">{suggestion}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        </>
      ) : (
        <Card className="text-center py-16">
          <div className="text-5xl mb-4 animate-float">📊</div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">暂无学习数据</h3>
          <p className="text-sm text-gray-400">开始学习后，这里将显示你的学习报告</p>
        </Card>
      )}
    </div>
  );
}
