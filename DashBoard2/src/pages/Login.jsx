// User authentication page supporting Supabase sign-in and sign-up with email and password
import React, { useState } from 'react';
import { Shield, KeyRound, Mail, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react';
import { supabase, isConfigured } from '../lib/supabase';
import { ThemeToggle } from '../components/ThemeToggle';

export function Login({ onLoginSuccess }) {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isConfigured) {
      setErrorMsg('Supabase URL and Anon Key are missing in DashBoard2/.env');
      return;
    }
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        if (data?.session) {
          onLoginSuccess(data.session);
        } else {
          setSuccessMsg('Account created! If email confirmation is enabled, check your inbox; otherwise you can now sign in.');
          setIsSignUp(false);
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        if (data?.session) {
          onLoginSuccess(data.session);
        }
      }
    } catch (err) {
      setErrorMsg(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-[#000308] text-white relative font-sans overflow-hidden">
      <div className="grid-bg" aria-hidden="true">
        <svg preserveAspectRatio="none" viewBox="0 0 1000 700">
          <line x1="0" y1="0" x2="410" y2="240" stroke="#fff" strokeOpacity="0.08" strokeWidth="1" />
          <line x1="1000" y1="0" x2="740" y2="240" stroke="#fff" strokeOpacity="0.08" strokeWidth="1" />
          <line x1="0" y1="700" x2="410" y2="430" stroke="#fff" strokeOpacity="0.08" strokeWidth="1" />
          <line x1="1000" y1="700" x2="740" y2="430" stroke="#fff" strokeOpacity="0.08" strokeWidth="1" />
          <line x1="410" y1="240" x2="740" y2="240" stroke="#fff" strokeOpacity="0.16" strokeWidth="1" />
          <line x1="410" y1="430" x2="740" y2="430" stroke="#fff" strokeOpacity="0.16" strokeWidth="1" />
          <line x1="410" y1="240" x2="410" y2="430" stroke="#fff" strokeOpacity="0.16" strokeWidth="1" />
          <line x1="740" y1="240" x2="740" y2="430" stroke="#fff" strokeOpacity="0.16" strokeWidth="1" />
          <line x1="575" y1="0" x2="575" y2="700" stroke="#fff" strokeOpacity="0.16" strokeWidth="1" />
        </svg>
      </div>
      <div className="grid-glow" aria-hidden="true" />

      <div className="absolute top-6 right-6 z-20">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-md p-8 sm:p-10 rounded-3xl border border-white/15 bg-[#000c24]/75 backdrop-blur-2xl shadow-[0_16px_48px_rgba(0,3,8,0.7)] relative z-10">
        <div className="flex flex-col items-center text-center mb-8">
          <div className="p-3.5 rounded-2xl bg-[#006eff]/15 text-[#006eff] border border-[#006eff]/35 shadow-[0_0_20px_rgba(0,110,255,0.3)] mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <span className="font-medium italic text-3xl tracking-tight text-white font-sans">
            Node<b className="text-[#006eff] not-italic font-bold">X</b>
          </span>
          <p className="text-xs text-[#c9d1de] mt-1.5 font-sans">
            Strictly read-only access to laptop proximity telemetry
          </p>
        </div>

        {errorMsg && (
          <div className="mb-5 p-3.5 rounded-2xl bg-[#f87171]/12 border border-[#f87171]/30 text-[#f87171] text-xs flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-5 p-3.5 rounded-2xl bg-[#34d399]/12 border border-[#34d399]/30 text-[#34d399] text-xs flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono font-medium text-[#c9d1de] mb-1.5">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-[#7c8ba1] absolute left-3.5 top-3" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full pl-10 pr-4 py-2.5 text-xs rounded-full border border-white/15 bg-white/[0.04] text-white placeholder:text-[#7c8ba1] focus:outline-none focus:border-[#006eff] focus:ring-1 focus:ring-[#006eff] transition-all"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono font-medium text-[#c9d1de] mb-1.5">
              Password
            </label>
            <div className="relative">
              <KeyRound className="w-4 h-4 text-[#7c8ba1] absolute left-3.5 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-10 pr-4 py-2.5 text-xs rounded-full border border-white/15 bg-white/[0.04] text-white placeholder:text-[#7c8ba1] focus:outline-none focus:border-[#006eff] focus:ring-1 focus:ring-[#006eff] transition-all"
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-6 rounded-full border border-white/30 bg-white/[0.03] hover:bg-[#006eff]/20 hover:border-[#006eff] hover:shadow-[0_0_24px_rgba(0,110,255,0.45)] text-white text-xs font-semibold tracking-wide transition-all shadow-md flex items-center justify-center gap-2.5 focus:outline-none disabled:opacity-50"
            >
              {loading ? 'Processing...' : isSignUp ? 'Create Supabase Account' : 'Sign In to View'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </form>

        <div className="mt-5 text-center">
          <button
            type="button"
            onClick={() => { setIsSignUp(!isSignUp); setErrorMsg(''); setSuccessMsg(''); }}
            className="text-xs text-[#006eff] hover:underline font-mono"
          >
            {isSignUp ? 'Already have an account? Sign In' : 'Need an account? Sign Up'}
          </button>
        </div>

        <div className="mt-6 pt-4 border-t border-white/10 text-center">
          <p className="text-[11px] text-[#7c8ba1] font-mono">
            Protected by Supabase Row-Level Security &bull; Read-Only
          </p>
        </div>
      </div>
    </div>
  );
}
