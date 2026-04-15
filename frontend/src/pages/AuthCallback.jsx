import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

export default function AuthCallback() {
  const navigate = useNavigate();
  const { processGoogleSession } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Prevent double processing in StrictMode
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      const hash = window.location.hash;
      const params = new URLSearchParams(hash.substring(1));
      const sessionId = params.get('session_id');

      if (!sessionId) {
        toast.error('Invalid callback');
        navigate('/auth');
        return;
      }

      try {
        await processGoogleSession(sessionId);
        toast.success('Welcome!');
        navigate('/');
      } catch (error) {
        console.error('Auth callback error:', error);
        toast.error('Authentication failed');
        navigate('/auth');
      }
    };

    processSession();
  }, [navigate, processGoogleSession]);

  return (
    <div className="min-h-screen bg-[#05050A] flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-[#A0A0AB]">Completing sign in...</p>
      </div>
    </div>
  );
}
