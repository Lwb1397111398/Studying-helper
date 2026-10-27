import { useEffect, useState } from 'react';
import { getKnowledgeUnit } from '../../api/learning';
import type { KnowledgeUnit } from '../../types';

/** 知识单元展开详情：AI 摘要 / 要点 / 概念 / 难度重要性 */
export default function UnitDetailPanel({ unitId }: { unitId: string }) {
  const [detail, setDetail] = useState<KnowledgeUnit | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getKnowledgeUnit(unitId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch(() => { if (!cancelled) setDetail(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [unitId]);

  if (loading) {
    return (
      <div className="mt-3 ml-4 p-4 bg-blue-50/60 rounded-xl border border-blue-100">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          加载中...
        </div>
      </div>
    );
  }

  if (!detail?.summary) {
    return (
      <div className="mt-3 ml-4 p-4 bg-blue-50/60 rounded-xl border border-blue-100 text-center">
        <p className="text-sm text-gray-500">暂无 AI 学习数据</p>
      </div>
    );
  }

  return (
    <div className="mt-3 ml-4 p-4 bg-blue-50/60 rounded-xl border border-blue-100 animate-fade-in">
      <div className="space-y-4">
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">AI 摘要</h4>
          <p className="text-sm text-gray-700 leading-relaxed">{detail.summary}</p>
        </div>
        {detail.key_points && detail.key_points.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">关键要点</h4>
            <ul className="space-y-1">
              {detail.key_points.map((point, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                  <span className="text-blue-500 mt-0.5">•</span>
                  <span>{typeof point === 'string' ? point : point.title}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {detail.concepts && detail.concepts.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">核心概念</h4>
            <div className="flex flex-wrap gap-2">
              {detail.concepts.map((concept, idx) => (
                <span key={idx} className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-white text-gray-700 border border-gray-200 shadow-sm">
                  {typeof concept === 'string' ? concept : concept.name}
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="flex items-center gap-4 pt-2 border-t border-blue-100">
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500">难度:</span>
            <div className="flex gap-0.5">
              {[1, 2, 3, 4, 5].map((level) => (
                <div key={level} className={`w-2 h-2 rounded-full ${level <= (detail.difficulty_level || 0) ? 'bg-amber-400' : 'bg-gray-200'}`} />
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500">重要性:</span>
            <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full" style={{ width: `${((detail.importance_score || 0) * 100)}%` }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
