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
    <div className="min-h-screen flex items-center justify-center p-4 bg-slate-50 dark:bg-nodex-base relative">
      <div className="absolute top-6 right-6">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-md p-8 rounded-2xl border border-slate-200 dark:border-nodex-border bg-white dark:bg-nodex-card shadow-xl backdrop-blur-md">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="p-3 rounded-2xl bg-cyan-500/10 text-cyan-500 dark:text-nodex-cyan border border-cyan-500/20 mb-3">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            Node<span className="text-cyan-500 dark:text-nodex-cyan">X</span> Cloud Dashboard
          </h1>
          <p className="text-xs text-slate-500 dark:text-nodex-secondary mt-1">
            Strictly read-only access to laptop proximity telemetry
          </p>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-nodex-red text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono font-medium text-slate-600 dark:text-nodex-secondary mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-nodex-border bg-slate-50 dark:bg-nodex-card2 text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono font-medium text-slate-600 dark:text-nodex-secondary mb-1">
              Password
            </label>
            <div className="relative">
              <KeyRound className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-nodex-border bg-slate-50 dark:bg-nodex-card2 text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-semibold tracking-wide transition-all shadow-md flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
          >
            {loading ? 'Processing...' : isSignUp ? 'Create Supabase Account' : 'Sign In to View'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => { setIsSignUp(!isSignUp); setErrorMsg(''); setSuccessMsg(''); }}
            className="text-xs text-cyan-600 dark:text-nodex-cyan hover:underline font-mono"
          >
            {isSignUp ? 'Already have an account? Sign In' : 'Need an account? Sign Up'}
          </button>
        </div>

        <div className="mt-6 pt-4 border-t border-slate-100 dark:border-nodex-border/40 text-center">
          <p className="text-[11px] text-slate-400 dark:text-nodex-dim font-mono">
            Protected by Supabase Row-Level Security &bull; Read-Only
          </p>
        </div>
      </div>
    </div>
  );
}
