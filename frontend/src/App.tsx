import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AppProvider } from './contexts/AppContext';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  return (
    <ErrorBoundary>
      <AppProvider>
        <RouterProvider router={router} />
      </AppProvider>
    </ErrorBoundary>
  );
}
