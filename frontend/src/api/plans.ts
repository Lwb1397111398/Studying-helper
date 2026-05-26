import client from './client';
import type { LearningPlan, PlanSessionItem, PlanUpdate, CurrentSessionResponse } from '../types';

// 生成学习方案
export const generatePlan = (bookId: string, dailyGoalMinutes: number = 30): Promise<LearningPlan> => {
  return client.post(`/v1/plans/${bookId}/generate`, { daily_goal_minutes: dailyGoalMinutes });
};

// 获取当前会话
export const getCurrentSession = (
  bookId: string,
  completedSessions: number = 0
): Promise<CurrentSessionResponse> => {
  return client.get(`/v1/plans/${bookId}/current-session`, {
    params: { completed_sessions: completedSessions },
  });
};

// 完成会话
export const completeSession = (
  bookId: string,
  sessionId: string,
  performance: {
    correct_rate: number;
    avg_response_time: number;
    questions_asked: number;
    duration_minutes: number;
    feedback_rating?: number;
  }
): Promise<PlanUpdate> => {
  return client.post(`/v1/plans/${bookId}/sessions/${sessionId}/complete`, performance);
};
