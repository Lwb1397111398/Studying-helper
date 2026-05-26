import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import { exportReview } from '../api/review';

interface ExportFormat {
  id: string;
  label: string;
  desc: string;
  icon: string;
  ext: string;
}

const FORMATS: ExportFormat[] = [
  { id: 'anki',          label: 'Anki 卡片',   desc: 'TSV 格式，可直接导入 Anki 复习',       icon: '🃏', ext: '.tsv' },
  { id: 'markdown',      label: 'Markdown 笔记', desc: '按章节整理的复习笔记，含掌握度标记', icon: '📝', ext: '.md' },
  { id: 'mind_map_mermaid', label: '思维导图 (Mermaid)', desc: 'Mermaid 格式知识图谱',         icon: '🧠', ext: '.mmd' },
  { id: 'mind_map_plantuml', label: '思维导图 (PlantUML)', desc: 'PlantUML 格式知识图谱',     icon: '🌳', ext: '.puml' },
  { id: 'wrong_answers', label: '错题集',       desc: '整理所有答错的题目和解析',             icon: '❌', ext: '.md' },
];

export default function Export() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [exporting, setExporting] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const handleExport = async (format: ExportFormat) => {
    setExporting(format.id);
    setDone(null);
    try {
      const result = await exportReview(bookId!, '当前书籍', format.id);
      // 创建下载
      const blob = new Blob([result.content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setDone(format.id);
    } catch (error) {
      console.error('导出失败:', error);
      alert('导出失败，请重试');
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-800">导出复习资料</h1>
          <p className="text-xs text-gray-400 mt-0.5">选择格式导出，随时随地复习</p>
        </div>
        <button onClick={() => navigate(`/books/${bookId}`)}
          className="px-4 py-2 text-gray-500 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors">
          ← 返回
        </button>
      </div>

      <div className="space-y-3">
        {FORMATS.map((format) => (
          <Card key={format.id} className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center text-2xl shrink-0">
              {format.icon}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-gray-800">{format.label}</h3>
              <p className="text-xs text-gray-400 mt-0.5">{format.desc}</p>
            </div>
            <button
              onClick={() => handleExport(format)}
              disabled={exporting === format.id}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all shrink-0 ${
                done === format.id
                  ? 'bg-emerald-100 text-emerald-700'
                  : exporting === format.id
                  ? 'bg-gray-100 text-gray-400 cursor-wait'
                  : 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:shadow-lg hover:shadow-blue-500/25'
              }`}
            >
              {exporting === format.id ? (
                <>
                  <span className="animate-spin">⏳</span> 导出中...
                </>
              ) : done === format.id ? (
                <>
                  ✓ 已下载
                </>
              ) : (
                <>
                  📥 导出{format.ext}
                </>
              )}
            </button>
          </Card>
        ))}
      </div>

      <Card className="mt-6 bg-blue-50/50 border-blue-100">
        <div className="flex items-start gap-3">
          <span className="text-lg">💡</span>
          <div>
            <h3 className="text-sm font-semibold text-blue-800 mb-1">使用提示</h3>
            <ul className="text-xs text-blue-600 space-y-1">
              <li>• <strong>Anki 卡片</strong>：导入 Anki 后自动按间隔重复算法安排复习</li>
              <li>• <strong>Markdown 笔记</strong>：可用 Obsidian、Notion 等工具打开</li>
              <li>• <strong>思维导图</strong>：Mermaid 可在 GitHub/Notion 渲染，PlantUML 可用 VS Code 插件预览</li>
              <li>• <strong>错题集</strong>：记录所有答错的题目，方便针对性复习</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
