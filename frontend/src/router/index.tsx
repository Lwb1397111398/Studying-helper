import { lazy, Suspense, type ComponentType } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import Layout from '../components/Layout';
import Loading from '../components/Loading';

// Lazy load pages to reduce initial bundle size
const Home = lazy(() => import('../pages/Home'));
const BookUpload = lazy(() => import('../pages/BookUpload'));
const BookOverview = lazy(() => import('../pages/BookOverview'));
const LearningSession = lazy(() => import('../pages/LearningSession'));
const TeachingSession = lazy(() => import('../pages/TeachingSession'));
const ReviewSession = lazy(() => import('../pages/ReviewSession'));
const ExamSession = lazy(() => import('../pages/ExamSession'));
const Export = lazy(() => import('../pages/Export'));
const KnowledgeGraph = lazy(() => import('../pages/KnowledgeGraph'));
const LearningReport = lazy(() => import('../pages/LearningReport'));
const Settings = lazy(() => import('../pages/Settings'));
const LearningPlan = lazy(() => import('../pages/LearningPlan'));
const Login = lazy(() => import('../pages/Login'));
const Profile = lazy(() => import('../pages/Profile'));

const PageLoading = () => (
  <div className="flex items-center justify-center py-20">
    <Loading />
  </div>
);

const NotFound = () => (
  <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
    <div className="text-6xl mb-5">🔍</div>
    <h2 className="text-xl font-bold text-gray-800 mb-2">页面不存在</h2>
    <p className="text-sm text-gray-400">请检查 URL 是否正确</p>
  </div>
);

// Helper to wrap lazy pages with Suspense
function page(LazyComponent: ComponentType) {
  return (
    <Suspense fallback={<PageLoading />}>
      <LazyComponent />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  // 登录页不用 Layout（独立全屏）
  { path: '/login', element: page(Login) },
  {
    path: '/',
    element: <Layout />,
    errorElement: <NotFound />,
    children: [
      { index: true, element: page(Home) },
      { path: 'upload', element: page(BookUpload) },
      { path: 'profile', element: page(Profile) },
      { path: 'books/:bookId', element: page(BookOverview) },
      { path: 'books/:bookId/learn', element: page(LearningSession) },
      { path: 'books/:bookId/teach', element: page(TeachingSession) },
      { path: 'books/:bookId/review', element: page(ReviewSession) },
      { path: 'books/:bookId/exam', element: page(ExamSession) },
      { path: 'books/:bookId/export', element: page(Export) },
      { path: 'books/:bookId/plan', element: page(LearningPlan) },
      { path: 'books/:bookId/graph', element: page(KnowledgeGraph) },
      { path: 'report', element: page(LearningReport) },
      { path: 'settings', element: page(Settings) },
    ],
  },
]);
