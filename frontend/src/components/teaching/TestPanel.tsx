import { useState } from 'react';
import Card from '../Card';
import type { SessionTest } from '../../types/teaching';

interface TestPanelProps {
  test: SessionTest;
  onSubmit: (answers: Record<number, string>) => void;
}

/** 教学测试面板：支持选择/填空/判断/连线/排序/简答 6 种题型 */
export default function TestPanel({ test, onSubmit }: TestPanelProps) {
  const [answers, setAnswers] = useState<Record<number, string>>({});

  const updateAnswer = (index: number, value: string) => {
    setAnswers(prev => ({ ...prev, [index]: value }));
  };

  const moveItem = (currentOrder: string[], fromIdx: number, direction: -1 | 1): string[] => {
    const toIdx = fromIdx + direction;
    if (toIdx < 0 || toIdx >= currentOrder.length) return currentOrder;
    const newOrder = [...currentOrder];
    [newOrder[fromIdx], newOrder[toIdx]] = [newOrder[toIdx], newOrder[fromIdx]];
    return newOrder;
  };

  if (test.score !== null) {
    return (
      <Card hover={false} className="mb-6 text-center">
        <div className="text-5xl mb-3">
          {test.score >= 80 ? '🎉' : test.score >= 60 ? '👍' : '💪'}
        </div>
        <p className="text-3xl font-bold text-gray-800 mb-1">{test.score.toFixed(0)}分</p>
        <p className="text-sm text-gray-500 mb-4">
          {test.score >= 80 ? '优秀！你已经掌握了核心概念' : test.score >= 60 ? '不错！还有一些细节需要加强' : '继续努力！建议复习标记为不懂的内容'}
        </p>
        {test.weak_points.length > 0 && (
          <div className="text-left bg-amber-50 rounded-xl p-4 border border-amber-100">
            <p className="text-xs font-semibold text-amber-600 mb-2">📌 薄弱点</p>
            {test.weak_points.map((wp, i) => (
              <p key={i} className="text-sm text-amber-700">{wp}</p>
            ))}
          </div>
        )}
      </Card>
    );
  }

  return (
    <Card hover={false} className="mb-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">📝 理解测试</h3>
      {test.questions.map((q, i) => (
        <div key={i} className="mb-5 pb-5 border-b border-gray-100 last:border-0">
          <p className="text-sm font-medium text-gray-800 mb-3">
            <span className="text-blue-500 font-bold mr-1">{i + 1}.</span>
            {q.question}
          </p>

          {q.question_type === 'choice' && q.options ? (
            <div className="space-y-2">
              {q.options.map((opt, j) => (
                <button key={j} onClick={() => updateAnswer(i, opt)}
                  className={`w-full p-3 text-left rounded-xl border-2 transition-all text-sm ${
                    answers[i] === opt ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100' : 'border-gray-100 hover:border-blue-200 hover:bg-blue-50/30'
                  }`}>
                  <span className="font-medium text-gray-500 mr-2">{String.fromCharCode(65 + j)}.</span>{opt}
                </button>
              ))}
            </div>
          ) : q.question_type === 'fill_blank' ? (
            <input type="text" value={answers[i] || ''} onChange={e => updateAnswer(i, e.target.value)}
              placeholder="请补充完整..."
              className="w-full p-3 border-2 border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50" />
          ) : q.question_type === 'true_false' ? (
            <div>
              {q.statement && (
                <div className="mb-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
                  <p className="text-sm text-gray-700">{q.statement}</p>
                </div>
              )}
              <div className="flex gap-3">
                {(q.options || ['正确', '错误']).map((opt, j) => (
                  <button key={j} onClick={() => updateAnswer(i, opt)}
                    className={`flex-1 p-3 text-center rounded-xl border-2 transition-all text-sm font-medium ${
                      answers[i] === opt ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100' : 'border-gray-100 hover:border-blue-200 hover:bg-blue-50/30'
                    }`}>{opt}</button>
                ))}
              </div>
            </div>
          ) : q.question_type === 'matching' && q.pairs ? (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 mb-2">请将左侧概念与右侧定义对应（输入配对编号，如 1A 2B 3C）</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-semibold text-gray-500 mb-2">概念</p>
                  {q.pairs.map((pair, j) => (
                    <div key={j} className="p-2 bg-blue-50 rounded-lg text-sm text-blue-700 mb-1.5">{j + 1}. {pair.left}</div>
                  ))}
                </div>
                <div>
                  <p className="text-xs font-semibold text-gray-500 mb-2">定义</p>
                  {q.pairs.map((pair, j) => (
                    <div key={j} className="p-2 bg-purple-50 rounded-lg text-sm text-purple-700 mb-1.5">{String.fromCharCode(65 + j)}. {pair.right}</div>
                  ))}
                </div>
              </div>
              <input type="text" value={answers[i] || ''} onChange={e => updateAnswer(i, e.target.value)}
                placeholder="输入配对结果，如：1B 2A 3C 4D"
                className="w-full p-3 border-2 border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50" />
            </div>
          ) : q.question_type === 'ordering' && q.options ? (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 mb-2">请将以下步骤排列为正确顺序（点击上下箭头调整）</p>
              {(() => {
                const currentOrder: string[] = answers[i] ? JSON.parse(answers[i]) : q.options || [];
                return currentOrder.map((step, j) => (
                  <div key={j} className="flex items-center gap-2 p-2.5 bg-gray-50 rounded-xl border border-gray-100">
                    <span className="text-xs font-bold text-blue-500 w-6 text-center">{j + 1}</span>
                    <span className="flex-1 text-sm text-gray-700">{step}</span>
                    <div className="flex gap-1">
                      <button onClick={() => updateAnswer(i, JSON.stringify(moveItem(currentOrder, j, -1)))}
                        disabled={j === 0}
                        className="w-6 h-6 flex items-center justify-center rounded text-xs text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-30">▲</button>
                      <button onClick={() => updateAnswer(i, JSON.stringify(moveItem(currentOrder, j, 1)))}
                        disabled={j === currentOrder.length - 1}
                        className="w-6 h-6 flex items-center justify-center rounded text-xs text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-30">▼</button>
                    </div>
                  </div>
                ));
              })()}
            </div>
          ) : (
            <textarea value={answers[i] || ''} onChange={e => updateAnswer(i, e.target.value)}
              placeholder="输入你的答案..." rows={3}
              className="w-full p-3 border-2 border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 resize-none" />
          )}
        </div>
      ))}
      <button onClick={() => onSubmit(answers)}
        disabled={Object.keys(answers).length < test.questions.length}
        className="w-full py-3 bg-gradient-to-r from-purple-500 to-violet-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-purple-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
        提交答案
      </button>
    </Card>
  );
}
