import type { KnowledgeUnit } from '../../types';

interface LearningPathProps {
  units: KnowledgeUnit[];
  viewingUnitId: string;
  currentUnitIndex: number;
  onViewUnit: (unitId: string) => void;
  onJumpToUnit: (unitId: string) => void;
}

/** 学习路径可视化：单元节点 + 连接线 */
export default function LearningPath({ units, viewingUnitId, currentUnitIndex, onViewUnit, onJumpToUnit }: LearningPathProps) {
  if (units.length <= 1) return null;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">学习路径</h3>
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {units.map((unit, index) => {
          const isCompleted = index < currentUnitIndex;
          const isViewing = unit.id === viewingUnitId;

          return (
            <div key={unit.id} className="flex items-center">
              <button
                onClick={() => {
                  onViewUnit(unit.id);
                  if (index !== currentUnitIndex) onJumpToUnit(unit.id);
                }}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium shrink-0 cursor-pointer hover:ring-2 hover:ring-blue-200 transition-all ${
                  isViewing
                    ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-300'
                    : isCompleted
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-500'
                }`}
              >
                <span className="w-5 h-5 flex items-center justify-center rounded-full bg-white text-xs font-bold">
                  {isCompleted ? '✓' : index + 1}
                </span>
                <span className="max-w-[100px] truncate">{unit.title || `单元${index + 1}`}</span>
              </button>
              {index < units.length - 1 && (
                <div className={`w-6 h-0.5 ${isCompleted ? 'bg-green-300' : 'bg-gray-200'}`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
