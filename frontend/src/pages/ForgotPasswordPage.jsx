import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { EnvelopeSimple, CheckCircle } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [state, setState] = useState('idle'); // idle | sending | sent | error
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (!email) return;
    setState('sending');
    setError('');
    try {
      await axios.post(`${API}/api/auth/forgot-password`, { email });
      setState('sent');
    } catch (err) {
      setState('error');
      setError(err.response?.data?.detail || 'Something went wrong');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0B0B14] via-[#11111E] to-[#0B0B14] p-4">
      <div className="w-full max-w-md bg-[#0F0F16] border border-white/5 rounded-2xl p-8" data-testid="forgot-password-page">
        <div className="flex items-center gap-2 mb-6">
          <EnvelopeSimple weight="fill" className="w-8 h-8 text-[#00E5FF]" />
          <h1 className="text-xl font-bold text-white">Forgot password</h1>
        </div>

        {state === 'sent' ? (
          <div className="text-center">
            <CheckCircle weight="fill" className="w-14 h-14 text-green-400 mx-auto mb-4" />
            <p className="text-sm text-[#A0A0AB] mb-5">
              If an account exists for <span className="text-white">{email}</span>, a reset link has been sent. Check your inbox (and spam folder).
            </p>
            <Link to="/auth" className="text-[#00E5FF] hover:underline text-sm" data-testid="forgot-back-to-login">
              ← Back to login
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-[#A0A0AB]">
              Enter the email you signed up with. We'll send you a link to reset your password.
            </p>
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1.5">Email</label>
              <Input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="bg-[#0F0F16] border-white/10 text-white placeholder-[#A0A0AB] focus:border-[#00E5FF]"
                data-testid="forgot-email-input"
              />
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <Button
              type="submit"
              disabled={state === 'sending' || !email}
              className="w-full bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC] disabled:opacity-50"
              data-testid="forgot-submit-btn"
            >
              {state === 'sending' ? 'Sending…' : 'Send reset link'}
            </Button>
            <div className="text-center">
              <Link to="/auth" className="text-xs text-[#A0A0AB] hover:text-white">← Back to login</Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
