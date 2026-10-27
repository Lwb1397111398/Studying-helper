import type { TeachingMessage, TeachingPhase } from '../../types/teaching';
import { PHASE_CONFIG } from '../../types/teaching';

/** 单条教学消息气泡 */
export default function MessageBubble({ msg }: { msg: TeachingMessage }) {
  const isQuestion = msg.content.startsWith('❓');
  const isAnswer = msg.content.startsWith('💬');
  const isStudentAnswer = msg.content.startsWith('📝');

  if (isQuestion) {
    return (
      <div className="flex justify-end mb-4 animate-fade-in">
        <div className="max-w-[70%] bg-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-3 shadow-sm">
          <p className="text-sm leading-relaxed">{msg.content.slice(2)}</p>
        </div>
      </div>
    );
  }

  if (isStudentAnswer) {
    return (
      <div className="flex justify-end mb-4 animate-fade-in">
        <div className="max-w-[70%] bg-green-500 text-white rounded-2xl rounded-br-sm px-4 py-3 shadow-sm">
          <p className="text-sm leading-relaxed">{msg.content.slice(2)}</p>
        </div>
      </div>
    );
  }

  if (isAnswer) {
    return (
      <div className="flex justify-start mb-4 animate-fade-in">
        <div className="max-w-[70%] bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
          <p className="text-sm text-gray-700 leading-relaxed">{msg.content.slice(2)}</p>
        </div>
      </div>
    );
  }

  // 系统教学消息
  const phaseColor = (PHASE_CONFIG[msg.phase as keyof typeof PHASE_CONFIG]?.color as string) || 'gray';
  const colorMap: Record<string, string> = {
    amber: 'from-amber-50 to-orange-50 border-amber-100',
    blue: 'from-blue-50 to-indigo-50 border-blue-100',
    purple: 'from-purple-50 to-violet-50 border-purple-100',
    green: 'from-green-50 to-emerald-50 border-green-100',
    orange: 'from-orange-50 to-yellow-50 border-orange-100',
    indigo: 'from-indigo-50 to-blue-50 border-indigo-100',
  };
  const bgClass = colorMap[phaseColor] || 'from-gray-50 to-slate-50 border-gray-100';
  const config = PHASE_CONFIG[msg.phase as keyof typeof PHASE_CONFIG];
  const label = config ? `${config.icon} ${config.label}` : msg.phase;

  return (
    <div key={msg.id} className="mb-5 animate-fade-in">
      <div className={`bg-gradient-to-r ${bgClass} border rounded-2xl p-5 shadow-sm`}>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-base">{label.split(' ')[0]}</span>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            {label.split(' ').slice(1).join(' ')}
          </span>
        </div>
        <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
          {msg.content}
        </div>
      </div>
    </div>
  );
}
