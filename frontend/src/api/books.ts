import client from './client';
import type { Book, Chapter } from '../types';

// TOC 相关类型
export interface TocItem {
  id: string;
  title: string;
  level: number;
  char_offset: number;
  children?: TocItem[];
}

export interface TocPreviewResponse {
  book_id: string;
  title: string;
  toc: TocItem[];
}

export interface ConfirmTocRequest {
  items: Array<{
    title: string;
    level: number;
    char_offset: number;
  }>;
}

export interface ConfirmTocResponse {
  book_id: string;
  chapters_count: number;
  sections_count: number;
  units_count: number;
}

export interface SplitResult {
  book_id: string;
  chapters_count: number;
  sections_count: number;
  units_count: number;
  message: string;
}

// 获取书籍列表
export const getBooks = async (): Promise<Book[]> => {
  const res: any = await client.get('/v1/books');
  if (res && Array.isArray(res.items)) {
    return res.items;
  }
  if (Array.isArray(res)) {
    return res;
  }
  return [];
};

// 获取书籍详情
export const getBook = (bookId: string): Promise<Book> => {
  return client.get(`/v1/books/${bookId}`);
};

// 上传书籍
export const uploadBook = (file: File, onProgress?: (percent: number) => void): Promise<Book> => {
  const formData = new FormData();
  formData.append('file', file);

  return client.post('/v1/documents/parse', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total));
      }
    },
  });
};

// 获取书籍章节列表（含小节）
export const getBookChapters = (bookId: string): Promise<Chapter[]> => {
  return client.get(`/v1/books/${bookId}/chapters`);
};

// 删除书籍
export const deleteBook = (bookId: string): Promise<void> => {
  return client.delete(`/v1/books/${bookId}`);
};

// 启动知识拆分（异步）
export const startSplit = (bookId: string): Promise<{ book_id: string; status: string }> => {
  return client.post(`/v1/split/${bookId}`);
};

// 获取拆分结果
export const getSplitResult = (bookId: string): Promise<SplitResult> => {
  return client.get(`/v1/split/${bookId}/result`);
};

// 获取目录预览（供用户编辑）
export const getTocPreview = (bookId: string): Promise<TocPreviewResponse> => {
  return client.get(`/v1/documents/${bookId}/toc/preview`);
};

// 确认目录并重新拆分
export const confirmToc = (bookId: string, items: ConfirmTocRequest['items']): Promise<ConfirmTocResponse> => {
  return client.post(`/v1/documents/${bookId}/toc/confirm`, { items });
};

// SSE 连接：订阅拆分进度
export function splitProgressSSE(
  bookId: string,
  onProgress: (data: { stage: string; percent: number; message: string; done: boolean; error?: string }) => void,
  onError?: (err: Error) => void,
): () => void {
  const evtSource = new EventSource(`/api/v1/split/${bookId}/progress`);

  evtSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onProgress(data);
      if (data.done) {
        evtSource.close();
      }
    } catch (e) {
      console.error('SSE parse error:', e);
    }
  };

  evtSource.onerror = () => {
    onError?.(new Error('进度连接断开'));
    evtSource.close();
  };

  // 返回取消函数
  return () => evtSource.close();
}
