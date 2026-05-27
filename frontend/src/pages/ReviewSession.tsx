import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import ProgressBar from '../components/ProgressBar';
import { startReviewSession, submitAnswer } from '../api/review';
import type { ReviewSession as ReviewSessionType, ReviewQuestion, ReviewFeedback } from '../types';

export default function ReviewSession() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<ReviewSessionType | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<ReviewQuestion | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [feedback, setFeedback] = useState<ReviewFeedback | null>(null);
  const [loading, setLoading] = useState(true);
  const [score, setScore] = useState(0);

  useEffect(() => {
    if (bookId) loadSession();
  }, [bookId]);

  const loadSession = async () => {
    try {
      const data = await startReviewSession(bookId!);
      setSession(data);
      if (data.questions && data.questions.length > 0) {
        setCurrentQuestion(data.questions[0]);
      }
    } catch (error) {
      console.error('加载复习会话失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!currentQuestion || !selectedAnswer) return;
    try {
      const result = await submitAnswer(session!.id, currentQuestion.id, selectedAnswer);
      setFeedback(result);
      if (result.is_correct) setScore((prev) => prev + 1);
    } catch (error) {
      console.error('提交答案失败:', error);
    }
  };

  const handleNext = () => {
    if (!session || !session.questions) return;
    const nextIndex = currentIndex + 1;
    if (nextIndex < session.questions.length) {
      setCurrentIndex(nextIndex);
      setCurrentQuestion(session.questions[nextIndex]);
      setSelectedAnswer('');
      setFeedback(null);
    } else {
      navigate(`/books/${bookId}`);
    }
  };

  if (loading) return <Loading />;
  if (!session || !session.questions || session.questions.length === 0 || !currentQuestion) {
    return (
      <div className="max-w-lg mx-auto text-center py-20 animate-fade-in">
        <div className="text-6xl mb-5 animate-float">🎉</div>
        <h2 className="text-xl font-bold text-gray-800 mb-2">没有待复习的内容</h2>
        <p className="text-sm text-gray-400 mb-8">完成学习后即可开始复习</p>
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
          <h1 className="text-xl font-bold text-gray-800">复习模式</h1>
          <p className="text-xs text-gray-400 mt-0.5">第 {currentIndex + 1} 题 / 共 {total} 题</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 rounded-full">
            <span className="text-xs text-emerald-600 font-semibold">✓ {score}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-full">
            <span className="text-xs text-gray-500 font-semibold">✗ {currentIndex - score}</span>
          </div>
        </div>
      </div>

      {/* 进度条 */}
      <ProgressBar value={currentIndex + 1} max={total} size="sm" color="green" className="mb-8" />

      {/* 题目 */}
      <Card className="mb-6 animate-scale-in" gradient>
        <div className="flex items-start gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-green-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
            {currentIndex + 1}
          </div>
          <p className="text-[15px] text-gray-800 leading-relaxed font-medium">{currentQuestion.question}</p>
        </div>

        {currentQuestion.options ? (
          <div className="space-y-2.5">
            {currentQuestion.options.map((option, i) => {
              const isSelected = selectedAnswer === option;
              const isCorrect = option === currentQuestion.correct_answer;
              const showResult = !!feedback;

              let style = 'border-gray-100 bg-white hover:border-blue-200 hover:bg-blue-50/30';
              if (isSelected && !showResult) style = 'border-blue-400 bg-blue-50 ring-2 ring-blue-100';
              if (showResult && isCorrect) style = 'border-emerald-400 bg-emerald-50 ring-2 ring-emerald-100';
              if (showResult && isSelected && !isCorrect) style = 'border-red-400 bg-red-50 ring-2 ring-red-100';

              return (
                <button key={i} onClick={() => !feedback && setSelectedAnswer(option)} disabled={showResult}
                  className={`w-full p-4 text-left rounded-xl border-2 transition-all text-sm ${style}`}>
                  <div className="flex items-center gap-3">
                    <span className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-[10px] font-bold shrink-0 ${
                      isSelected && !showResult ? 'border-blue-400 bg-blue-500 text-white' :
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
          <input type="text" value={selectedAnswer} onChange={(e) => setSelectedAnswer(e.target.value)}
            placeholder="输入你的答案..." disabled={!!feedback}
            className="w-full p-4 border-2 border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 disabled:opacity-50 transition-all" />
        )}
      </Card>

      {/* 反馈 */}
      {feedback && (
        <Card className={`mb-6 animate-scale-in ${feedback.is_correct ? 'border-emerald-200 bg-emerald-50/50' : 'border-red-200 bg-red-50/50'}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">{feedback.is_correct ? '🎉' : '💡'}</span>
            <p className={`font-semibold ${feedback.is_correct ? 'text-emerald-600' : 'text-red-600'}`}>
              {feedback.is_correct ? '回答正确！' : '回答错误'}
            </p>
          </div>
          <p className="text-sm text-gray-600 leading-relaxed">{feedback.explanation}</p>
          {feedback.mastery_change !== undefined && (
            <p className={`text-xs mt-2 font-medium ${feedback.mastery_change > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
              {feedback.mastery_change > 0 ? '📈' : '📉'} 掌握度 {feedback.mastery_change > 0 ? '+' : ''}{Math.round(feedback.mastery_change * 100)}%
            </p>
          )}
        </Card>
      )}

      {/* 操作按钮 */}
      <div className="flex justify-between items-center">
        <button onClick={() => navigate(`/books/${bookId}`)}
          className="px-4 py-2.5 text-gray-500 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors">
          退出复习
        </button>
        {feedback ? (
          <button onClick={handleNext}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all">
            {currentIndex + 1 < total ? '下一题 →' : '✓ 完成复习'}
          </button>
        ) : (
          <button onClick={handleSubmit} disabled={!selectedAnswer}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-emerald-500 to-green-500 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-emerald-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
            提交答案
          </button>
        )}
      </div>
    </div>
  );
}
