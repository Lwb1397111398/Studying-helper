import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import { getTocPreview, confirmToc } from '../api/books';
import type { TocItem } from '../api/books';

interface EditableTocItem extends TocItem {
  children: EditableTocItem[];
}

export default function TocConfirm() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [tocItems, setTocItems] = useState<EditableTocItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (bookId) loadToc();
  }, [bookId]);

  const loadToc = async () => {
    try {
      setLoading(true);
      const response = await getTocPreview(bookId!);
      // 扁平化树形结构
      const flatItems = flattenTocTree(response.toc);
      setTocItems(flatItems);
      if (flatItems.length > 0) {
        setSelectedId(flatItems[0].id);
      }
    } catch (err: any) {
      setError(err.message || '加载目录失败');
    } finally {
      setLoading(false);
    }
  };

  // 扁平化树形结构为可编辑列表
  const flattenTocTree = (items: TocItem[]): EditableTocItem[] => {
    const result: EditableTocItem[] = [];

    const traverse = (node: TocItem) => {
      const flatNode: EditableTocItem = {
        ...node,
        children: [],
      };
      result.push(flatNode);
      if (node.children) {
        node.children.forEach(traverse);
      }
    };

    items.forEach(traverse);
    return result;
  };

  // 更新标题
  const updateTitle = (id: string, title: string) => {
    setTocItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, title } : item))
    );
  };

  // 更新层级
  const updateLevel = (id: string, level: number) => {
    setTocItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, level } : item))
    );
  };

  // 删除节点
  const deleteItem = (id: string) => {
    setTocItems((prev) => prev.filter((item) => item.id !== id));
    if (selectedId === id) {
      setSelectedId(tocItems.length > 1 ? tocItems[0].id : null);
    }
  };

  // 添加节点
  const addItem = () => {
    const newItem: EditableTocItem = {
      id: `new-${Date.now()}`,
      title: '新章节',
      level: 0,
      char_offset: 0,
      children: [],
    };
    setTocItems((prev) => [...prev, newItem]);
    setSelectedId(newItem.id);
  };

  // 重置
  const handleReset = () => {
    if (confirm('确定要重新加载目录吗？当前编辑将丢失。')) {
      loadToc();
    }
  };

  // 确认并拆分
  const handleConfirm = async () => {
    if (tocItems.length === 0) {
      setError('目录不能为空');
      return;
    }

    // 校验：至少要有 level 0 的章节
    const level0Items = tocItems.filter((item) => item.level === 0);
    if (level0Items.length === 0) {
      setError('至少需要有一个顶级章节（level 0）');
      return;
    }

    // 校验：标题不能为空
    const emptyTitles = tocItems.filter((item) => !item.title.trim());
    if (emptyTitles.length > 0) {
      setError('章节标题不能为空');
      return;
    }

    try {
      setSaving(true);
      setError('');

      // 转换为 API 格式
      const items = tocItems.map((item) => ({
        title: item.title.trim(),
        level: item.level,
        char_offset: item.char_offset,
      }));

      await confirmToc(bookId!, items);
      navigate(`/books/${bookId}`);
    } catch (err: any) {
      setError(err.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Loading />;
  if (error && tocItems.length === 0) {
    return (
      <div className="max-w-4xl mx-auto">
        <Card className="text-center py-12">
          <div className="text-5xl mb-4">⚠️</div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">加载失败</h3>
          <p className="text-sm text-gray-400 mb-6">{error}</p>
          <button
            onClick={handleReset}
            className="px-6 py-2 bg-blue-500 text-white rounded-xl text-sm hover:bg-blue-400"
          >
            重试
          </button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto animate-fade-in">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800 mb-1">编辑目录</h1>
          <p className="text-sm text-gray-400">
            共 {tocItems.length} 个章节，{tocItems.filter((i) => i.level === 0).length} 个顶级章节
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            className="px-4 py-2 bg-gray-100 text-gray-600 rounded-xl text-sm hover:bg-gray-200"
          >
            🔄 重置
          </button>
          <button
            onClick={handleConfirm}
            disabled={saving}
            className="px-6 py-2 bg-blue-500 text-white rounded-xl text-sm hover:bg-blue-400 disabled:opacity-50"
          >
            {saving ? '保存中...' : '✅ 确认拆分'}
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-100 rounded-xl flex items-center gap-3">
          <span className="text-red-500">⚠️</span>
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {/* 目录编辑区 */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">目录结构</h2>
          <button
            onClick={addItem}
            className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-sm hover:bg-blue-100"
          >
            + 添加章节
          </button>
        </div>

        {tocItems.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <div className="text-5xl mb-4">📂</div>
            <p className="mb-4">暂无目录数据</p>
            <button
              onClick={addItem}
              className="px-4 py-2 bg-blue-500 text-white rounded-xl text-sm hover:bg-blue-400"
            >
              手动添加章节
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {tocItems.map((item, index) => (
              <div
                key={item.id}
                className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
                  selectedId === item.id
                    ? 'border-blue-300 bg-blue-50/50'
                    : 'border-gray-100 hover:border-gray-200'
                }`}
                onClick={() => setSelectedId(item.id)}
              >
                {/* 层级缩进指示 */}
                <div className="flex items-center gap-1 w-16">
                  <select
                    value={item.level}
                    onChange={(e) => updateLevel(item.id, Number(e.target.value))}
                    onClick={(e) => e.stopPropagation()}
                    className="px-2 py-1 bg-white border border-gray-200 rounded-lg text-xs focus:outline-none focus:border-blue-300"
                  >
                    <option value={0}>Level 0</option>
                    <option value={1}>Level 1</option>
                    <option value={2}>Level 2</option>
                  </select>
                </div>

                {/* 序号 */}
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
                  {index + 1}
                </div>

                {/* 标题输入 */}
                <input
                  type="text"
                  value={item.title}
                  onChange={(e) => updateTitle(item.id, e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-300"
                />

                {/* 操作按钮 */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteItem(item.id);
                    }}
                    className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 底部提示 */}
      <div className="mt-6 p-4 bg-amber-50 border border-amber-100 rounded-xl">
        <div className="flex items-start gap-3">
          <span className="text-amber-500">💡</span>
          <div className="text-sm text-amber-700">
            <p className="font-medium mb-1">编辑说明</p>
            <ul className="list-disc list-inside space-y-1 text-amber-600">
              <li>Level 0 = 顶级章节（第X章、第X部分等）</li>
              <li>Level 1 = 节（第X节、X.X 格式等）</li>
              <li>Level 2 = 小节（X.X.X 格式）</li>
              <li>确认后将根据目录重新拆分知识单元</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
