import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import Header from "./components/Header";
import Footer from "./components/Footer";

import HomePage from "./pages/HomePage";
import PricingPage from "./pages/PricingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import CheckoutSuccessPage from "./pages/CheckoutSuccessPage";
import AffiliatePage from "./pages/AffiliatePage";
import AdminDashboardPage from "./pages/AdminDashboardPage";

function Protected({ children, requireAdmin = false }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-12 text-center text-muted">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (requireAdmin && !user.is_admin) return <Navigate to="/dashboard" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <div className="min-h-full flex flex-col">
        <Header />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />
            <Route path="/affiliate" element={<Protected><AffiliatePage /></Protected>} />
            <Route path="/admin" element={<Protected requireAdmin><AdminDashboardPage /></Protected>} />
            <Route path="/checkout/success" element={<Protected><CheckoutSuccessPage /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </AuthProvider>
  );
}
