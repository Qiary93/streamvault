import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { CheckCircle, XCircle, Spinner, EnvelopeSimple } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const navigate = useNavigate();
  const [state, setState] = useState('verifying'); // verifying | success | error
  const [message, setMessage] = useState('');
  const [resendEmail, setResendEmail] = useState('');
  const [resendState, setResendState] = useState('');

  useEffect(() => {
    if (!token) { setState('error'); setMessage('No verification token provided.'); return; }
    axios.post(`${API}/api/auth/verify-email`, { token })
      .then(res => { setState('success'); setMessage(res.data.message || 'Email verified'); })
      .catch(err => { setState('error'); setMessage(err.response?.data?.detail || 'Verification failed'); });
  }, [token]);

  const resend = async () => {
    if (!resendEmail) return;
    setResendState('sending');
    try {
      await axios.post(`${API}/api/auth/resend-verification`, { email: resendEmail });
      setResendState('sent');
    } catch {
      setResendState('error');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0B0B14] via-[#11111E] to-[#0B0B14] p-4">
      <div className="w-full max-w-md bg-[#0F0F16] border border-white/5 rounded-2xl p-8 text-center" data-testid="verify-email-page">
        {state === 'verifying' && (
          <>
            <Spinner className="w-12 h-12 text-[#00E5FF] animate-spin mx-auto mb-4" />
            <h1 className="text-xl font-bold text-white mb-2">Verifying your email…</h1>
            <p className="text-sm text-[#A0A0AB]">Please wait.</p>
          </>
        )}
        {state === 'success' && (
          <>
            <CheckCircle weight="fill" className="w-14 h-14 text-green-400 mx-auto mb-4" />
            <h1 className="text-xl font-bold text-white mb-2">Email verified!</h1>
            <p className="text-sm text-[#A0A0AB] mb-5">{message}</p>
            <Button onClick={() => navigate('/auth')} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold w-full" data-testid="verify-go-login">
              Go to login
            </Button>
          </>
        )}
        {state === 'error' && (
          <>
            <XCircle weight="fill" className="w-14 h-14 text-red-400 mx-auto mb-4" />
            <h1 className="text-xl font-bold text-white mb-2">Verification failed</h1>
            <p className="text-sm text-[#A0A0AB] mb-5">{message}</p>
            <div className="p-4 bg-[#1A1A24] rounded-lg text-left">
              <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2"><EnvelopeSimple className="w-4 h-4" /> Resend verification email</h3>
              <Input value={resendEmail} onChange={e => setResendEmail(e.target.value)} placeholder="your@email.com" className="bg-[#0F0F16] border-white/10 text-white mb-2" data-testid="resend-email-input" />
              <Button onClick={resend} disabled={resendState === 'sending' || !resendEmail} size="sm" className="w-full bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="resend-btn">
                {resendState === 'sending' ? 'Sending…' : resendState === 'sent' ? 'Sent ✓' : 'Resend'}
              </Button>
              {resendState === 'error' && <p className="text-xs text-red-400 mt-2">Could not send — check SMTP setup or contact admin.</p>}
            </div>
            <Link to="/" className="text-sm text-[#00E5FF] hover:underline mt-4 inline-block">← Back to home</Link>
          </>
        )}
      </div>
    </div>
  );
}
