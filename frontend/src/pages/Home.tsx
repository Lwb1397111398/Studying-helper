import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { getBooks } from '../api/books';
import { getLearningStats } from '../api/learning';
import type { Book, LearningStats } from '../types';

const FILE_ICONS: Record<string, string> = { pdf: '📄', epub: '📚', txt: '📝' };

export default function Home() {
  const navigate = useNavigate();
  const [books, setBooks] = useState<Book[]>([]);
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const [booksData, statsData] = await Promise.allSettled([getBooks(), getLearningStats()]);
      if (booksData.status === 'fulfilled') setBooks(booksData.value);
      if (statsData.status === 'fulfilled') setStats(statsData.value);
    } catch (error) {
      console.error('加载数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Loading />;

  return (
    <div className="animate-fade-in">
      {/* 欢迎横幅 */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-blue-600 via-blue-500 to-purple-600 p-8 mb-8 text-white shadow-xl shadow-blue-500/15">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PHBhdGggZD0iTTM2IDM0djItSDI0di0yaDEyem0wLTRWMjhIMjR2Mmgxem0tMi0ydi0ySDI2djJoOHptMC00di0ySDI2djJoOHoiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-30" />
        <div className="relative">
          <h1 className="text-2xl font-bold mb-2">欢迎回来 👋</h1>
          <p className="text-blue-100 text-sm max-w-md">
            {books.length > 0
              ? `你已上传 ${books.length} 本书籍，继续学习之旅吧！`
              : '上传你的第一本书，开启智能学习之旅'}
          </p>
        </div>
        <div className="absolute -right-6 -top-6 w-32 h-32 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute -right-2 -bottom-8 w-24 h-24 rounded-full bg-purple-400/20 blur-xl" />
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: '学习天数', value: stats.total_days, unit: '天', color: 'blue', icon: '📅' },
            { label: '完成单元', value: stats.completed_units, unit: '个', color: 'green', icon: '✅' },
            { label: '今日学习', value: stats.today_minutes, unit: '分钟', color: 'purple', icon: '⏱️' },
            { label: '连续学习', value: stats.streak_days, unit: '天', color: 'yellow', icon: '🔥' },
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
              <p className="text-xs text-gray-400 mt-0.5">{s.unit}</p>
            </Card>
          ))}
        </div>
      )}

      {/* 书籍列表 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-bold text-gray-800">我的书籍</h2>
          <p className="text-xs text-gray-400 mt-0.5">{books.length} 本书籍</p>
        </div>
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 hover:-translate-y-0.5 transition-all duration-200"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
          </svg>
          上传新书
        </button>
      </div>

      {books.length === 0 ? (
        <Card className="text-center py-16 animate-fade-in">
          <div className="text-6xl mb-4 animate-float">📚</div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">还没有书籍</h3>
          <p className="text-sm text-gray-400 mb-6 max-w-sm mx-auto">上传你的第一本书，系统将自动解析内容并生成知识单元</p>
          <button
            onClick={() => navigate('/upload')}
            className="px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all duration-200"
          >
            上传第一本书
          </button>
        </Card>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {books.map((book, i) => (
            <Card
              key={book.id}
              className={`animate-fade-in delay-${Math.min((i + 1) * 100, 400)} group`}
              onClick={() => navigate(`/books/${book.id}`)}
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-16 rounded-lg bg-gradient-to-br from-blue-100 to-purple-100 flex items-center justify-center text-2xl shrink-0 shadow-sm">
                  {FILE_ICONS[book.file_type] || '📖'}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-800 truncate group-hover:text-blue-600 transition-colors">{book.title}</h3>
                  {book.author && <p className="text-xs text-gray-400 mt-0.5 truncate">{book.author}</p>}
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-[10px] text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">{book.total_chapters} 章节</span>
                    <span className="text-[10px] text-gray-400 uppercase">{book.file_type}</span>
                  </div>
                </div>
              </div>
              {/* 进度条 */}
              {book.total_units > 0 && (
                <div className="mt-4 pt-3 border-t border-gray-50">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] text-gray-400">学习进度</span>
                    <span className="text-[10px] font-medium text-gray-500">
                      {book.learned_units}/{book.total_units}
                    </span>
                  </div>
                  <ProgressBar
                    value={book.learned_units}
                    max={book.total_units}
                    size="sm"
                    color={book.learned_units >= book.total_units ? 'green' : 'blue'}
                  />
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
