import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function Layout() {
  return (
    <div className="flex h-screen bg-[#f8fafc]">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-gradient-to-br from-slate-50 via-white to-blue-50/30">
        <div className="p-8 max-w-[1200px] mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
