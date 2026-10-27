import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import ProgressBar from '../components/ProgressBar';
import Icon from '../components/ui/Icon';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import EmptyState from '../components/ui/EmptyState';
import { HomeSkeleton } from '../components/ui/Skeleton';
import { getBooks } from '../api/books';
import { getLearningStats } from '../api/learning';
import { LAST_BOOK_KEY, type LastBook } from '../utils/lastBook';
import type { Book, LearningStats } from '../types';

type SortKey = 'recent' | 'progress' | 'title';

const FILE_TILE: Record<string, string> = {
  pdf: 'from-rose-100 to-orange-100 text-rose-500',
  epub: 'from-emerald-100 to-teal-100 text-emerald-500',
  txt: 'from-blue-100 to-indigo-100 text-blue-500',
};

function readLastBook(): LastBook | null {
  try {
    const raw = localStorage.getItem(LAST_BOOK_KEY);
    return raw ? (JSON.parse(raw) as LastBook) : null;
  } catch {
    return null;
  }
}

export default function Home() {
  const navigate = useNavigate();
  const [books, setBooks] = useState<Book[]>([]);
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('recent');

  useEffect(() => {
    (async () => {
      const [booksData, statsData] = await Promise.allSettled([getBooks(), getLearningStats()]);
      if (booksData.status === 'fulfilled') setBooks(booksData.value);
      if (statsData.status === 'fulfilled') setStats(statsData.value);
      setLoading(false);
    })();
  }, []);

  const lastBook = useMemo(() => {
    const last = readLastBook();
    if (!last) return null;
    return books.find(b => b.id === last.id) ?? null;
  }, [books]);

  const visibleBooks = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    let list = kw
      ? books.filter(b =>
          b.title.toLowerCase().includes(kw) || (b.author ?? '').toLowerCase().includes(kw))
      : [...books];
    switch (sortKey) {
      case 'progress':
        list.sort((a, b) =>
          (b.total_units ? b.learned_units / b.total_units : 0) -
          (a.total_units ? a.learned_units / a.total_units : 0));
        break;
      case 'title':
        list.sort((a, b) => a.title.localeCompare(b.title, 'zh'));
        break;
      default:
        // 后端已按创建时间倒序返回
        break;
    }
    return list;
  }, [books, keyword, sortKey]);

  if (loading) return <HomeSkeleton />;

  const statCards = stats ? [
    { label: '学习天数', value: stats.total_days, unit: '天', icon: 'calendar', cls: 'bg-blue-50 text-blue-600', num: 'text-blue-600' },
    { label: '完成单元', value: stats.completed_units, unit: '个', icon: 'checkCircle', cls: 'bg-emerald-50 text-emerald-600', num: 'text-emerald-600' },
    { label: '今日学习', value: stats.today_minutes, unit: '分钟', icon: 'clock', cls: 'bg-purple-50 text-purple-600', num: 'text-purple-600' },
    { label: '连续学习', value: stats.streak_days, unit: '天', icon: 'fire', cls: 'bg-amber-50 text-amber-600', num: 'text-amber-600' },
  ] : [];

  return (
    <div className="animate-fade-in">
      {/* 欢迎横幅 */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-blue-600 via-blue-500 to-purple-600 p-8 mb-8 text-white shadow-xl shadow-blue-500/15">
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold mb-2">欢迎回来 👋</h1>
            <p className="text-blue-100 text-sm max-w-md">
              {books.length > 0
                ? `你已上传 ${books.length} 本书籍，继续学习之旅吧！`
                : '上传你的第一本书，开启智能学习之旅'}
            </p>
          </div>
          {lastBook && (
            <button
              onClick={() => navigate(`/books/${lastBook.id}`)}
              className="group flex items-center gap-3 pl-4 pr-5 py-3 bg-white/15 hover:bg-white/25 backdrop-blur rounded-xl border border-white/20 transition-all text-left"
            >
              <span className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center shrink-0">
                <Icon name="play" className="w-4 h-4" />
              </span>
              <span>
                <span className="block text-[10px] uppercase tracking-wider text-blue-100">继续学习</span>
                <span className="block text-sm font-semibold max-w-[180px] truncate">{lastBook.title}</span>
              </span>
              <Icon name="chevronRight" className="w-4 h-4 text-blue-100 group-hover:translate-x-0.5 transition-transform" />
            </button>
          )}
        </div>
        <div className="absolute -right-6 -top-6 w-32 h-32 rounded-full bg-white/10 blur-2xl pointer-events-none" />
        <div className="absolute -right-2 -bottom-8 w-24 h-24 rounded-full bg-purple-400/20 blur-xl pointer-events-none" />
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {statCards.map((s, i) => (
            <Card key={s.label} hover={false} className={`animate-fade-in delay-${(i + 1) * 100}`}>
              <div className="flex items-start justify-between mb-3">
                <span className={`w-9 h-9 rounded-xl flex items-center justify-center ${s.cls}`}>
                  <Icon name={s.icon} className="w-[18px] h-[18px]" />
                </span>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{s.label}</span>
              </div>
              <p className={`text-3xl font-bold tracking-tight ${s.num}`}>{s.value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{s.unit}</p>
            </Card>
          ))}
        </div>
      )}

      {/* 书籍列表头部 */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h2 className="text-lg font-bold text-gray-800">我的书籍</h2>
          <p className="text-xs text-gray-400 mt-0.5">{books.length} 本书籍</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" icon="refresh" onClick={() => navigate('/sync')}>同步中心</Button>
          <Button icon="plus" onClick={() => navigate('/upload')}>上传新书</Button>
        </div>
      </div>

      {/* 搜索与排序 */}
      {books.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-5">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Icon name="search" className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={keyword}
              onChange={e => setKeyword(e.target.value)}
              placeholder="搜索书名或作者..."
              className="w-full pl-9 pr-3 py-2 bg-white border border-gray-200 rounded-xl text-sm
                focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100 transition-all"
            />
          </div>
          <select
            value={sortKey}
            onChange={e => setSortKey(e.target.value as SortKey)}
            className="px-3 py-2 bg-white border border-gray-200 rounded-xl text-sm text-gray-600
              focus:outline-none focus:border-blue-300"
          >
            <option value="recent">最近添加</option>
            <option value="progress">按进度</option>
            <option value="title">按书名</option>
          </select>
        </div>
      )}

      {books.length === 0 ? (
        <Card hover={false}>
          <EmptyState
            icon="bookOpen"
            title="还没有书籍"
            description="上传你的第一本书，系统将自动解析内容并生成知识单元"
            action={<Button size="lg" icon="upload" onClick={() => navigate('/upload')}>上传第一本书</Button>}
          />
        </Card>
      ) : visibleBooks.length === 0 ? (
        <Card hover={false}>
          <EmptyState icon="search" title="没有匹配的书籍" description={`找不到与「${keyword}」相关的书名或作者`} />
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {visibleBooks.map((book, i) => (
            <Card
              key={book.id}
              className={`animate-fade-in delay-${Math.min((i + 1) * 100, 400)} group`}
              onClick={() => navigate(`/books/${book.id}`)}
            >
              <div className="flex items-start gap-4">
                <div className={`w-12 h-16 rounded-lg bg-gradient-to-br flex items-center justify-center shrink-0 shadow-sm ${FILE_TILE[book.file_type] || 'from-gray-100 to-slate-100 text-gray-400'}`}>
                  <Icon name="bookOpen" className="w-6 h-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-800 truncate group-hover:text-blue-600 transition-colors">{book.title}</h3>
                  {book.author && <p className="text-xs text-gray-400 mt-0.5 truncate">{book.author}</p>}
                  <div className="flex items-center gap-2 mt-2">
                    <Badge>{book.total_chapters} 章节</Badge>
                    <Badge className="uppercase">{book.file_type}</Badge>
                    {book.total_units > 0 && book.learned_units >= book.total_units && (
                      <Badge tone="green">已学完</Badge>
                    )}
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
