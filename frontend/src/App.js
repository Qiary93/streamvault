import React from 'react';
import { BrowserRouter, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Toaster } from './components/ui/sonner';

// Pages
import HomePage from './pages/HomePage';
import StreamPage from './pages/StreamPage';
import BrowsePage from './pages/BrowsePage';
import CategoryPage from './pages/CategoryPage';
import ProfilePage from './pages/ProfilePage';
import AuthPage from './pages/AuthPage';
import AuthCallback from './pages/AuthCallback';
import DashboardPage from './pages/DashboardPage';
import DonationSuccess from './pages/DonationSuccess';
import SearchPage from './pages/SearchPage';
import VODPage from './pages/VODPage';
import VODDetailPage from './pages/VODDetailPage';
import SubscriptionSuccess from './pages/SubscriptionSuccess';
import AdminPage from './pages/AdminPage';
import TagDiscoveryPage from './pages/TagDiscoveryPage';
import GameDiscoveryPage from './pages/GameDiscoveryPage';

// Layout
import Layout from './components/Layout';

import './App.css';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#05050A] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }

  return children;
}

function AppRouter() {
  const location = useLocation();

  // Check URL fragment for session_id (OAuth callback)
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/browse" element={<BrowsePage />} />
        <Route path="/category/:categoryId" element={<CategoryPage />} />
        <Route path="/stream/:streamId" element={<StreamPage />} />
        <Route path="/user/:username" element={<ProfilePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/tag/:tag" element={<TagDiscoveryPage />} />
        <Route path="/game/:gameName" element={<GameDiscoveryPage />} />
        <Route path="/vods" element={<VODPage />} />
        <Route path="/vod/:streamId" element={<VODDetailPage />} />
        <Route path="/donation/success" element={<DonationSuccess />} />
        <Route path="/donation/cancel" element={<DonationSuccess />} />
        <Route path="/subscription/success" element={<SubscriptionSuccess />} />
        <Route path="/subscription/cancel" element={<SubscriptionSuccess />} />
        
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } />
        <Route path="/admin" element={
          <ProtectedRoute>
            <AdminPage />
          </ProtectedRoute>
        } />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
        <Toaster position="top-right" />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
