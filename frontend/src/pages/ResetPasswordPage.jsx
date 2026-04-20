import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Lock, CheckCircle } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [state, setState] = useState('idle');
  const [error, setError] = useState('');

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0B0B14] via-[#11111E] to-[#0B0B14] p-4">
        <div className="w-full max-w-md bg-[#0F0F16] border border-white/5 rounded-2xl p-8 text-center" data-testid="reset-password-page">
          <h1 className="text-xl font-bold text-white mb-2">Invalid reset link</h1>
          <p className="text-sm text-[#A0A0AB] mb-4">No reset token provided.</p>
          <Link to="/forgot-password" className="text-[#00E5FF] hover:underline text-sm">Request a new reset link</Link>
        </div>
      </div>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) { setError('Password must be at least 8 characters'); return; }
    if (password !== confirm) { setError('Passwords do not match'); return; }
    setState('sending');
    try {
      await axios.post(`${API}/api/auth/reset-password`, { token, password });
      setState('done');
      setTimeout(() => navigate('/auth'), 2000);
    } catch (err) {
      setState('idle');
      setError(err.response?.data?.detail || 'Reset failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0B0B14] via-[#11111E] to-[#0B0B14] p-4">
      <div className="w-full max-w-md bg-[#0F0F16] border border-white/5 rounded-2xl p-8" data-testid="reset-password-page">
        <h1 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
          <Lock className="w-6 h-6 text-[#00E5FF]" /> Reset your password
        </h1>

        {state === 'done' ? (
          <div className="text-center">
            <CheckCircle weight="fill" className="w-14 h-14 text-green-400 mx-auto mb-4" />
            <p className="text-sm text-[#A0A0AB] mb-5">Password updated! Redirecting to login…</p>
            <Link to="/auth" className="text-[#00E5FF] hover:underline text-sm">Go to login →</Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1.5">New password</label>
              <Input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={8}
                placeholder="At least 8 characters"
                className="bg-[#0F0F16] border-white/10 text-white focus:border-[#00E5FF]"
                data-testid="reset-password-input"
              />
            </div>
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1.5">Confirm password</label>
              <Input
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                required
                minLength={8}
                className="bg-[#0F0F16] border-white/10 text-white focus:border-[#00E5FF]"
                data-testid="reset-password-confirm-input"
              />
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <Button
              type="submit"
              disabled={state === 'sending'}
              className="w-full bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC] disabled:opacity-50"
              data-testid="reset-submit-btn"
            >
              {state === 'sending' ? 'Updating…' : 'Update password'}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
