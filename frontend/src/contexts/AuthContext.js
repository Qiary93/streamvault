import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const API = process.env.REACT_APP_BACKEND_URL;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // CRITICAL: If returning from OAuth callback, skip the /me check
    // AuthCallback will exchange the session_id and establish the session first
    if (window.location.hash?.includes('session_id=')) {
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`${API}/api/auth/me`, {
        withCredentials: true
      });
      setUser(response.data);
    } catch (error) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    const response = await axios.post(`${API}/api/auth/login`, 
      { email, password },
      { withCredentials: true }
    );
    setUser(response.data);
    return response.data;
  };

  const register = async (email, username, password, displayName) => {
    const response = await axios.post(`${API}/api/auth/register`,
      { email, username, password, display_name: displayName },
      { withCredentials: true }
    );
    // If verification_required, don't setUser (account not activated yet)
    if (response.data?.verification_required) {
      return response.data;
    }
    setUser(response.data);
    return response.data;
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/api/auth/logout`, {}, { withCredentials: true });
    } catch (error) {
      console.error('Logout error:', error);
    }
    setUser(null);
  };

  const googleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/auth/callback';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const processGoogleSession = async (sessionId) => {
    const response = await axios.post(`${API}/api/auth/google/session`,
      { session_id: sessionId },
      { withCredentials: true }
    );
    setUser(response.data);
    return response.data;
  };

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      register,
      logout,
      googleLogin,
      processGoogleSession,
      checkAuth
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
