// 书籍相关
export interface Book {
  id: string;
  title: string;
  author?: string;
  file_type: string;
  total_chapters: number;
  total_units: number;
  learned_units: number;
  reading_motivation?: string;
  parse_status: string;
  split_status: string;
  created_at: string;
}

// 章节 — 支持多级层级（编>章>节>...）
export interface Chapter {
  id: string;
  book_id: string;
  title: string;
  level: number;       // 0=编, 1=章, 2=节, 3=小节...
  parent_id?: string;
  order_index: number;
  is_container: boolean; // 是否为容器节点（有子节点，无实际内容）
  knowledge_units: KnowledgeUnit[];
  children?: Chapter[]; // 前端构建树形结构时使用
}

// 保留 Section 作为类型别名以兼容其他引用
export type Section = Chapter;

// 结构化要点
export interface KeyPoint {
  title: string;
  explanation?: string;
  examples?: string[];
}

// 概念
export interface Concept {
  name: string;
  definition?: string;
  examples?: string[];
  related_concepts?: string[];
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
  explanation?: string;
  difficulty_level: number;
  importance_score: number;
  concepts: (string | Concept)[];
  key_points: (string | KeyPoint)[];
}

// 学习记录
export interface LearningRecord {
  id: string;
  user_id: string;
  book_id: string;
  session_id: string;
  started_at: string;
  ended_at?: string;
  duration_minutes?: number;
  units_covered?: string;
  questions_asked: number;
  test_score?: number;
  annotations_created: number;
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

// 自由回忆
export interface RecalledPoint {
  content: string;
  matched_point?: string;
  is_accurate: boolean;
}

export interface FreeRecallResult {
  question_id: string;
  unit_id: string;
  coverage: number;
  accuracy: number;
  depth: number;
  overall_score: number;
  recalled_points: RecalledPoint[];
  missed_points: string[];
  incorrect_points: string[];
  gap_report: string;
  mastery_change: number;
  next_review_at: string;
}

// 知识图谱
export interface KGNode {
  id: string;
  node_type: string;
  label: string;
  short_label?: string;
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

// 可视化数据（后端 /visualization 接口返回）
export interface VisNode {
  id: string;
  label: string;
  group: string;
  size: number;
  color: string;
  title: string;
}

export interface VisEdge {
  from_id: string;
  to_id: string;
  label: string;
  width: number;
  dashes: boolean;
}

export interface VisualizationData {
  nodes: VisNode[];
  edges: VisEdge[];
  layout: string;
}

// 学习统计
export interface LearningStats {
  total_days: number;
  completed_units: number;
  mastery_distribution: Record<string, number>;
  today_minutes: number;
  streak_days: number;
}

// 每日统计
export interface DailyStats {
  user_id: string;
  date: string;
  total_minutes: number;
  units_learned: number;
  units_reviewed: number;
  tests_taken: number;
  avg_test_score: number;
  streak_day: number;
}

// 学习进度
export interface LearningProgress {
  book_id: string;
  status: string;
  total_units: number;
  learned_units: number;
  progress_percent: number;
}

// 书籍概览章节
export interface BookOverviewChapter {
  chapter_id: string;
  title: string;
  unit_count: number;
  estimated_minutes: number;
  difficulty_level: number;
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

// ===== 学习方案 =====

// 学习风格（4 维偏好，各 0-1）
export interface LearningStyle {
  visual_score: number;     // 视觉偏好：图表/思维导图
  verbal_score: number;     // 文字偏好：阅读/写作
  active_score: number;     // 主动偏好：练习/实践
  sequential_score: number; // 顺序偏好：按步骤 vs 跳跃
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

// 用户设置（仅用户偏好，不含 LLM 配置）
export interface UserSettings {
  daily_goal_minutes: number;
  daily_goal_units: number;
  review_reminder: boolean;
  reminder_time: string;
  llm_max_concurrent: number;
}

// AI 模块配置（只读）
export interface LLMModuleConfig {
  module: string;
  label: string;
  description: string;
  strength_hint: string;
  model: string;
  has_custom_key: boolean;
  base_url: string;
}

export interface AIConfigResponse {
  default_model: string;
  default_base_url: string;
  modules: LLMModuleConfig[];
}

// AI 配置更新请求
export interface LLMModuleUpdate {
  model?: string;
  api_key?: string;
  base_url?: string;
}

export interface AIConfigUpdate {
  default_model?: string;
  default_api_key?: string;
  default_base_url?: string;
  modules?: Record<string, LLMModuleUpdate>;
}
