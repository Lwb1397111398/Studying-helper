import { useState } from 'react';
import Card from '../Card';
import ProgressBar from '../ProgressBar';
import Icon from '../ui/Icon';
import Badge from '../ui/Badge';
import UnitDetailPanel from './UnitDetailPanel';
import type { Chapter, MasteryRecord } from '../../types';

// 根据层级深度生成样式标记，不硬编码名称
const getLevelBadge = (level: number) => {
  const colors = [
    'bg-blue-100 text-blue-700',
    'bg-indigo-100 text-indigo-700',
    'bg-violet-100 text-violet-700',
    'bg-purple-100 text-purple-700',
    'bg-fuchsia-100 text-fuchsia-700',
  ];
  return colors[Math.min(level, colors.length - 1)];
};

// 根据层级深度生成渐变色
const getLevelGradient = (depth: number) => {
  const gradients = [
    'from-blue-500 to-purple-500',
    'from-indigo-500 to-blue-500',
    'from-violet-500 to-indigo-500',
    'from-purple-500 to-violet-500',
    'from-fuchsia-500 to-purple-500',
  ];
  return gradients[Math.min(depth, gradients.length - 1)];
};

// 层级标题字体大小
const getLevelTitleClass = (level: number): string => {
  switch (level) {
    case 0: return 'text-xl font-bold text-gray-900';
    case 1: return 'text-lg font-semibold text-gray-800';
    case 2: return 'text-base font-medium text-gray-700';
    default: return 'text-sm font-medium text-gray-600';
  }
};

// 中文层级名称
const getLevelName = (level: number): string => {
  const names = ['编', '章', '节', '小节', '条'];
  return names[Math.min(level, names.length - 1)] || `L${level}`;
};

interface ChapterNodeProps {
  chapter: Chapter;
  depth: number;
  index: number;
  mastery: MasteryRecord[];
  expandedUnitId: string | null;
  onUnitClick: (unitId: string) => void;
  onRelearn: (unitId: string) => Promise<void>;
  onEnrich: (unitId: string) => Promise<void>;
  onUnitLoop?: (unitId: string) => Promise<void>;
  unitLoopLoading?: boolean;
}

/** 递归章节节点：容器章节可折叠，叶子章节展示知识单元列表 */
export default function ChapterNode({
  chapter, depth, index, mastery, expandedUnitId,
  onUnitClick, onRelearn, onEnrich, onUnitLoop, unitLoopLoading,
}: ChapterNodeProps) {
  const getUnitMastery = (unitId: string) => {
    const record = mastery.find((m) => m.knowledge_unit_id === unitId);
    return Math.round((record?.mastery_score ?? 0) * 100);
  };

  const getMasteryLevelLabel = (level: string) => {
    const map: Record<string, { label: string; tone: 'green' | 'blue' | 'amber' | 'red' }> = {
      mastered: { label: '已掌握', tone: 'green' },
      proficient: { label: '熟练', tone: 'blue' },
      familiar: { label: '熟悉', tone: 'amber' },
      beginner: { label: '初学', tone: 'red' },
    };
    return map[level] || null;
  };

  const unitCount = chapter.knowledge_units?.length || 0;
  const hasChildren = chapter.children && chapter.children.length > 0;
  const hasUnits = unitCount > 0;
  const isContainer = chapter.is_container;
  const gradientClass = getLevelGradient(depth);
  const badgeClass = getLevelBadge(chapter.level);
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Card hover={false} className={`animate-fade-in delay-${Math.min((index + 1) * 100, 400)} ${isContainer ? 'bg-gradient-to-r from-slate-50 to-gray-50 border-l-4 border-l-blue-400' : ''}`}>
      {/* 章节标题 */}
      <div
        className={`flex items-center gap-3 mb-3 ${isContainer ? 'cursor-pointer' : ''}`}
        style={{ paddingLeft: depth * 12 }}
        onClick={() => isContainer && setCollapsed(!collapsed)}
      >
        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${gradientClass} flex items-center justify-center text-white shadow-sm shrink-0`}>
          {isContainer
            ? <Icon name="folder" className="w-4 h-4" />
            : <span className="text-xs font-bold">{index + 1}</span>}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${badgeClass}`}>
              {getLevelName(chapter.level)}
            </span>
            <h3 className={`${getLevelTitleClass(chapter.level)} truncate`}>{chapter.title}</h3>
          </div>
        </div>
        {isContainer && hasChildren && (
          <Badge tone="blue">{chapter.children!.length} 子章节</Badge>
        )}
        {!isContainer && hasUnits && (
          <Badge>{unitCount} 单元</Badge>
        )}
        {isContainer && (
          <Icon name="chevronDown" className={`w-4 h-4 text-gray-400 transition-transform ${collapsed ? '-rotate-90' : ''}`} />
        )}
      </div>

      {/* 子章节递归渲染 */}
      {hasChildren && !collapsed && (
        <div className={`space-y-3 pl-6 ml-4 border-l-2 ${isContainer ? 'border-blue-200' : 'border-gray-100'}`}>
          {chapter.children!.map((child, i) => (
            <ChapterNode
              key={child.id}
              chapter={child}
              depth={depth + 1}
              index={i}
              mastery={mastery}
              expandedUnitId={expandedUnitId}
              onUnitClick={onUnitClick}
              onRelearn={onRelearn}
              onEnrich={onEnrich}
              onUnitLoop={onUnitLoop}
              unitLoopLoading={unitLoopLoading}
            />
          ))}
        </div>
      )}

      {/* 知识单元列表（容器节点不显示） */}
      {!isContainer && hasUnits && (
        <div className="space-y-2 pl-11 mt-2">
          {chapter.knowledge_units.map((unit) => {
            const score = getUnitMastery(unit.id);
            const record = mastery.find((m) => m.knowledge_unit_id === unit.id);
            const levelInfo = getMasteryLevelLabel(record?.mastery_level || '');
            const hasAiContent = !!unit.summary;
            const isExpanded = expandedUnitId === unit.id;

            return (
              <div key={unit.id}>
                <div className="flex items-center gap-3 group cursor-pointer" onClick={() => onUnitClick(unit.id)}>
                  <div className="flex-1 flex items-center gap-2 min-w-0">
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${score >= 80 ? 'bg-emerald-400' : score >= 50 ? 'bg-amber-400' : score > 0 ? 'bg-red-400' : 'bg-gray-300'}`} />
                    <p className="text-sm text-gray-600 group-hover:text-gray-800 transition-colors truncate">{unit.title}</p>
                    {hasAiContent && <Badge tone="blue">已学习</Badge>}
                    {levelInfo && <Badge tone={levelInfo.tone}>{levelInfo.label}</Badge>}
                  </div>
                  <div className="w-24 hidden sm:block shrink-0">
                    <ProgressBar value={score} size="sm" color={score >= 80 ? 'green' : score >= 50 ? 'yellow' : 'red'} />
                  </div>
                  <span className="text-xs text-gray-400 w-10 text-right font-medium shrink-0">{score}%</span>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                      {onUnitLoop && (
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (!unitLoopLoading) await onUnitLoop(unit.id);
                          }}
                          disabled={!!unitLoopLoading}
                          className="p-1 text-blue-500 hover:text-blue-600 rounded hover:bg-blue-50 transition-colors disabled:opacity-40"
                          title="启动单单元闭环（分析+教学 v2）">
                          <Icon name="bolt" className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {hasAiContent && (
                        <>
                      <button
                        onClick={async (e) => { e.stopPropagation(); await onRelearn(unit.id); }}
                        className="p-1 text-purple-500 hover:text-purple-600 rounded hover:bg-purple-50 transition-colors"
                        title="重新生成 AI 分析">
                        <Icon name="refresh" className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={async (e) => { e.stopPropagation(); await onEnrich(unit.id); }}
                        className="p-1 text-emerald-500 hover:text-emerald-600 rounded hover:bg-emerald-50 transition-colors"
                        title="增量更新（补充例子）">
                        <Icon name="sparkles" className="w-3.5 h-3.5" />
                      </button>
                        </>
                      )}
                    </div>
                  <Icon name="chevronRight" className={`w-3.5 h-3.5 text-gray-400 transition-transform shrink-0 ${isExpanded ? 'rotate-90' : ''}`} />
                </div>

                {/* 展开的详情面板 */}
                {isExpanded && <UnitDetailPanel unitId={unit.id} />}
              </div>
            );
          })}
        </div>
      )}

      {/* 无子章节也无单元时显示提示 */}
      {!isContainer && !hasChildren && !hasUnits && (
        <p className="text-sm text-gray-400 pl-11">暂无知识单元</p>
      )}
    </Card>
  );
}
