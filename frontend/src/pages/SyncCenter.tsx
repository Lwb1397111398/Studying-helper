import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import { getBooks } from '../api/books';
import {
  exportAllSyncPackage,
  exportSyncPackage,
  importSyncPackage,
  previewSyncPackage,
  type SyncImportResult,
  type SyncPreviewResult,
} from '../api/sync';
import type { Book } from '../types';

function downloadJson(content: Record<string, unknown>, filename: string) {
  const blob = new Blob([JSON.stringify(content, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-gray-600 border border-gray-100">
      {label}：{value}
    </span>
  );
}

export default function SyncCenter() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previewRequestRef = useRef(0);
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<SyncPreviewResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<SyncImportResult | null>(null);

  useEffect(() => {
    getBooks()
      .then(setBooks)
      .catch((error) => {
        console.error('加载书籍失败:', error);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleExportAll = async () => {
    setExporting('all');
    try {
      const data = await exportAllSyncPackage();
      downloadJson(data, 'studying-helper-sync.json');
    } catch (error) {
      console.error('导出全部同步包失败:', error);
      alert('导出全部同步包失败，请重试');
    } finally {
      setExporting(null);
    }
  };

  const handleExportBook = async (book: Book) => {
    setExporting(book.id);
    try {
      const data = await exportSyncPackage(book.id);
      downloadJson(data, `studying-helper-${book.id}-sync.json`);
    } catch (error) {
      console.error('导出书籍同步包失败:', error);
      alert('导出书籍同步包失败，请重试');
    } finally {
      setExporting(null);
    }
  };

  const handleSelectFile = async (file: File | undefined) => {
    if (!file) return;
    const requestId = previewRequestRef.current + 1;
    previewRequestRef.current = requestId;
    setSelectedFile(file);
    setPreview(null);
    setImportResult(null);
    try {
      const result = await previewSyncPackage(file);
      if (previewRequestRef.current === requestId) {
        setPreview(result);
      }
    } catch (error) {
      if (previewRequestRef.current !== requestId) return;
      console.error('同步包预览失败:', error);
      alert('同步包预览失败，请检查文件是否正确');
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleImport = async () => {
    if (!selectedFile) return;
    setImporting(true);
    try {
      const result = await importSyncPackage(selectedFile);
      setImportResult(result);
      setPreview(null);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      const refreshed = await getBooks();
      setBooks(refreshed);
    } catch (error) {
      console.error('同步包导入失败:', error);
      alert('同步包导入失败，请检查文件后重试');
    } finally {
      setImporting(false);
    }
  };

  if (loading) return <Loading />;

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">同步中心</h1>
          <p className="text-sm text-gray-400 mt-1">在电脑端和 Android 端之间双向导入导出学习数据</p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 text-gray-500 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors"
        >
          返回首页
        </button>
      </div>

      <div className="grid grid-cols-2 gap-5 mb-6">
        <Card hover={false} gradient>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl mb-4">⇩</div>
              <h2 className="text-lg font-semibold text-gray-800">导出到手机</h2>
              <p className="text-sm text-gray-400 mt-2">导出电脑端全部书籍、学习进度、复习记录和教学记录。</p>
            </div>
            <button
              onClick={handleExportAll}
              disabled={exporting === 'all'}
              className="px-4 py-2 rounded-xl text-sm font-medium bg-gradient-to-r from-emerald-500 to-emerald-600 text-white hover:shadow-lg hover:shadow-emerald-500/25 disabled:bg-gray-100 disabled:text-gray-400 disabled:shadow-none"
            >
              {exporting === 'all' ? '导出中...' : '导出全部'}
            </button>
          </div>
        </Card>

        <Card hover={false} gradient>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl mb-4">⇧</div>
              <h2 className="text-lg font-semibold text-gray-800">从手机导入</h2>
              <p className="text-sm text-gray-400 mt-2">先预览同步包内容，再确认覆盖导入对应书籍进度。</p>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-4 py-2 rounded-xl text-sm font-medium bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:shadow-lg hover:shadow-blue-500/25"
            >
              选择同步包
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(event) => handleSelectFile(event.target.files?.[0])}
            />
          </div>
        </Card>
      </div>

      {preview && (
        <Card className="mb-6 border-blue-100 bg-blue-50/40" hover={false}>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-800">同步包预览</h2>
              <p className="text-sm text-gray-500 mt-1">
                来源：{preview.source === 'android' ? 'Android 手机端' : '电脑端'} · {preview.books_count} 本书 · {preview.units_count} 个知识单元
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                <StatPill label="章节" value={preview.chapters_count} />
                <StatPill label="知识单元" value={preview.units_count} />
                <StatPill label="掌握记录" value={preview.mastery_records_count} />
                <StatPill label="注释" value={preview.annotations_count} />
                <StatPill label="图谱节点" value={preview.kg_nodes_count} />
                <StatPill label="图谱关系" value={preview.kg_edges_count} />
                <StatPill label="每日统计" value={preview.daily_stats_count} />
                <StatPill label="学习记录" value={preview.learning_records_count} />
                <StatPill label="复习/考试" value={preview.review_sessions_count} />
                <StatPill label="教学会话" value={preview.teaching_sessions_count} />
                <StatPill label="用户提问" value={preview.user_questions_count} />
                <StatPill label="阶段测试" value={preview.session_tests_count} />
                <StatPill label="效率记录" value={preview.learning_efficiency_count} />
                <StatPill label="学习画像" value={preview.learner_intent_profiles_count} />
                <StatPill label="教学设计" value={preview.teaching_designs_count} />
                <StatPill label="模块编排" value={preview.module_micro_plans_count} />
              </div>
            </div>
            <button
              onClick={handleImport}
              disabled={importing}
              className="px-4 py-2 rounded-xl text-sm font-medium bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:shadow-lg hover:shadow-blue-500/25 disabled:bg-gray-100 disabled:text-gray-400 disabled:shadow-none"
            >
              {importing ? '导入中...' : '确认导入'}
            </button>
          </div>
          <div className="space-y-2">
            {preview.books.map((book) => (
              <div key={book.id} className="flex items-center justify-between rounded-xl bg-white px-4 py-3 border border-blue-100/70">
                <div>
                  <p className="text-sm font-medium text-gray-800">{book.title}</p>
                  <p className="text-xs text-gray-400">更新时间：{new Date(book.source_updated_at).toLocaleString()}</p>
                </div>
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${book.will_overwrite ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                  {book.will_overwrite ? `将覆盖：${book.local_title}` : '新增导入'}
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-amber-600 mt-4">导入会覆盖同 ID 书籍在电脑端的本地数据，请确认后继续。</p>
        </Card>
      )}

      {importResult && (
        <Card className="mb-6 border-emerald-100 bg-emerald-50/40" hover={false}>
          <h2 className="text-lg font-semibold text-emerald-800 mb-2">导入完成</h2>
          <div className="flex flex-wrap gap-2 mt-3">
            <StatPill label="书籍" value={importResult.books_imported} />
            <StatPill label="章节" value={importResult.chapters_imported} />
            <StatPill label="知识单元" value={importResult.units_imported} />
            <StatPill label="掌握记录" value={importResult.mastery_records_imported} />
            <StatPill label="注释" value={importResult.annotations_imported} />
            <StatPill label="图谱节点" value={importResult.kg_nodes_imported} />
            <StatPill label="图谱关系" value={importResult.kg_edges_imported} />
            <StatPill label="学习记录" value={importResult.learning_records_imported} />
            <StatPill label="每日统计" value={importResult.daily_stats_imported} />
            <StatPill label="复习/考试" value={importResult.review_sessions_imported} />
            <StatPill label="教学会话" value={importResult.teaching_sessions_imported} />
            <StatPill label="教学消息" value={importResult.teaching_messages_imported} />
            <StatPill label="用户提问" value={importResult.user_questions_imported} />
            <StatPill label="阶段测试" value={importResult.session_tests_imported} />
            <StatPill label="效率记录" value={importResult.learning_efficiency_imported} />
            <StatPill label="学习画像" value={importResult.learner_intent_profiles_imported} />
            <StatPill label="教学设计" value={importResult.teaching_designs_imported} />
            <StatPill label="模块编排" value={importResult.module_micro_plans_imported} />
          </div>
          {importResult.overwritten_books.length > 0 && (
            <p className="text-xs text-emerald-600 mt-2">覆盖书籍：{importResult.overwritten_books.join('、')}</p>
          )}
        </Card>
      )}

      <Card hover={false}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">按书籍导出</h2>
            <p className="text-sm text-gray-400 mt-1">只同步某一本书时使用。</p>
          </div>
          <button
            onClick={() => navigate('/upload')}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            上传新书
          </button>
        </div>
        {books.length === 0 ? (
          <p className="text-sm text-gray-400 py-6 text-center">还没有书籍，上传或从手机导入后即可同步。</p>
        ) : (
          <div className="space-y-2">
            {books.map((book) => (
              <div key={book.id} className="flex items-center justify-between rounded-xl border border-gray-100 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-800">{book.title}</p>
                  <p className="text-xs text-gray-400">{book.total_chapters} 章节 · {book.total_units} 知识单元 · 已学 {book.learned_units}</p>
                </div>
                <button
                  onClick={() => handleExportBook(book)}
                  disabled={exporting === book.id}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:text-gray-400"
                >
                  {exporting === book.id ? '导出中...' : '导出本书'}
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
