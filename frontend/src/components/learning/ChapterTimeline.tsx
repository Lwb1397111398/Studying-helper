import type { Chapter } from '../../types';

type ChapterTreeNode = Omit<Chapter, 'children'> & { children?: ChapterTreeNode[] };

interface ChapterTimelineProps {
  chapter: ChapterTreeNode;
  depth: number;
  isLast: boolean;
  currentUnitId?: string;
  selectMode: boolean;
  selectedUnitIds: Set<string>;
  collapsedChapters: Set<string>;
  onToggleCollapse: (id: string) => void;
  onLoadUnit: (id: string) => void;
  onToggleSelection: (id: string) => void;
}

/** 时间线风格的章节树节点：容器章节可折叠，叶子章节展示知识单元 */
export default function ChapterTimelineNode({
  chapter, depth, isLast, currentUnitId, selectMode, selectedUnitIds,
  collapsedChapters, onToggleCollapse, onLoadUnit, onToggleSelection,
}: ChapterTimelineProps) {
  const isContainer = chapter.is_container;
  const units = chapter.knowledge_units || [];
  const learnedCount = units.filter((u) => u.summary).length;
  const isCollapsed = collapsedChapters.has(chapter.id);
  const hasChildren = chapter.children && chapter.children.length > 0;
  // 单单元叶子节点：合并显示，不展开单元列表
  const isMerged = !isContainer && !hasChildren && units.length === 1;
  const showUnits = !isContainer && !isMerged && !isCollapsed && units.length > 0;

  // 时间线圆点样式
  const dotStyles = [
    { size: 'w-2.5 h-2.5', color: 'bg-blue-500', ring: 'ring-2 ring-blue-100' },
    { size: 'w-2 h-2', color: 'bg-indigo-400', ring: 'ring-2 ring-indigo-50' },
    { size: 'w-1.5 h-1.5', color: 'bg-violet-400', ring: '' },
  ];
  const dot = dotStyles[Math.min(depth, dotStyles.length - 1)];

  // 字体样式
  const fontStyles = [
    'text-[11px] font-bold tracking-wide',
    'text-[11px] font-semibold',
    'text-[10.5px] font-medium text-gray-600',
  ];
  const fontClass = fontStyles[Math.min(depth, fontStyles.length - 1)];

  return (
    <div>
      {/* 章节标题行 */}
      <div className={`relative flex items-center ${isMerged && currentUnitId === units[0]?.id ? 'bg-blue-50/80 rounded' : ''}`}
        style={{ paddingLeft: depth * 14 + 8 }}>
        {/* 竖线连接（非首层） */}
        {depth > 0 && (
          <div className="absolute top-0 bottom-0 w-px bg-gray-200" style={{ left: (depth - 1) * 14 + 16 }} />
        )}

        {/* 时间线圆点 */}
        {isMerged && selectMode ? (
          <input type="checkbox" checked={selectedUnitIds.has(units[0].id)}
            onChange={(e) => { e.stopPropagation(); onToggleSelection(units[0].id); }}
            onClick={(e) => e.stopPropagation()}
            className="rounded border-gray-300 text-blue-500 focus:ring-blue-500 shrink-0 w-3 h-3 mr-2 z-10" />
        ) : (
          <div className={`shrink-0 ${isMerged ? 'w-1.5 h-1.5' : dot.size} rounded-full ${
            isMerged
              ? (units[0]?.summary ? 'bg-green-400' : 'bg-gray-300')
              : `${dot.color} ${dot.ring}`
          } mr-2 z-10`} />
        )}

        {/* 标题 */}
        <button
          onClick={() => {
            if (isMerged && !selectMode) onLoadUnit(units[0].id);
            else if (isContainer || hasChildren) onToggleCollapse(chapter.id);
            else if (units.length > 0 && !selectMode) onLoadUnit(units[0].id);
          }}
          className={`flex-1 flex items-center justify-between py-1.5 pr-2 text-left hover:bg-gray-50/80 transition-colors rounded ${fontClass} ${
            isMerged && currentUnitId === units[0]?.id ? 'text-blue-700' : ''
          } ${units.length === 0 && !isContainer && !hasChildren ? 'text-gray-400' : ''}`}>
          <span className="truncate text-gray-700">{chapter.title}</span>
          <div className="flex items-center gap-1.5 shrink-0 ml-1">
            {units.length > 0 && !isContainer && !isMerged && (
              <span className={`text-[9px] font-normal ${learnedCount === units.length ? 'text-green-500' : 'text-gray-400'}`}>
                {learnedCount}/{units.length}
              </span>
            )}
            {(isContainer || hasChildren) && (
              <span className={`text-[9px] text-gray-400 transition-transform ${isCollapsed ? '' : 'rotate-90'}`}>▶</span>
            )}
          </div>
        </button>
      </div>

      {/* 子章节 */}
      {!isCollapsed && hasChildren && chapter.children!.map((child, i) => (
        <ChapterTimelineNode
          key={child.id}
          chapter={child}
          depth={depth + 1}
          isLast={i === chapter.children!.length - 1}
          currentUnitId={currentUnitId}
          selectMode={selectMode}
          selectedUnitIds={selectedUnitIds}
          collapsedChapters={collapsedChapters}
          onToggleCollapse={onToggleCollapse}
          onLoadUnit={onLoadUnit}
          onToggleSelection={onToggleSelection}
        />
      ))}

      {/* 知识单元列表（叶子节点） */}
      {showUnits && (
        <div className="relative" style={{ paddingLeft: depth * 14 + 8 }}>
          <div className="absolute top-0 bottom-0 w-px bg-gray-200" style={{ left: depth * 14 + 16 }} />
          {units.map((unit, i) => {
            const isSelected = currentUnitId === unit.id;
            const isChecked = selectedUnitIds.has(unit.id);
            const isLastUnit = i === units.length - 1;
            return (
              <div key={unit.id}
                className={`relative flex items-center gap-1.5 pl-6 pr-2 py-1 cursor-pointer transition-colors ${
                  isSelected ? 'bg-blue-50/80' : 'hover:bg-gray-50/60'
                }`}
                onClick={() => onLoadUnit(unit.id)}>
                <div className={`absolute w-px bg-gray-200 ${isLastUnit ? 'h-2.5' : 'top-0 bottom-0'}`}
                  style={{ left: depth * 14 + 16 }} />
                <div className={`absolute w-1 h-1 rounded-full ${unit.summary ? 'bg-green-400' : 'bg-gray-300'} z-10`}
                  style={{ left: depth * 14 + 15 }} />
                {selectMode && (
                  <input type="checkbox" checked={isChecked}
                    onChange={(e) => { e.stopPropagation(); onToggleSelection(unit.id); }}
                    onClick={(e) => e.stopPropagation()}
                    className="rounded border-gray-300 text-blue-500 focus:ring-blue-500 shrink-0 w-3 h-3" />
                )}
                <span className={`text-[10px] truncate flex-1 ${isSelected ? 'text-blue-700 font-medium' : 'text-gray-500'}`}>
                  {unit.title}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
