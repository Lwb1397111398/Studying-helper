import client from './client';
import type { KnowledgeUnit, LearningRecord, LearningStats, LearningReport } from '../types';

// 获取知识单元详情
export const getKnowledgeUnit = (unitId: string): Promise<KnowledgeUnit> => {
  return client.get(`/v1/learning/units/${unitId}`);
};

// 开始学习会话
export const startLearningSession = (unitId: string): Promise<LearningRecord> => {
  return client.post('/v1/learning/sessions', { unit_id: unitId });
};

// 结束学习会话
export const endLearningSession = (sessionId: string, score?: number): Promise<LearningRecord> => {
  return client.put(`/v1/learning/sessions/${sessionId}`, { performance_score: score });
};

// 保存学习笔记
export const saveNote = (unitId: string, content: string): Promise<void> => {
  return client.post(`/v1/learning/units/${unitId}/notes`, { content });
};

// 标记知识单元
export const markUnit = (unitId: string, mark: 'important' | 'confusing'): Promise<void> => {
  return client.post(`/v1/learning/units/${unitId}/mark`, { mark });
};

// 获取学习统计
export const getLearningStats = (): Promise<LearningStats> => {
  return client.get('/v1/learning/stats');
};

// 获取学习报告
export const getLearningReport = (period: string = 'week'): Promise<LearningReport> => {
  return client.get('/v1/learning/report', { params: { period } });
};

// ── 以下为新接口 ──

// 开始 AI 学习（整本书或指定单元）
export const startLearning = (
  bookId: string,
  unitIds?: string[],
): Promise<{
  book_id: string;
  total_units: number;
  learned_count: number;
  failed_count: number;
  skipped_count: number;
  total_token_cost: number;
  duration_seconds: number;
}> => {
  return client.post(`/v1/learning/${bookId}/learn`, { unit_ids: unitIds });
};

// 重新生成指定知识单元的 AI 分析（覆盖旧结果）
export const relearnUnit = (
  unitId: string,
): Promise<{
  unit_id: string;
  summary: string;
  key_points: string[];
  concepts: Array<{ name: string; definition: string }>;
  difficulty_level: number;
  token_cost: number;
}> => {
  return client.post(`/v1/learning/units/${unitId}/relearn`);
};

// 增量更新指定知识单元（在原有基础上补充细节）
export const enrichUnit = (
  unitId: string,
  options?: {
    focus?: 'examples' | 'explanations' | 'connections';
    instruction?: string;
  },
): Promise<{
  unit_id: string;
  summary: string;
  key_points: string[];
  concepts: Array<{ name: string; definition: string; examples: string[] }>;
  difficulty_level: number;
  token_cost: number;
}> => {
  return client.put(`/v1/learning/units/${unitId}/enrich`, {
    focus: options?.focus,
    instruction: options?.instruction,
  });
};
