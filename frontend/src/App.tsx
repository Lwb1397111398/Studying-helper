import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AppProvider } from './contexts/AppContext';
import { ToastProvider } from './components/ui/Toast';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  return (
    <ErrorBoundary>
      <AppProvider>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </AppProvider>
    </ErrorBoundary>
  );
}
