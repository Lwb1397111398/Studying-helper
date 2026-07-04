import { expect, test, type Page, type Route } from '@playwright/test';
import path from 'node:path';

const now = '2026-07-04T12:00:00.000Z';
const bookId = 'round3-book';

const sampleBook = {
  id: bookId,
  title: '第三轮端到端样例书籍：主动学习小册',
  author: 'Studying-helper 验收样例',
  file_type: 'txt',
  total_chapters: 3,
  total_units: 6,
  learned_units: 6,
  reading_motivation: '第三轮端到端验收',
  parse_status: 'completed',
  split_status: 'completed',
  learn_status: 'completed',
  created_at: now,
  updated_at: now,
};

const units = [
  {
    id: 'unit-1',
    book_id: bookId,
    chapter_id: 'chapter-1',
    title: '提问',
    content: '提问可以暴露理解缺口。',
    summary: '主动提问帮助定位理解缺口。',
    explanation: '提出具体问题可以让学习更主动。',
    difficulty_level: 2,
    importance_score: 0.8,
    concepts: ['提问', '主动学习'],
    key_points: ['提出对象、关系和困惑点'],
  },
  {
    id: 'unit-2',
    book_id: bookId,
    chapter_id: 'chapter-1',
    title: '复述',
    content: '复述要求学习者用自己的话重建内容。',
    summary: '复述检验是否真正理解。',
    explanation: '不能只照抄原文。',
    difficulty_level: 3,
    importance_score: 0.7,
    concepts: ['复述'],
    key_points: ['用自己的话解释'],
  },
];

const chapters = [
  {
    id: 'chapter-1',
    book_id: bookId,
    title: '第一章 主动学习的基本概念',
    level: 0,
    order_index: 0,
    is_container: false,
    knowledge_units: units,
  },
];

const profile = {
  id: 'profile-1',
  user_id: 'anonymous',
  book_id: bookId,
  identity_background: 'unknown',
  goal_depth: 'apply_understand',
  cognitive_pref: 'rigorous_system',
  restructure_tolerance: 'moderate',
  time_budget_minutes: 30,
  source: 'user_set',
  status: 'confirmed',
  extra_json: '{}',
  created_at: now,
  updated_at: now,
};

const design = {
  id: 'design-1',
  user_id: 'anonymous',
  book_id: bookId,
  profile_id: 'profile-1',
  macro_design: {
    id: 'macro-1',
    book_id: bookId,
    profile_id: 'profile-1',
    modules: [
      {
        index: 0,
        title: '主动学习入门',
        unit_ids: ['unit-1', 'unit-2'],
        concept_ids: ['主动学习'],
        strategy_tags: ['understand_first'],
        rationale: '先理解主动学习的基本动作。',
        estimated_minutes: 20,
      },
    ],
    global_strategy: '以理解和应用为主，保留必要复习。',
    total_modules: 1,
    version: 1,
    created_at: now,
  },
  current_module_index: 0,
  generated_module_count: 1,
  adjustments: [],
  status: 'active',
  version: 1,
  created_at: now,
  updated_at: now,
};

const micro = {
  id: 'micro-1',
  design_id: 'design-1',
  module_index: 0,
  module_title: '主动学习入门',
  ordered_unit_ids: ['unit-1', 'unit-2'],
  unit_annotations: [
    {
      unit_id: 'unit-1',
      cognitive_mode: 'understand',
      merge_group: null,
      defer_to_module: null,
      emphasis: '先理解提问作用',
      note: null,
    },
  ],
  module_intro: '这个模块会用提问和复述建立主动学习的基本循环。',
  module_status: 'active',
  module_summary_json: null,
  created_at: now,
  updated_at: now,
};

const teachingSession = {
  id: 'teaching-1',
  user_id: 'anonymous',
  plan_session_id: '',
  book_id: bookId,
  unit_ids: ['unit-1', 'unit-2'],
  current_unit_index: 0,
  current_phase: 'activate',
  started_at: now,
  ended_at: null,
  status: 'active',
  strategy: {
    explanation_style: 'rigorous',
    visual_level: 'medium',
    interaction_frequency: 'medium',
    pace: 'normal',
    knowledge_type: 'concept',
    cognitive_level: 'understand',
    scaffold_level: 'medium',
    feedback_style: 'encouraging',
    phases: ['activate', 'intro', 'core', 'check', 'reflect', 'connect'],
  },
};

const syncPreview = {
  schema_version: '1.0',
  source: 'android',
  exported_at: now,
  books_count: 1,
  chapters_count: 1,
  units_count: 2,
  mastery_records_count: 1,
  annotations_count: 0,
  kg_nodes_count: 0,
  kg_edges_count: 0,
  daily_stats_count: 0,
  learning_records_count: 0,
  review_sessions_count: 1,
  teaching_sessions_count: 1,
  teaching_messages_count: 1,
  user_questions_count: 0,
  session_tests_count: 0,
  learning_efficiency_count: 0,
  learner_intent_profiles_count: 1,
  teaching_designs_count: 1,
  module_micro_plans_count: 1,
  books: [
    {
      id: bookId,
      title: sampleBook.title,
      source_updated_at: now,
      will_overwrite: true,
      local_title: sampleBook.title,
    },
  ],
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installMockApi(page: Page) {
  await page.addInitScript(({ book }) => {
    class MockEventSource {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSED = 2;

      url: string;
      readyState = MockEventSource.CONNECTING;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      constructor(url: string) {
        this.url = url;
        window.setTimeout(() => {
          this.readyState = MockEventSource.OPEN;
          this.onmessage?.(
            new MessageEvent('message', {
              data: JSON.stringify({
                upload_id: 'round3-upload',
                stage: 'done',
                percent: 100,
                message: '解析完成',
                done: true,
                book,
              }),
            }),
          );
        }, 50);
      }

      close() {
        this.readyState = MockEventSource.CLOSED;
      }

      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() {
        return true;
      }
    }

    Object.assign(MockEventSource, {
      CONNECTING: 0,
      OPEN: 1,
      CLOSED: 2,
    });
    window.EventSource = MockEventSource as unknown as typeof EventSource;
  }, { book: sampleBook });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const endpoint = `${url.pathname}${url.search}`;
    const method = request.method();

    if (method === 'GET' && endpoint === '/api/v1/books') {
      return fulfillJson(route, { items: [sampleBook] });
    }
    if (method === 'GET' && endpoint === `/api/v1/books/${bookId}`) {
      return fulfillJson(route, sampleBook);
    }
    if (method === 'GET' && endpoint === `/api/v1/books/${bookId}/chapters`) {
      return fulfillJson(route, chapters);
    }
    if (method === 'GET' && endpoint === `/api/v1/books/${bookId}/mastery`) {
      return fulfillJson(route, [
        {
          id: 'mastery-1',
          knowledge_unit_id: 'unit-1',
          book_id: bookId,
          mastery_score: 0.7,
          mastery_level: 'familiar',
          next_review_at: now,
          review_count: 1,
          ease_factor: 2.5,
          interval_days: 1,
        },
      ]);
    }
    if (method === 'GET' && endpoint === '/api/v1/learning/stats') {
      return fulfillJson(route, {
        total_days: 1,
        completed_units: 2,
        today_minutes: 20,
        streak_days: 1,
      });
    }
    if (method === 'GET' && endpoint === `/api/v1/learning/${bookId}/progress`) {
      return fulfillJson(route, {
        book_id: bookId,
        status: 'completed',
        total_units: 2,
        learned_units: 2,
        progress_percent: 100,
      });
    }
    if (method === 'POST' && endpoint === '/api/v1/documents/parse/start') {
      return fulfillJson(route, { upload_id: 'round3-upload' });
    }

    if (method === 'GET' && endpoint === `/api/v1/aid/${bookId}/profile`) {
      return fulfillJson(route, profile);
    }
    if (method === 'POST' && endpoint === `/api/v1/aid/${bookId}/profile/confirm`) {
      return fulfillJson(route, profile);
    }
    if (method === 'POST' && endpoint === `/api/v1/aid/${bookId}/macro`) {
      return fulfillJson(route, design.macro_design);
    }
    if (method === 'GET' && endpoint === `/api/v1/aid/${bookId}/design`) {
      return fulfillJson(route, design);
    }
    if (method === 'GET' && endpoint === `/api/v1/aid/${bookId}/micro/0`) {
      return fulfillJson(route, micro);
    }
    if (method === 'POST' && endpoint === `/api/v1/aid/${bookId}/micro/0`) {
      return fulfillJson(route, micro);
    }
    if (method === 'POST' && endpoint === `/api/v1/aid/${bookId}/activate`) {
      return fulfillJson(route, { current_module_index: 0 });
    }
    if (method === 'GET' && endpoint === `/api/v1/aid/${bookId}/active-units`) {
      return fulfillJson(route, { book_id: bookId, unit_ids: ['unit-1', 'unit-2'] });
    }

    if (method === 'GET' && endpoint === `/api/v1/teaching/sessions/active?book_id=${bookId}`) {
      return fulfillJson(route, { detail: '没有活跃会话' }, 404);
    }
    if (method === 'POST' && endpoint === '/api/v1/teaching/sessions/start') {
      return fulfillJson(route, teachingSession);
    }
    if (method === 'GET' && endpoint === '/api/v1/teaching/sessions/teaching-1/next-message') {
      return fulfillJson(route, {
        id: 'message-1',
        session_id: 'teaching-1',
        unit_id: 'unit-1',
        phase: 'activate',
        content: '先回想一次：你最近是如何做学习笔记的？',
        content_type: 'text',
        next_phase: 'intro',
        requires_answer: false,
        created_at: now,
      });
    }

    if (method === 'GET' && endpoint === '/api/v1/sync/export') {
      return fulfillJson(route, { schema_version: '1.0', source: 'web', books: [sampleBook] });
    }
    if (method === 'POST' && endpoint === '/api/v1/sync/preview') {
      return fulfillJson(route, syncPreview);
    }
    if (method === 'POST' && endpoint === '/api/v1/sync/import') {
      return fulfillJson(route, {
        books_imported: 1,
        chapters_imported: 1,
        units_imported: 2,
        mastery_records_imported: 1,
        overwritten_books: [bookId],
        annotations_imported: 0,
        kg_nodes_imported: 0,
        kg_edges_imported: 0,
        learning_records_imported: 0,
        daily_stats_imported: 0,
        review_sessions_imported: 1,
        teaching_sessions_imported: 1,
        teaching_messages_imported: 1,
        user_questions_imported: 0,
        session_tests_imported: 0,
        learning_efficiency_imported: 0,
        learner_intent_profiles_imported: 1,
        teaching_designs_imported: 1,
        module_micro_plans_imported: 1,
      });
    }

    return fulfillJson(route, { detail: `Unhandled mock route: ${method} ${endpoint}` }, 500);
  });
}

test('round3 web smoke covers upload, design, teaching, and sync routes', async ({ page }) => {
  await installMockApi(page);

  await page.goto('/upload');
  await expect(page.getByRole('heading', { name: '上传书籍' })).toBeVisible();

  const samplePath = path.resolve('../docs/samples/round3_sample_book.txt');
  await page.locator('input[type="file"]').setInputFiles(samplePath);

  await expect(page).toHaveURL(/\/books\/round3-book$/);
  await expect(page.getByText(sampleBook.title).first()).toBeVisible();
  await expect(page.getByRole('button', { name: '教学设计' })).toBeVisible();

  await page.getByRole('button', { name: '教学设计' }).click();
  await expect(page).toHaveURL(/\/books\/round3-book\/design$/);
  await expect(page.getByRole('heading', { name: '教学设计' })).toBeVisible();
  await expect(page.getByText('主动学习入门')).toBeVisible();

  await page.getByRole('button', { name: '开始教学' }).click();
  await expect(page).toHaveURL(/\/books\/round3-book\/teach$/);
  await expect(page.getByText('学习路径')).toBeVisible();
  await expect(page.getByText('先回想一次').first()).toBeVisible();

  await page.goto('/sync');
  await expect(page.getByRole('heading', { name: '同步中心' })).toBeVisible();
  await expect(page.getByText('导出到手机')).toBeVisible();
  await expect(page.getByText('从手机导入')).toBeVisible();

  const syncPackage = {
    schema_version: '1.0',
    exported_at: now,
    source: 'android',
    user_id: 'anonymous',
    books: [sampleBook],
  };
  await page.locator('input[type="file"]').setInputFiles({
    name: 'round3-sync.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(syncPackage)),
  });
  await expect(page.getByRole('heading', { name: '同步包预览' })).toBeVisible();
  await expect(page.getByText('复习/考试：1')).toBeVisible();
  await expect(page.getByText('教学会话：1')).toBeVisible();
  await expect(page.getByText('学习画像：1')).toBeVisible();
  await expect(page.getByText('模块编排：1')).toBeVisible();
});
