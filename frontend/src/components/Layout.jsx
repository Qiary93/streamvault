import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import RecommendedSidebar from './RecommendedSidebar';

export default function Layout() {
  const location = useLocation();
  const showRecommended = location.pathname === '/' || location.pathname === '/browse';

  return (
    <div className="min-h-screen bg-[#05050A] flex" data-testid="app-layout">
      <Sidebar />
      <div className="flex-1 flex flex-col ml-0 lg:ml-64">
        <Header />
        <div className="flex-1 flex overflow-auto">
          <main className="flex-1 overflow-auto">
            <Outlet />
          </main>
          {showRecommended && <RecommendedSidebar />}
        </div>
      </div>
    </div>
  );
}
