import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { startExam, submitExam } from '../api/review';
import type { ReviewSession, ReviewQuestion, ExamResult } from '../types';

export default function ExamSession() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<{ correct: boolean; explanation: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ExamResult | null>(null);

  useEffect(() => {
    if (bookId) initExam();
  }, [bookId]);

  const initExam = async () => {
    try {
      // 考试默认覆盖所有章节，传空数组让后端自行决定
      const data = await startExam(bookId!, []);
      setSession(data);
    } catch (error) {
      console.error('创建考试失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const currentQuestion: ReviewQuestion | null =
    session?.questions ? session.questions[currentIndex] ?? null : null;

  const handleSubmitAnswer = () => {
    if (!currentQuestion || !answers[currentQuestion.id]) return;
    setFeedback({
      correct: answers[currentQuestion.id] === currentQuestion.correct_answer,
      explanation: `正确答案：${currentQuestion.correct_answer}`,
    });
  };

  const handleNext = async () => {
    if (!session) return;
    const nextIndex = currentIndex + 1;
    if (nextIndex < session.questions.length) {
      setCurrentIndex(nextIndex);
      setAnswers({});
      setFeedback(null);
    } else {
      // 交卷
      await handleSubmitExam();
    }
  };

  const handleSubmitExam = async () => {
    if (!session) return;
    setSubmitting(true);
    try {
      const examResult = await submitExam(session.id, answers);
      setResult(examResult);
    } catch (error) {
      console.error('提交考试失败:', error);
      alert('提交失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <Loading text="正在生成试卷..." />;

  // 考试结果页
  if (result) {
    return (
      <div className="max-w-2xl mx-auto animate-fade-in">
        <Card className="text-center py-10" gradient>
          <div className="text-6xl mb-4">{result.passed ? '🎉' : '💪'}</div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">
            {result.passed ? '考试通过！' : '继续加油！'}
          </h1>
          <p className="text-sm text-gray-400 mb-8">
            用时 {result.time_spent_minutes} 分钟
          </p>

          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-white/60 rounded-xl p-4 border border-gray-100">
              <p className="text-3xl font-bold text-blue-600">{result.score}</p>
              <p className="text-xs text-gray-400 mt-1">总分</p>
            </div>
            <div className="bg-white/60 rounded-xl p-4 border border-gray-100">
              <p className="text-3xl font-bold text-emerald-600">{result.correct_count}</p>
              <p className="text-xs text-gray-400 mt-1">正确</p>
            </div>
            <div className="bg-white/60 rounded-xl p-4 border border-gray-100">
              <p className="text-3xl font-bold text-red-500">{result.total_count - result.correct_count}</p>
              <p className="text-xs text-gray-400 mt-1">错误</p>
            </div>
          </div>

          {result.weak_points.length > 0 && (
            <div className="text-left mb-8">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">📌 薄弱知识点</h3>
              <div className="space-y-2">
                {result.weak_points.map((point, i) => (
                  <div key={i} className="flex items-start gap-2 p-3 bg-red-50/50 rounded-lg border border-red-100">
                    <span className="text-red-400 text-xs mt-0.5">•</span>
                    <p className="text-sm text-gray-600">{point}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-3 justify-center">
            <button onClick={() => navigate(`/books/${bookId}`)}
              className="px-5 py-2.5 bg-gray-100 text-gray-600 rounded-xl text-sm font-medium hover:bg-gray-200 transition-all">
              返回书籍
            </button>
            <button onClick={() => { setResult(null); setLoading(true); initExam(); }}
              className="px-5 py-2.5 bg-gradient-to-r from-orange-500 to-amber-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-orange-500/25 transition-all">
              再考一次
            </button>
          </div>
        </Card>
      </div>
    );
  }

  if (!session || !session.questions || session.questions.length === 0 || !currentQuestion) {
    return (
      <div className="max-w-lg mx-auto text-center py-20 animate-fade-in">
        <div className="text-6xl mb-5 animate-float">📝</div>
        <h2 className="text-xl font-bold text-gray-800 mb-2">暂无可考内容</h2>
        <p className="text-sm text-gray-400 mb-8">请先完成知识拆分和学习</p>
        <button onClick={() => navigate(`/books/${bookId}`)}
          className="px-5 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all">
          返回书籍详情
        </button>
      </div>
    );
  }

  const total = session.questions.length;
  const progress = Math.round(((currentIndex + (feedback ? 1 : 0)) / total) * 100);

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      {/* 顶部 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-800">模拟考试</h1>
          <p className="text-xs text-gray-400 mt-0.5">第 {currentIndex + 1} 题 / 共 {total} 题</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-32">
            <ProgressBar value={currentIndex + 1} max={total} size="sm" color="orange" />
          </div>
          <span className="text-sm font-semibold text-orange-600">{progress}%</span>
        </div>
      </div>

      {/* 题目 */}
      <Card className="mb-6 animate-scale-in" gradient>
        <div className="flex items-start gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
            {currentIndex + 1}
          </div>
          <p className="text-[15px] text-gray-800 leading-relaxed font-medium">{currentQuestion.question}</p>
        </div>

        {currentQuestion.options ? (
          <div className="space-y-2.5">
            {currentQuestion.options.map((option, i) => {
              const isSelected = answers[currentQuestion.id] === option;
              const isCorrect = option === currentQuestion.correct_answer;
              const showResult = !!feedback;

              let style = 'border-gray-100 bg-white hover:border-orange-200 hover:bg-orange-50/30';
              if (isSelected && !showResult) style = 'border-orange-400 bg-orange-50 ring-2 ring-orange-100';
              if (showResult && isCorrect) style = 'border-emerald-400 bg-emerald-50 ring-2 ring-emerald-100';
              if (showResult && isSelected && !isCorrect) style = 'border-red-400 bg-red-50 ring-2 ring-red-100';

              return (
                <button key={i} onClick={() => !feedback && setAnswers({ ...answers, [currentQuestion.id]: option })} disabled={showResult}
                  className={`w-full p-4 text-left rounded-xl border-2 transition-all text-sm ${style}`}>
                  <div className="flex items-center gap-3">
                    <span className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-[10px] font-bold shrink-0 ${
                      isSelected && !showResult ? 'border-orange-400 bg-orange-500 text-white' :
                      showResult && isCorrect ? 'border-emerald-400 bg-emerald-500 text-white' :
                      showResult && isSelected && !isCorrect ? 'border-red-400 bg-red-500 text-white' :
                      'border-gray-200 text-gray-400'
                    }`}>
                      {showResult && isCorrect ? '✓' : showResult && isSelected && !isCorrect ? '✗' : String.fromCharCode(65 + i)}
                    </span>
                    <span className="text-gray-700">{option}</span>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <input type="text" value={answers[currentQuestion.id] || ''}
            onChange={(e) => setAnswers({ ...answers, [currentQuestion.id]: e.target.value })}
            placeholder="输入你的答案..." disabled={!!feedback}
            className="w-full p-4 border-2 border-gray-100 rounded-xl text-sm focus:outline-none focus:border-orange-300 focus:ring-2 focus:ring-orange-50 bg-gray-50/50 disabled:opacity-50 transition-all" />
        )}
      </Card>

      {/* 反馈 */}
      {feedback && (
        <Card className={`mb-6 animate-scale-in ${feedback.correct ? 'border-emerald-200 bg-emerald-50/50' : 'border-red-200 bg-red-50/50'}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">{feedback.correct ? '✅' : '❌'}</span>
            <p className={`font-semibold ${feedback.correct ? 'text-emerald-600' : 'text-red-600'}`}>
              {feedback.correct ? '回答正确' : '回答错误'}
            </p>
          </div>
          <p className="text-sm text-gray-600 leading-relaxed">{feedback.explanation}</p>
        </Card>
      )}

      {/* 操作按钮 */}
      <div className="flex justify-between items-center">
        <button onClick={() => navigate(`/books/${bookId}`)}
          className="px-4 py-2.5 text-gray-500 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors">
          退出考试
        </button>
        {feedback ? (
          <button onClick={handleNext}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-orange-500 to-amber-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-orange-500/25 transition-all">
            {currentIndex + 1 < total ? '下一题 →' : '📋 交卷'}
          </button>
        ) : (
          <button onClick={handleSubmitAnswer} disabled={!answers[currentQuestion.id]}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-orange-500 to-amber-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-orange-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
            确认答案
          </button>
        )}
      </div>
    </div>
  );
}
