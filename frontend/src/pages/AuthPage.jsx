import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Broadcast, Envelope, Lock, User, GoogleLogo } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';

function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default function AuthPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, login, register, googleLogin } = useAuth();
  
  const [mode, setMode] = useState(searchParams.get('mode') === 'register' ? 'register' : 'login');
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    displayName: ''
  });

  useEffect(() => {
    if (user) {
      navigate('/');
    }
  }, [user, navigate]);

  const handleChange = (e) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (mode === 'login') {
        await login(formData.email, formData.password);
        toast.success('Welcome back!');
        navigate('/');
      } else {
        const res = await register(formData.email, formData.username, formData.password, formData.displayName);
        if (res?.verification_required) {
          toast.success('Verification email sent! Check your inbox to activate your account.', { duration: 7000 });
          setMode('login');
        } else {
          toast.success('Account created successfully!');
          navigate('/');
        }
      }
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#05050A] flex" data-testid="auth-page">
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[#0F0F16] to-[#05050A] items-center justify-center p-12">
        <div className="max-w-md">
          <div className="flex items-center gap-3 mb-8">
            <Broadcast weight="fill" className="w-12 h-12 text-[#00E5FF]" />
            <span className="font-bold text-3xl font-['Outfit'] text-white">StreamVault</span>
          </div>
          <h1 className="text-4xl lg:text-5xl font-black text-white mb-6 font-['Outfit']">
            Watch. Stream. Connect.
          </h1>
          <p className="text-[#A0A0AB] text-lg">
            Join millions of viewers and creators on the ultimate live streaming platform.
          </p>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <Broadcast weight="fill" className="w-8 h-8 text-[#00E5FF]" />
            <span className="font-bold text-xl font-['Outfit'] text-white">StreamVault</span>
          </div>

          <h2 className="text-2xl font-bold text-white mb-2 font-['Outfit']">
            {mode === 'login' ? 'Welcome back' : 'Create account'}
          </h2>
          <p className="text-[#A0A0AB] mb-8">
            {mode === 'login' 
              ? 'Enter your credentials to access your account' 
              : 'Fill in your details to get started'}
          </p>

          {/* Google OAuth */}
          <Button
            type="button"
            onClick={googleLogin}
            className="w-full bg-white text-black hover:bg-gray-100 mb-6"
            data-testid="google-login-btn"
          >
            <GoogleLogo weight="bold" className="w-5 h-5 mr-2" />
            Continue with Google
          </Button>

          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-white/10" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-[#05050A] px-2 text-[#A0A0AB]">Or continue with</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1.5">Email</label>
              <div className="relative">
                <Envelope className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#A0A0AB]" />
                <Input
                  type="email"
                  name="email"
                  placeholder="you@example.com"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  className="pl-10 bg-[#0F0F16] border-white/10 text-white placeholder-[#A0A0AB] focus:border-[#00E5FF]"
                  data-testid="email-input"
                />
              </div>
            </div>

            {mode === 'register' && (
              <>
                <div>
                  <label className="text-sm text-[#A0A0AB] block mb-1.5">Username</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#A0A0AB]" />
                    <Input
                      type="text"
                      name="username"
                      placeholder="coolstreamer"
                      value={formData.username}
                      onChange={handleChange}
                      required
                      className="pl-10 bg-[#0F0F16] border-white/10 text-white placeholder-[#A0A0AB] focus:border-[#00E5FF]"
                      data-testid="username-input"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-sm text-[#A0A0AB] block mb-1.5">Display Name (optional)</label>
                  <Input
                    type="text"
                    name="displayName"
                    placeholder="Cool Streamer"
                    value={formData.displayName}
                    onChange={handleChange}
                    className="bg-[#0F0F16] border-white/10 text-white placeholder-[#A0A0AB] focus:border-[#00E5FF]"
                    data-testid="displayname-input"
                  />
                </div>
              </>
            )}

            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#A0A0AB]" />
                <Input
                  type="password"
                  name="password"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  minLength={6}
                  className="pl-10 bg-[#0F0F16] border-white/10 text-white placeholder-[#A0A0AB] focus:border-[#00E5FF]"
                  data-testid="password-input"
                />
              </div>
              {mode === 'login' && (
                <div className="flex justify-end mt-2">
                  <Link to="/forgot-password" className="text-xs text-[#00E5FF] hover:underline" data-testid="forgot-password-link">
                    Forgot password?
                  </Link>
                </div>
              )}
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC] disabled:opacity-50"
              data-testid="submit-btn"
            >
              {loading ? 'Please wait...' : (mode === 'login' ? 'Log in' : 'Create account')}
            </Button>
          </form>

          <p className="mt-6 text-center text-[#A0A0AB]">
            {mode === 'login' ? (
              <>
                Don't have an account?{' '}
                <button 
                  onClick={() => setMode('register')}
                  className="text-[#00E5FF] hover:underline"
                  data-testid="switch-to-register"
                >
                  Sign up
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button 
                  onClick={() => setMode('login')}
                  className="text-[#00E5FF] hover:underline"
                  data-testid="switch-to-login"
                >
                  Log in
                </button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
