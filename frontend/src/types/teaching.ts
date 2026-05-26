// === 教学模块类型定义 ===

/** 教学阶段 */
export type TeachingPhase =
  | 'activate'
  | 'intro'
  | 'core'
  | 'check'
  | 'reflect'
  | 'connect';

/** 知识类型 */
export type KnowledgeType = 'concept' | 'principle' | 'procedure' | 'fact';

/** 认知层级 */
export type CognitiveLevel = 'remember' | 'understand' | 'apply' | 'analyze';

/** 教学策略配置 */
export interface TeachingStrategy {
  explanation_style: string;
  visual_level: string;
  interaction_frequency: string;
  pace: string;
  knowledge_type: KnowledgeType;
  cognitive_level: CognitiveLevel;
  scaffold_level: string;
  feedback_style: string;
}

/** 用户教学画像 */
export interface UserTeachingProfile {
  avg_mastery_score: number;
  total_sessions: number;
  preferred_style: string;
  weakness_tags: string[];
  avg_test_score: number;
}

/** 教学消息 */
export interface TeachingMessage {
  id: string;
  session_id: string;
  unit_id: string;
  phase: TeachingPhase;
  content: string;
  content_type: string;
  created_at: string;
}

/** 用户提问 */
export interface UserQuestion {
  id: string;
  session_id: string;
  question: string;
  answer: string;
  intent: string;
  follow_up_questions: string[];
  asked_at: string;
}

/** 笔记/标记 */
export interface Annotation {
  id: string;
  user_id: string;
  knowledge_unit_id: string;
  annotation_type: string;
  content?: string;
  created_at: string;
}

/** 测试题目 */
export interface TestQuestion {
  question: string;
  question_type: 'choice' | 'fill_blank' | 'short_answer';
  options?: string[];
  correct_answer: string;
  explanation: string;
}

/** 测试结果 */
export interface SessionTest {
  id: string;
  session_id: string;
  questions: TestQuestion[];
  user_answers: string[];
  score: number | null;
  weak_points: string[];
  completed_at: string | null;
}

/** 教学会话 */
export interface TeachingSession {
  id: string;
  user_id: string;
  plan_session_id: string;
  book_id: string;
  unit_ids: string[];
  current_unit_index: number;
  current_phase: TeachingPhase;
  started_at: string;
  ended_at: string | null;
  status: string;
  strategy: TeachingStrategy;
}

/** 会话总结 */
export interface SessionSummary {
  session_id: string;
  duration_minutes: number;
  units_covered: number;
  questions_asked: number;
  test_score: number | null;
  annotations_created: number;
}

/** 阶段显示配置 */
export const PHASE_CONFIG: Record<TeachingPhase, { label: string; icon: string; color: string }> = {
  activate: { label: '激活旧知', icon: '💡', color: 'amber' },
  intro:    { label: '引入',     icon: '📖', color: 'blue' },
  core:     { label: '核心讲解', icon: '🎯', color: 'purple' },
  check:    { label: '检验理解', icon: '✅', color: 'green' },
  reflect:  { label: '反思',     icon: '🤔', color: 'orange' },
  connect:  { label: '串联',     icon: '🔗', color: 'indigo' },
};
