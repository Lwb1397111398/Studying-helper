import client from './client';

/** 学习资产 / 单单元闭环 API */

export interface EnsureBlocksResult {
  book_id: string;
  document_revision_id: string;
}

export interface AnalyzeUnitResult {
  asset_id: string;
  unit_id: string;
  version: number;
  status: string;
  readiness_status: string;
  quality_score?: number | null;
  analysis_job_id?: string | null;
}

export interface UnitAsset {
  id: string;
  unit_id: string;
  version: number;
  status: string;
  readiness_status: string;
  freshness_status: string;
  quality_score?: number | null;
  document_revision_id?: string | null;
  payload: Record<string, unknown>;
  schema_version: string;
}

export interface TeachingV2Session {
  id: string;
  user_id?: string;
  book_id: string;
  unit_ids?: string;
  primary_unit_id?: string | null;
  asset_id?: string | null;
  state_v2?: string | null;
  completion_status?: string | null;
  pause_reason?: string | null;
  status?: string;
  parent_session_id?: string | null;
  engine?: string;
  current_phase?: string;
}

export interface AttemptResult {
  attempt_id: string;
  idempotent?: boolean;
  score?: number;
  result?: string;
  evidences?: Array<Record<string, unknown>>;
}

export const ensureDocumentBlocks = (bookId: string): Promise<EnsureBlocksResult> =>
  client.post(`/v1/learning-assets/books/${bookId}/document-blocks/ensure`);

export const analyzeUnitAsset = (unitId: string): Promise<AnalyzeUnitResult> =>
  client.post(`/v1/learning-assets/units/${unitId}/analyze`, {}, { timeout: 180000 });

export const getActiveUnitAsset = (unitId: string): Promise<UnitAsset> =>
  client.get(`/v1/learning-assets/units/${unitId}/asset`);

export const getUnitAssetById = (assetId: string): Promise<UnitAsset> =>
  client.get(`/v1/learning-assets/assets/${assetId}`);

export const startTeachingSessionV2 = (
  bookId: string,
  unitId: string,
  assetId?: string,
): Promise<TeachingV2Session> =>
  client.post('/v1/teaching/v2/sessions/start', {
    user_id: 'anonymous',
    book_id: bookId,
    unit_id: unitId,
    asset_id: assetId,
  });

/** 兼容旧 start 端点的 engine=v2 开关 */
export const startTeachingSessionWithEngine = (
  bookId: string,
  unitIds: string[],
  engine: 'v1' | 'v2' = 'v1',
): Promise<TeachingV2Session | Record<string, unknown>> =>
  client.post('/v1/teaching/sessions/start', {
    book_id: bookId,
    unit_ids: unitIds,
    engine,
  });

export const teachingV2Event = (
  sessionId: string,
  event: string,
  guards: Record<string, unknown> = {},
): Promise<TeachingV2Session> =>
  client.post(`/v1/teaching/v2/sessions/${sessionId}/event`, { event, guards });

export const teachingV2Attempt = (
  sessionId: string,
  body: {
    assessment_item_id: string;
    response: Record<string, unknown>;
    idempotency_key: string;
    source_type?: string;
    user_id?: string;
  },
): Promise<AttemptResult> =>
  client.post(`/v1/teaching/v2/sessions/${sessionId}/attempts`, {
    user_id: body.user_id || 'anonymous',
    assessment_item_id: body.assessment_item_id,
    response: body.response,
    idempotency_key: body.idempotency_key,
    source_type: body.source_type || 'assessment',
  });

export const getTeachingV2Session = (sessionId: string): Promise<TeachingV2Session> =>
  client.get(`/v1/teaching/v2/sessions/${sessionId}`);

/**
 * 准备并开始单单元 v2 闭环：ensure blocks → analyze → start session。
 * 供书籍详情「单单元闭环」入口使用。
 */
export async function prepareAndStartUnitLoop(
  bookId: string,
  unitId: string,
): Promise<{ asset: AnalyzeUnitResult; session: TeachingV2Session }> {
  await ensureDocumentBlocks(bookId);
  const asset = await analyzeUnitAsset(unitId);
  if (!['teachable', 'degraded_teachable'].includes(asset.readiness_status) || asset.status !== 'active') {
    throw new Error(`单元资产不可教学：status=${asset.status} readiness=${asset.readiness_status}`);
  }
  const session = await startTeachingSessionV2(bookId, unitId, asset.asset_id);
  return { asset, session };
}
