// 记录最近打开的书籍，供首页"继续学习"入口使用
export const LAST_BOOK_KEY = 'sh:last-book';

export interface LastBook {
  id: string;
  title: string;
}

export function saveLastBook(book: LastBook): void {
  try {
    localStorage.setItem(LAST_BOOK_KEY, JSON.stringify(book));
  } catch {
    // localStorage 不可用时静默忽略
  }
}
