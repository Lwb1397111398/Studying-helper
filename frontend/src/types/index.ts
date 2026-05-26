// 书籍相关
export interface Book {
  id: string;
  title: string;
  author?: string;
  file_type: string;
  total_chapters: number;
  total_units: number;
  learned_units: number;
  parse_status: string;
  split_status: string;
  created_at: string;
}

// 章节
export interface Chapter {
  id: string;
  book_id: string;
  title: string;
  order_num: number;
  level?: number;
  parent_id?: string;
  knowledge_units: KnowledgeUnit[];
}

// 小节 — level=1 的目录节点
export interface Section {
  id: string;
  chapter_id: string;
  title: string;
  order_index: number;
  knowledge_units: KnowledgeUnit[];
}

// 知识单元
export interface KnowledgeUnit {
  id: string;
  book_id: string;
  chapter_id: string;
  section_id?: string;
  title: string;
  content: string;
  summary?: string;
  difficulty_level: number;
  importance_score?: number;
  concepts: string[];
  key_points?: string[];
}

// 学习记录
export interface LearningRecord {
  id: string;
  user_id: string;
  knowledge_unit_id: string;
  session_type: string;
  performance_score?: number;
  started_at: string;
  ended_at?: string;
}

// 掌握度
export interface MasteryRecord {
  id: string;
  knowledge_unit_id: string;
  book_id?: string;
  mastery_score: number;
  mastery_level: string;
  next_review_at: string;
  review_count: number;
  ease_factor?: number;
  interval_days?: number;
  last_reviewed_at?: string;
}

// 复习会话
export interface ReviewSession {
  id: string;
  review_type: string;
  questions: ReviewQuestion[];
  started_at: string;
  ended_at?: string;
  score?: number;
}

export interface ReviewQuestion {
  id: string;
  unit_id: string;
  question: string;
  question_type: string;
  options?: string[];
  correct_answer: string;
  user_answer?: string;
  is_correct?: boolean;
}

// 考试结果
export interface ExamResult {
  session_id: string;
  score: number;
  passed: boolean;
  correct_count: number;
  total_count: number;
  weak_points: string[];
  time_spent_minutes: number;
  recommended_review: string[];
}

// 复习反馈
export interface ReviewFeedback {
  is_correct: boolean;
  correct_answer: string;
  explanation: string;
  mastery_change: number;
  next_review_at: string;
}

// 知识图谱
export interface KGNode {
  id: string;
  node_type: string;
  label: string;
  mastery_score?: number;
  color?: string;
  size: number;
}

export interface KGEdge {
  id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
  weight: number;
}

export interface KnowledgeGraph {
  book_id: string;
  nodes: KGNode[];
  edges: KGEdge[];
}

// 学习统计
export interface LearningStats {
  total_days: number;
  completed_units: number;
  mastery_distribution: Record<string, number>;
  today_minutes: number;
  streak_days: number;
}

// 学习报告
export interface LearningReport {
  period: string;
  total_minutes: number;
  units_completed: number;
  mastery_distribution: Record<string, number>;
  weak_points: string[];
  suggestions: string[];
}

// 用户
export interface AuthUser {
  id: string;
  username: string;
  email?: string;
  daily_goal_minutes: number;
  preferred_language: string;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  token: string;
  user: AuthUser;
}

// ===== 学习方案 =====

// 学习风格
export interface LearningStyle {
  visual_score: number;
  auditory_score: number;
  reading_score: number;
  kinesthetic_score: number;
  fast_paced: boolean;
  step_by_step: boolean;
  holistic: boolean;
  example_heavy: boolean;
  theory_first: boolean;
  problem_based: boolean;
  interactive: boolean;
  self_paced: boolean;
  confidence: number;
}

// 方案中的单次会话
export interface PlanSessionItem {
  id: string;
  session_number: number;
  unit_ids: string[];
  estimated_minutes: number;
  teaching_strategy: string;
  prerequisites_check: string[];
}

// 里程碑
export interface Milestone {
  id: string;
  title: string;
  session_indices: number[];
  reward_description: string;
}

// 学习方案
export interface LearningPlan {
  id: string;
  book_id: string;
  user_id: string;
  created_at: string;
  sessions: PlanSessionItem[];
  total_estimated_minutes: number;
  milestones: Milestone[];
  style_snapshot: LearningStyle;
  daily_goal_minutes: number;
  status: 'active' | 'paused' | 'completed' | 'abandoned';
}

// 当前会话响应
export interface CurrentSessionResponse {
  session: PlanSessionItem;
  total_sessions: number;
  completed_sessions: number;
  progress_percent: number;
}

// 方案更新（完成会话后返回）
export interface PlanUpdate {
  adjusted: boolean;
  reason: string | null;
  next_session: PlanSessionItem | null;
  milestone_reached: Milestone | null;
}

// 用户设置
export interface UserSettings {
  daily_goal_minutes: number;
  daily_goal_units: number;
  review_reminder: boolean;
  reminder_time: string;
  llm_provider: string;
  llm_api_base: string;
  llm_api_key: string;
  llm_model: string;
}
