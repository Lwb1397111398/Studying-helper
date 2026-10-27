import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

/** 概念标签：对象型概念可展开弹出层（portal 渲染，避免被下方元素遮挡） */
export default function ConceptTag({ concept, index, isExpanded, onToggle, onClose }: {
  concept: string | { name: string; definition?: string; examples?: string[]; related_concepts?: string[] };
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
  onClose: () => void;
}) {
  const isObj = typeof concept !== 'string';
  const btnRef = useRef<HTMLButtonElement>(null);
  const [popupStyle, setPopupStyle] = useState<React.CSSProperties>({});
  const popupRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (isExpanded && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      const popupWidth = 288;
      let left = rect.left;
      if (left + popupWidth > window.innerWidth - 8) {
        left = window.innerWidth - popupWidth - 8;
      }
      setPopupStyle({
        position: 'fixed',
        left,
        top: rect.bottom + 4,
        zIndex: 9999,
        width: popupWidth,
      });
    }
  }, [isExpanded]);

  // 点击外部关闭
  useEffect(() => {
    if (!isExpanded) return;
    const handler = (e: MouseEvent) => {
      if (btnRef.current?.contains(e.target as Node)) return;
      if (popupRef.current?.contains(e.target as Node)) return;
      onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isExpanded, onClose]);

  return (
    <>
      <button ref={btnRef} onClick={onToggle}
        className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${
          isObj ? 'bg-blue-50 text-blue-600 border-blue-100 hover:bg-blue-100 cursor-pointer' : 'bg-blue-50 text-blue-600 border-blue-100'
        }`}>
        {isObj ? concept.name : concept}
        {isObj && <span className="ml-1 text-blue-400">{isExpanded ? '▲' : '▼'}</span>}
      </button>
      {isExpanded && isObj && createPortal(
        <div ref={popupRef} style={popupStyle}
             className="p-3 bg-white rounded-xl shadow-lg border border-gray-100 text-left animate-scale-in">
          {concept.definition && (
            <p className="text-xs text-gray-700 mb-2">
              <span className="font-semibold text-gray-500">定义：</span>{concept.definition}
            </p>
          )}
          {concept.examples && concept.examples.length > 0 && (
            <div className="text-xs text-gray-600">
              <span className="font-semibold text-gray-500">示例：</span>
              <ul className="mt-1 space-y-0.5 list-disc list-inside">
                {concept.examples.map((ex, j) => <li key={j}>{ex}</li>)}
              </ul>
            </div>
          )}
          {concept.related_concepts && concept.related_concepts.length > 0 && (
            <p className="text-xs text-gray-600 mt-1">
              <span className="font-semibold text-gray-500">关联：</span>{concept.related_concepts.join('、')}
            </p>
          )}
        </div>,
        document.body
      )}
    </>
  );
}
