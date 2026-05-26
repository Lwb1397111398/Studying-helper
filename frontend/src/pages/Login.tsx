import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppState } from '../contexts/AppContext';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAppState();
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) {
      setError('请输入用户名');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await login(username.trim());
      navigate('/');
    } catch (err: any) {
      setError(err.message || '登录失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-500/25">
            <svg className="w-8 h-8 text-white" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3zM3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-.89 11.115 11.115 0 01.25-3.762zM9.3 16.573A9.026 9.026 0 007 14.935v-3.957l1.818.78a3 3 0 002.364 0l5.508-2.361a11.026 11.026 0 01.25 3.762 1 1 0 01-.89.89 8.968 8.968 0 00-5.35 2.524 1 1 0 01-1.4 0zM6 18a1 1 0 001-1v-2.065a8.935 8.935 0 00-2-.712V17a1 1 0 001 1z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-800">学习助手</h1>
          <p className="text-sm text-gray-400 mt-1">输入用户名即可开始学习</p>
        </div>

        {/* 登录表单 */}
        <div className="bg-white rounded-2xl shadow-xl shadow-gray-200/50 border border-gray-100 p-8">
          <form onSubmit={handleSubmit}>
            <label className="block text-sm font-medium text-gray-600 mb-2">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="输入你的用户名..."
              autoFocus
              className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all"
            />

            {error && (
              <div className="mt-3 p-3 bg-red-50 border border-red-100 rounded-xl flex items-center gap-2">
                <span className="text-red-500">⚠️</span>
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username.trim()}
              className="w-full mt-4 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {loading ? '登录中...' : '登录 / 注册'}
            </button>
          </form>

          <p className="text-xs text-gray-400 text-center mt-4">
            用户不存在时自动创建，无需密码
          </p>
        </div>
      </div>
    </div>
  );
}
