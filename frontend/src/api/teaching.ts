import client from './client';
import type {
  TeachingSession, TeachingMessage, UserQuestion,
  SessionTest, SessionSummary, UserTeachingProfile, TeachingStrategy,
  CornellNote,
} from '../types/teaching';

// 获取某本书的活跃教学会话
export const getActiveTeachingSession = (
  bookId: string,
): Promise<TeachingSession> => {
  return client.get(`/v1/teaching/sessions/active?book_id=${bookId}`);
};

// 开始教学会话
export const startTeachingSession = (
  bookId: string,
  unitIds: string[],
  userProfile?: UserTeachingProfile,
): Promise<TeachingSession> => {
  return client.post('/v1/teaching/sessions/start', {
    book_id: bookId,
    unit_ids: unitIds,
    user_profile: userProfile,
  });
};

// 获取下一条教学消息
export const getNextTeachingMessage = (
  sessionId: string,
): Promise<TeachingMessage> => {
  return client.get(`/v1/teaching/sessions/${sessionId}/next-message`);
};

// 推进到下一教学阶段
export const continueToNextPhase = (
  sessionId: string,
): Promise<TeachingSession> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/continue`);
};

// 提问
export const askTeachingQuestion = (
  sessionId: string,
  question: string,
): Promise<UserQuestion> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/ask`, { question });
};

// 学生提交回答
export const submitTeachingAnswer = (
  sessionId: string,
  answer: string,
): Promise<TeachingMessage> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/answer`, { answer });
};

// 跳转到指定知识单元
export const jumpToUnit = (
  sessionId: string,
  unitId: string,
): Promise<TeachingSession> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/jump-to-unit`, { unit_id: unitId });
};

// 清空会话消息
export const clearSessionMessages = (
  sessionId: string,
): Promise<TeachingSession> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/clear`);
};

// 获取会话消息历史
export const getTeachingMessages = (
  sessionId: string,
): Promise<TeachingMessage[]> => {
  return client.get(`/v1/teaching/sessions/${sessionId}/messages`);
};

// 添加笔记/标记
export const addTeachingAnnotation = (
  unitId: string,
  annotationType: string,
  content?: string,
  relatedConcepts?: string[],
  example?: string,
  cornellCues?: string[],
  cornellSummary?: string,
): Promise<{ id: string }> => {
  return client.post('/v1/teaching/annotations', {
    unit_id: unitId,
    annotation_type: annotationType,
    content,
    related_concepts: relatedConcepts,
    example,
    cornell_cues: cornellCues,
    cornell_summary: cornellSummary,
  });
};

// 运行测试（支持薄弱点聚焦）
export const runTeachingTest = (
  sessionId: string,
  weakPoints?: string[],
): Promise<SessionTest> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/test`, {
    weak_points: weakPoints ?? [],
  });
};

// 提交测试答案
export const submitTeachingAnswers = (
  testId: string,
  answers: string[],
): Promise<SessionTest> => {
  return client.post(`/v1/teaching/tests/${testId}/submit`, { answers });
};

// 完成教学会话
export const completeTeachingSession = (
  sessionId: string,
  params?: { questions_asked?: number; test_score?: number; annotations_created?: number },
): Promise<SessionSummary> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/complete`, params ?? {});
};

// 调整教学策略
export const adaptTeachingStrategy = (
  sessionId: string,
  data: {
    questions_asked?: number;
    correct_rate?: number;
    confusing_marks?: number;
    avg_response_time?: number;
  },
): Promise<TeachingStrategy> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/adapt-strategy`, data);
};

// 获取教学统计
export const getTeachingStats = (
  bookId?: string,
  days: number = 7,
): Promise<{
  total_sessions: number;
  total_minutes: number;
  questions_asked: number;
  avg_test_score: number;
  units_covered: number;
}> => {
  const params = new URLSearchParams();
  if (bookId) params.append('book_id', bookId);
  params.append('days', days.toString());
  return client.get(`/v1/teaching/stats?${params.toString()}`);
};

// AI 生成康奈尔笔记线索栏
export const generateCornellCues = (
  unitId: string,
  notesContent: string,
): Promise<{ cues: string[] }> => {
  return client.post('/v1/teaching/annotations/cornell/cues', {
    unit_id: unitId,
    notes_content: notesContent,
  });
};

// AI 生成康奈尔笔记总结栏
export const generateCornellSummary = (
  unitId: string,
  notesContent: string,
): Promise<{ summary: string }> => {
  return client.post('/v1/teaching/annotations/cornell/summary', {
    unit_id: unitId,
    notes_content: notesContent,
  });
};

// 获取知识单元的康奈尔笔记
export const getCornellNotes = (
  unitId: string,
): Promise<CornellNote[]> => {
  return client.get(`/v1/teaching/annotations/cornell/${unitId}`);
};
