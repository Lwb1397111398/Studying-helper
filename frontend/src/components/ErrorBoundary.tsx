// Error Boundary - catches render errors

import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string }) {
    console.error('[ErrorBoundary]', error.message, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
          <div className="w-20 h-20 rounded-2xl bg-red-50 flex items-center justify-center text-4xl mb-5">
            ⚠️
          </div>
          <h2 className="text-xl font-bold text-gray-800 mb-2">出现错误</h2>
          <p className="text-sm text-gray-400 mb-6 max-w-xs text-center">
            {this.state.error?.message || '未知错误，请重试'}
          </p>
          <button
            onClick={this.handleReset}
            className="px-5 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all"
          >
            重新加载
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
