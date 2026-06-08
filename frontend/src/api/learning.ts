import client from './client';
import type { KnowledgeUnit, LearningRecord, LearningStats, LearningReport, KeyPoint } from '../types';

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
  forceRelearn?: boolean,
): Promise<{
  book_id: string;
  status: string;
  total_units: number;
  message: string;
}> => {
  return client.post(`/v1/learning/${bookId}/learn`, {
    unit_ids: unitIds,
    force_relearn: forceRelearn || false,
  });
};

// 重新生成指定知识单元的 AI 分析（覆盖旧结果）
export const relearnUnit = (
  unitId: string,
): Promise<{
  unit_id: string;
  summary: string;
  key_points: KeyPoint[];
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
    focus?: 'examples' | 'explanations' | 'connections' | 'applications' | 'mistakes' | 'simplify';
    instruction?: string;
  },
): Promise<{
  unit_id: string;
  summary: string;
  explanation: string;
  key_points: KeyPoint[];
  concepts: Array<{ name: string; definition: string; examples: string[] }>;
  difficulty_level: number;
  token_cost: number;
}> => {
  return client.put(`/v1/learning/units/${unitId}/enrich`, {
    focus: options?.focus,
    instruction: options?.instruction,
  });
};

// 恢复知识单元到指定状态（撤销增量更新）
export const restoreUnit = (
  unitId: string,
  snapshot: {
    summary: string;
    explanation?: string;
    key_points: (string | KeyPoint)[];
    concepts: Array<{ name: string; definition?: string; examples?: string[]; related_concepts?: string[] }>;
    difficulty_level: number;
    importance_score: number;
    prerequisites?: string[];
  },
): Promise<{ success: boolean; unit_id: string }> => {
  return client.post(`/v1/learning/units/${unitId}/restore`, snapshot);
};

// 选择性学习（按章节）
export const startSelectedLearning = (
  bookId: string,
  chapterIds: string[],
): Promise<{
  book_id: string;
  total_units: number;
  learned_count: number;
  failed_count: number;
  skipped_count: number;
  total_token_cost: number;
  duration_seconds: number;
}> => {
  return client.post(`/v1/learning/${bookId}/learn-selected`, { chapter_ids: chapterIds }, { timeout: 1800000 });
};

// 获取学习进度
export const getLearningProgress = (
  bookId: string,
): Promise<{
  book_id: string;
  status: string;
  total_units: number;
  learned_units: number;
  progress_percent: number;
}> => {
  return client.get(`/v1/learning/${bookId}/progress`);
};

// 获取 AI 学习进度（实时）
export const getAILearningProgress = (
  bookId: string,
): Promise<{
  status: string;
  current: number;
  total: number;
  message: string;
}> => {
  return client.get(`/v1/learning/${bookId}/learn-progress`);
};

// 获取书籍概览（含难度、预计时长）
export const getBookOverview = (
  bookId: string,
): Promise<{
  book_id: string;
  title: string;
  total_chapters: number;
  chapters: Array<{
    chapter_id: string;
    title: string;
    unit_count: number;
    estimated_minutes: number;
    difficulty_level: number;
  }>;
}> => {
  return client.get(`/v1/learning/${bookId}/overview`);
};
