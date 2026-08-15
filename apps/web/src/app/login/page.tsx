"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, LogIn, AlertTriangle, ShieldCheck, UserCheck, Loader2, Zap } from "lucide-react";
import { api, saveAuth, AuthUser } from "../../lib/api";

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

const QUICK_ACCOUNTS = [
  {
    id: "admin",
    role: "admin",
    name: "Campus Admin",
    email: "admin@campus.edu",
    password: "admin123",
    style: "bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20 hover:border-amber-400",
    icon: ShieldCheck,
  },
  {
    id: "faculty-1",
    role: "faculty",
    name: "Dr. Anita Rao",
    email: "anita.rao@campus.edu",
    password: "faculty123",
    style: "bg-indigo-500/10 border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/20 hover:border-indigo-400",
    icon: UserCheck,
  },
  {
    id: "faculty-2",
    role: "faculty",
    name: "Prof. Ravi Kumar",
    email: "ravi.kumar@campus.edu",
    password: "faculty123",
    style: "bg-violet-500/10 border-violet-500/30 text-violet-300 hover:bg-violet-500/20 hover:border-violet-400",
    icon: UserCheck,
  },
  {
    id: "faculty-3",
    role: "faculty",
    name: "Dr. Meera Nair",
    email: "meera.nair@campus.edu",
    password: "faculty123",
    style: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20 hover:border-emerald-400",
    icon: UserCheck,
  },
  {
    id: "faculty-4",
    role: "faculty",
    name: "Prof. Suresh Shetty",
    email: "suresh.shetty@campus.edu",
    password: "faculty123",
    style: "bg-sky-500/10 border-sky-500/30 text-sky-300 hover:bg-sky-500/20 hover:border-sky-400",
    icon: UserCheck,
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null);

  const executeLogin = async (loginEmail: string, loginPass: string, accountId?: string) => {
    setError("");
    setLoading(true);
    if (accountId) setActiveAccountId(accountId);

    setEmail(loginEmail);
    setPassword(loginPass);

    try {
      const res = await api<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: loginEmail, password: loginPass }),
      });
      saveAuth(res.access_token, res.user);
      router.push(res.user.role === "admin" ? "/setup" : "/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
      setActiveAccountId(null);
    }
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeLogin(email, password, "manual");
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-slate-950">
      {/* ambient glow */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-600/15 rounded-full blur-[140px] pointer-events-none" />

      <div className="glass-panel rounded-2xl p-6 sm:p-7 w-full max-w-md relative z-10 border border-slate-800/80 shadow-2xl backdrop-blur-xl bg-slate-900/70">
        
        {/* Header */}
        <div className="flex items-center space-x-3 mb-6">
          <div className="bg-indigo-500/10 p-2.5 rounded-xl border border-indigo-500/20 text-indigo-400">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-wider bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
              CAMPUS OPS
            </h1>
            <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
              Sign in to continue
            </span>
          </div>
        </div>

        {/* Credentials Form */}
        <form onSubmit={handleManualSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 uppercase tracking-wider font-semibold mb-1.5">
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@campus.edu"
              className="glass-input w-full rounded-xl px-4 py-2.5 text-sm bg-slate-950/60 border border-slate-800 focus:border-indigo-500 text-slate-200 placeholder-slate-500 transition-all outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 uppercase tracking-wider font-semibold mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="glass-input w-full rounded-xl px-4 py-2.5 text-sm bg-slate-950/60 border border-slate-800 focus:border-indigo-500 text-slate-200 placeholder-slate-500 transition-all outline-none"
            />
          </div>

          {error && (
            <div className="flex items-center space-x-2 text-amber-400 text-xs bg-amber-500/10 border border-amber-500/20 rounded-xl px-3.5 py-2.5">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center space-x-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 text-white font-medium rounded-xl px-4 py-2.5 text-sm transition-all shadow-md shadow-indigo-600/20 active:scale-[0.98]"
          >
            {loading && activeAccountId === "manual" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Signing in...</span>
              </>
            ) : (
              <>
                <LogIn className="h-4 w-4" />
                <span>Sign In</span>
              </>
            )}
          </button>
        </form>

        {/* Quick Demo Login Section */}
        <div className="mt-6 pt-4 border-t border-slate-800/80">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 flex items-center gap-1.5">
              <Zap className="h-3 w-3 text-amber-400" />
              Quick Demo Login
            </span>
            <span className="text-[10px] text-slate-500">1-Click</span>
          </div>

          {/* Admin Button */}
          <div className="mb-2">
            <button
              type="button"
              disabled={loading}
              onClick={() => executeLogin(QUICK_ACCOUNTS[0].email, QUICK_ACCOUNTS[0].password, QUICK_ACCOUNTS[0].id)}
              className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${QUICK_ACCOUNTS[0].style} disabled:opacity-50`}
            >
              <span className="flex items-center gap-2">
                <ShieldCheck className="h-3.5 w-3.5" />
                {QUICK_ACCOUNTS[0].name}
              </span>
              {loading && activeAccountId === QUICK_ACCOUNTS[0].id ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <span className="text-[10px] font-bold uppercase tracking-wider opacity-80">Admin</span>
              )}
            </button>
          </div>

          {/* 4 Faculty Buttons Grid */}
          <div className="grid grid-cols-2 gap-1.5">
            {QUICK_ACCOUNTS.slice(1).map((acc) => {
              const isThisActive = loading && activeAccountId === acc.id;
              const Icon = acc.icon;

              return (
                <button
                  key={acc.id}
                  type="button"
                  disabled={loading}
                  onClick={() => executeLogin(acc.email, acc.password, acc.id)}
                  className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all ${acc.style} disabled:opacity-50 truncate`}
                >
                  <span className="flex items-center gap-1.5 truncate">
                    <Icon className="h-3 w-3 shrink-0" />
                    <span className="truncate">{acc.name}</span>
                  </span>
                  {isThisActive && <Loader2 className="h-3 w-3 animate-spin shrink-0 ml-1" />}
                </button>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
}
