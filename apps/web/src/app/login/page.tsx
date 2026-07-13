"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, LogIn, AlertTriangle } from "lucide-react";
import { api, saveAuth, AuthUser } from "../../lib/api";

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      saveAuth(res.access_token, res.user);
      router.push(res.user.role === "admin" ? "/setup" : "/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* ambient glow to match dashboard aesthetic */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-600/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="glass-panel rounded-2xl p-8 w-full max-w-md relative">
        <div className="flex items-center space-x-3 mb-8">
          <div className="bg-indigo-500/10 p-2.5 rounded-xl border border-indigo-500/20 text-indigo-400">
            <Sparkles className="h-6 w-6" />
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

        <form onSubmit={handleLogin} className="space-y-4">
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
              className="glass-input w-full rounded-xl px-4 py-3 text-sm"
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
              className="glass-input w-full rounded-xl px-4 py-3 text-sm"
            />
          </div>

          {error && (
            <div className="flex items-center space-x-2 text-amber-400 text-sm bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-2.5">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-xl px-4 py-3 transition-colors"
          >
            <LogIn className="h-4 w-4" />
            <span>{loading ? "Signing in..." : "Sign In"}</span>
          </button>
        </form>

        <div className="mt-6 pt-5 border-t border-slate-800 text-[11px] text-slate-500 leading-relaxed">
          <p className="font-semibold text-slate-400 mb-1">Demo accounts</p>
          <p>admin@campus.edu / admin123 · anita.rao@campus.edu / faculty123 · student@campus.edu / student123</p>
        </div>
      </div>
    </div>
  );
}
