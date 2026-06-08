import client from './client';

export interface SyncPreviewBook {
  id: string;
  title: string;
  source_updated_at: string;
  will_overwrite: boolean;
  local_title?: string | null;
}

export interface SyncPreviewResult {
  schema_version: string;
  source: 'web' | 'android';
  exported_at: string;
  books_count: number;
  chapters_count: number;
  units_count: number;
  mastery_records_count: number;
  annotations_count: number;
  kg_nodes_count: number;
  kg_edges_count: number;
  daily_stats_count: number;
  learning_records_count: number;
  review_sessions_count: number;
  teaching_sessions_count: number;
  teaching_messages_count: number;
  user_questions_count: number;
  session_tests_count: number;
  learning_efficiency_count: number;
  books: SyncPreviewBook[];
}

export interface SyncImportResult {
  books_imported: number;
  chapters_imported: number;
  units_imported: number;
  mastery_records_imported: number;
  overwritten_books: string[];
  annotations_imported: number;
  kg_nodes_imported: number;
  kg_edges_imported: number;
  learning_records_imported: number;
  daily_stats_imported: number;
  review_sessions_imported: number;
  teaching_sessions_imported: number;
  teaching_messages_imported: number;
  user_questions_imported: number;
  session_tests_imported: number;
  learning_efficiency_imported: number;
}

export const exportAllSyncPackage = (): Promise<Record<string, unknown>> => {
  return client.get('/v1/sync/export');
};

export const exportSyncPackage = (bookId: string): Promise<Record<string, unknown>> => {
  return client.get(`/v1/sync/books/${bookId}/export`);
};

export const previewSyncPackage = (file: File): Promise<SyncPreviewResult> => {
  const formData = new FormData();
  formData.append('file', file);
  return client.post('/v1/sync/preview', formData);
};

export const importSyncPackage = (file: File): Promise<SyncImportResult> => {
  const formData = new FormData();
  formData.append('file', file);
  return client.post('/v1/sync/import', formData);
};
