import client from './client';
import type { ReviewSession, ReviewQuestion, MasteryRecord, ExamResult, ReviewFeedback } from '../types';

// 开始复习会话（间隔重复）
export const startReviewSession = (bookId: string, unitIds: string[] = [], reviewType: string = 'spaced'): Promise<ReviewSession> => {
  return client.post('/v1/review/start', { book_id: bookId, unit_ids: unitIds, review_type: reviewType });
};

// 提交答案
export const submitAnswer = (
  sessionId: string,
  questionId: string,
  answer: string
): Promise<ReviewFeedback> => {
  return client.post('/v1/review/answer', {
    session_id: sessionId,
    question_id: questionId,
    answer,
  });
};

// 获取掌握度记录
export const getMasteryRecords = (bookId: string): Promise<MasteryRecord[]> => {
  return client.get(`/v1/books/${bookId}/mastery`);
};

// 获取待复习单元
export const getPendingReviews = (bookId: string): Promise<{ unit_id: string; next_review_at: string }[]> => {
  return client.get('/v1/review/due', { params: { book_id: bookId } });
};

// 开始考试
export const startExam = (bookId: string, chapterIds: string[] = []): Promise<ReviewSession> => {
  return client.post('/v1/review/exam/start', { book_id: bookId, chapter_ids: chapterIds });
};

// 提交考试答案
export const submitExam = (sessionId: string, answers: Record<string, string>): Promise<ExamResult> => {
  return client.post('/v1/review/exam/submit', { session_id: sessionId, answers });
};

// 导出
export const exportReview = (
  bookId: string,
  bookTitle: string,
  format: string
): Promise<{ format: string; content: string; filename: string; size_bytes: number }> => {
  return client.get(`/v1/review/export/${bookId}`, { params: { book_title: bookTitle, format } });
};
