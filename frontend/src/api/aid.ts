import client from './client';

export type IdentityBackground = 'expert' | 'related' | 'unrelated' | 'unknown';
export type GoalDepth = 'exam_memorize' | 'apply_understand' | 'general_interest';
export type CognitivePref = 'vivid_analogy' | 'rigorous_system' | 'problem_driven';
export type RestructureTolerance = 'keep_book_order' | 'moderate' | 'aggressive';

export interface LearnerIntentProfile {
  id: string;
  user_id: string;
  book_id: string;
  identity_background: IdentityBackground;
  goal_depth: GoalDepth;
  cognitive_pref: CognitivePref;
  restructure_tolerance: RestructureTolerance;
  time_budget_minutes?: number | null;
  source: 'ai_inferred' | 'user_set' | 'user_adjusted';
  status: 'draft' | 'confirmed';
  extra_json: string;
  created_at: string;
  updated_at: string;
}

export interface ProfileUpdateRequest {
  identity_background?: IdentityBackground;
  goal_depth?: GoalDepth;
  cognitive_pref?: CognitivePref;
  restructure_tolerance?: RestructureTolerance;
  time_budget_minutes?: number | null;
}

export interface ModuleSkeleton {
  index: number;
  title: string;
  unit_ids: string[];
  concept_ids: string[];
  strategy_tags: string[];
  rationale: string;
  estimated_minutes?: number | null;
}

export interface MacroDesign {
  id: string;
  book_id: string;
  profile_id: string;
  modules: ModuleSkeleton[];
  global_strategy: string;
  total_modules: number;
  version: number;
  created_at: string;
}

export interface UnitRetrofitAnnotation {
  unit_id: string;
  cognitive_mode: 'memorize' | 'understand' | 'skip_if_mastered';
  merge_group?: string | null;
  defer_to_module?: number | null;
  emphasis?: string | null;
  note?: string | null;
}

export interface MicroPlan {
  id: string;
  design_id: string;
  module_index: number;
  module_title: string;
  ordered_unit_ids: string[];
  unit_annotations: UnitRetrofitAnnotation[];
  module_intro?: string | null;
  module_status: 'pending' | 'active' | 'done' | 'skipped';
  module_summary_json?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TeachingDesign {
  id: string;
  user_id: string;
  book_id: string;
  profile_id?: string | null;
  macro_design?: MacroDesign | null;
  current_module_index: number;
  generated_module_count: number;
  adjustments: unknown[];
  status: 'draft' | 'active' | 'completed' | 'superseded';
  version: number;
  created_at: string;
  updated_at: string;
}

export const getAidProfile = (bookId: string): Promise<LearnerIntentProfile> => {
  return client.get(`/v1/aid/${bookId}/profile`);
};

export const updateAidProfile = (
  bookId: string,
  data: ProfileUpdateRequest,
): Promise<LearnerIntentProfile> => {
  return client.put(`/v1/aid/${bookId}/profile`, data);
};

export const confirmAidProfile = (bookId: string): Promise<LearnerIntentProfile> => {
  return client.post(`/v1/aid/${bookId}/profile/confirm`);
};

export const generateAidMacro = (bookId: string): Promise<MacroDesign> => {
  return client.post(`/v1/aid/${bookId}/macro`, undefined, { timeout: 120000 });
};

export const getAidDesign = (bookId: string): Promise<TeachingDesign | null> => {
  return client.get(`/v1/aid/${bookId}/design`);
};

export const generateAidMicro = (bookId: string, moduleIndex: number): Promise<MicroPlan> => {
  return client.post(`/v1/aid/${bookId}/micro/${moduleIndex}`, undefined, { timeout: 120000 });
};

export const getAidMicro = (bookId: string, moduleIndex: number): Promise<MicroPlan | null> => {
  return client.get(`/v1/aid/${bookId}/micro/${moduleIndex}`);
};

export const activateAidDesign = (
  bookId: string,
): Promise<{ current_module_index: number }> => {
  return client.post(`/v1/aid/${bookId}/activate`);
};

export const getAidActiveUnits = (
  bookId: string,
): Promise<{ book_id: string; unit_ids: string[] }> => {
  return client.get(`/v1/aid/${bookId}/active-units`);
};
