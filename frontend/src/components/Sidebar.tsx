import { NavLink, useLocation } from 'react-router-dom';

const navItems = [
  { path: '/', label: '首页', icon: HomeIcon },
  { path: '/upload', label: '上传书籍', icon: UploadIcon },
  { path: '/report', label: '学习报告', icon: ReportIcon },
  { path: '/settings', label: '设置', icon: SettingsIcon },
];

// 书籍相关功能入口
const bookActions = [
  { path: '/plan', label: '学习方案', icon: '📋' },
  { path: '/learn', label: '学习模式', icon: '📚' },
  { path: '/design', label: '教学设计', icon: '🧭' },
  { path: '/teach', label: '教学模式', icon: '🎓' },
  { path: '/review', label: '复习模式', icon: '🔄' },
  { path: '/exam', label: '考试模式', icon: '📝' },
];

const bookManageActions = [
  { path: '/graph', label: '知识图谱', icon: '🕸️' },
  { path: '/export', label: '导出笔记', icon: '📦' },
  { path: '/toc', label: '编辑目录', icon: '📝' },
];

function HomeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M9.293 2.293a1 1 0 011.414 0l7 7A1 1 0 0117 11h-1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-3a1 1 0 00-1-1H9a1 1 0 00-1 1v3a1 1 0 01-1 1H5a1 1 0 01-1-1v-6H3a1 1 0 01-.707-1.707l7-7z" clipRule="evenodd" />
    </svg>
  );
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path d="M5.5 13a3.5 3.5 0 01-.369-6.98 4 4 0 117.753-1.977A4.5 4.5 0 1113.5 13H11V9.413l1.293 1.293a1 1 0 001.414-1.414l-3-3a1 1 0 00-1.414 0l-3 3a1 1 0 001.414 1.414L9 9.414V13H5.5z" />
      <path d="M9 13h2v5a1 1 0 11-2 0v-5z" />
    </svg>
  );
}

function ReportIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" />
    </svg>
  );
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
    </svg>
  );
}

export default function Sidebar() {
  const location = useLocation();
  // 从 URL 中提取 bookId
  const bookMatch = location.pathname.match(/^\/books\/([^/]+)/);
  const currentBookId = bookMatch ? bookMatch[1] : null;
  const isBookRoot = location.pathname.match(/^\/books\/[^/]+$/);

  return (
    <aside className="w-60 bg-white/80 backdrop-blur-xl border-r border-gray-100/80 flex flex-col shrink-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-100/60">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <svg className="w-5 h-5 text-white" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3zM3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-.89 11.115 11.115 0 01.25-3.762zM9.3 16.573A9.026 9.026 0 007 14.935v-3.957l1.818.78a3 3 0 002.364 0l5.508-2.361a11.026 11.026 0 01.25 3.762 1 1 0 01-.89.89 8.968 8.968 0 00-5.35 2.524 1 1 0 01-1.4 0zM6 18a1 1 0 001-1v-2.065a8.935 8.935 0 00-2-.712V17a1 1 0 001 1z" />
            </svg>
          </div>
          <div>
            <h1 className="text-[15px] font-bold text-gray-800 tracking-tight">学习助手</h1>
            <p className="text-[10px] text-gray-400 font-medium tracking-wide uppercase">Learning Helper</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        <p className="px-3 mb-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">菜单</p>
        <ul className="space-y-1 mb-4">
          {navItems.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-md shadow-blue-500/25'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <item.icon className={`w-[18px] h-[18px] ${isActive ? 'text-white' : 'text-gray-400'}`} />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>

        {/* 当前书籍功能入口 */}
        {currentBookId && (
          <div className="mt-2">
            <p className="px-3 mb-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">当前书籍</p>

            {/* 返回书籍详情 */}
            {!isBookRoot && (
              <NavLink
                to={`/books/${currentBookId}`}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-[13px] font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-50 transition-all mb-1"
              >
                <span className="text-sm">📖</span>
                <span>书籍详情</span>
              </NavLink>
            )}

            {/* 学习相关 */}
            <ul className="space-y-0.5">
              {bookActions.map((action) => (
                <li key={action.path}>
                  <NavLink
                    to={`/books/${currentBookId}${action.path}`}
                    className={({ isActive }) =>
                      `flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] transition-all ${
                        isActive
                          ? 'bg-blue-50 text-blue-600 font-medium'
                          : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                      }`
                    }
                  >
                    <span className="text-sm">{action.icon}</span>
                    <span>{action.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>

            {/* 分隔线 */}
            <div className="mx-3 my-2 border-t border-gray-100" />

            {/* 管理相关 */}
            <ul className="space-y-0.5">
              {bookManageActions.map((action) => (
                <li key={action.path}>
                  <NavLink
                    to={`/books/${currentBookId}${action.path}`}
                    className={({ isActive }) =>
                      `flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] transition-all ${
                        isActive
                          ? 'bg-blue-50 text-blue-600 font-medium'
                          : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                      }`
                    }
                  >
                    <span className="text-sm">{action.icon}</span>
                    <span>{action.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        )}
      </nav>

      {/* 用户信息 */}
      <div className="px-4 py-4 border-t border-gray-100/60">
        <NavLink to="/profile" className="flex items-center gap-3 px-2 py-1.5 rounded-xl hover:bg-gray-50 transition-colors">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white text-xs font-bold shrink-0">
            本
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-700">本地用户</p>
            <p className="text-[10px] text-gray-400">单机模式</p>
          </div>
        </NavLink>
      </div>
    </aside>
  );
}
