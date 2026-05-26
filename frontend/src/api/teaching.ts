import client from './client';
import type {
  TeachingSession, TeachingMessage, UserQuestion,
  SessionTest, SessionSummary, UserTeachingProfile,
} from '../types/teaching';

// 开始教学会话
export const startTeachingSession = (
  userId: string,
  bookId: string,
  unitIds: string[],
  userProfile?: UserTeachingProfile,
): Promise<TeachingSession> => {
  return client.post('/v1/teaching/sessions/start', {
    user_id: userId,
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

// 提问
export const askTeachingQuestion = (
  sessionId: string,
  question: string,
): Promise<UserQuestion> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/ask`, { question });
};

// 获取会话消息历史
export const getTeachingMessages = (
  sessionId: string,
): Promise<TeachingMessage[]> => {
  return client.get(`/v1/teaching/sessions/${sessionId}/messages`);
};

// 添加笔记/标记
export const addTeachingAnnotation = (
  userId: string,
  unitId: string,
  annotationType: string,
  content?: string,
): Promise<void> => {
  return client.post('/v1/teaching/annotations', {
    user_id: userId,
    knowledge_unit_id: unitId,
    annotation_type: annotationType,
    content,
  });
};

// 运行测试
export const runTeachingTest = (
  sessionId: string,
): Promise<SessionTest> => {
  return client.post(`/v1/teaching/sessions/${sessionId}/test`);
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
  return client.post(`/v1/teaching/sessions/${sessionId}/complete`, params);
};
