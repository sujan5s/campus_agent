"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Clock,
  CalendarDays,
  ShieldCheck,
  Sparkles,
  LogIn,
  AlertTriangle,
  Shield,
  User,
  Loader2,
  ArrowRight,
  LayoutGrid,
} from "lucide-react";
import { api, saveAuth, AuthUser } from "../../lib/api";
import CampusLogo from "../../components/CampusLogo";

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
    roleBadge: "Admin",
  },
  {
    id: "faculty-1",
    role: "faculty",
    name: "Dr. Anita Rao",
    email: "anita.rao@campus.edu",
    password: "faculty123",
    roleBadge: "Faculty 1",
  },
  {
    id: "faculty-2",
    role: "faculty",
    name: "Prof. Ravi Kumar",
    email: "ravi.kumar@campus.edu",
    password: "faculty123",
    roleBadge: "Faculty 2",
  },
  {
    id: "faculty-3",
    role: "faculty",
    name: "Dr. Meera Nair",
    email: "meera.nair@campus.edu",
    password: "faculty123",
    roleBadge: "Faculty 3",
  },
  {
    id: "faculty-4",
    role: "faculty",
    name: "Prof. Suresh Shetty",
    email: "suresh.shetty@campus.edu",
    password: "faculty123",
    roleBadge: "Faculty 4",
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
    <div className="min-h-screen flex flex-col lg:flex-row bg-white text-slate-800 font-sans">

      {/* LEFT PANEL - DARK Indigo/Navy GRADIENT */}
      <div className="w-full lg:w-1/2 bg-gradient-to-br from-[#0f172a] via-[#1e1b4b] to-[#00078b] p-8 sm:p-12 lg:p-16 flex flex-col justify-between text-white relative overflow-hidden shrink-0">

        {/* Glow accent */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-[#fdb813]/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none" />

        {/* Top Logo */}
        <div className="flex items-center space-x-3 relative z-10">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-[#fdb813] to-amber-300 flex items-center justify-center shadow-lg font-bold p-1.5">
            <CampusLogo variant="dark" className="h-6 w-6" />
          </div>
          <span className="text-xl font-extrabold tracking-tight text-white italic">
            SmartCampus<span className="not-italic text-[#fdb813]">Control</span>
          </span>
        </div>

        {/* Hero Section */}
        <div className="my-12 max-w-lg relative z-10">
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight mb-4 leading-tight">
            Welcome back
          </h1>
          <p className="text-slate-300 text-sm sm:text-base leading-relaxed mb-8 font-normal">
            Continue your journey of effortless scheduling and time management with the most intelligent timetable generator.
          </p>

          {/* Feature List */}
          <div className="space-y-4 text-sm font-medium text-slate-200 border-t border-white/10 pt-6">
            <div className="flex items-center space-x-3.5 pb-3 border-b border-white/10">
              <div className="p-2 rounded-lg bg-white/10 text-[#fdb813]">
                <Clock className="h-4 w-4" />
              </div>
              <span>Save hours of manual scheduling work</span>
            </div>

            <div className="flex items-center space-x-3.5 pb-3 border-b border-white/10">
              <div className="p-2 rounded-lg bg-white/10 text-[#fdb813]">
                <CalendarDays className="h-4 w-4" />
              </div>
              <span>Access your timetables anywhere, anytime</span>
            </div>

            <div className="flex items-center space-x-3.5">
              <div className="p-2 rounded-lg bg-white/10 text-[#fdb813]">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <span>Secure and reliable scheduling platform</span>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="relative z-10 pt-6">
          <p className="text-xs text-slate-400 font-medium">
            Trusted by 50,000+ institutes worldwide &bull; Smart Campus Operations
          </p>
        </div>
      </div>

      {/* RIGHT PANEL - CLEAN WHITE CANVAS */}
      <div className="w-full lg:w-1/2 bg-white p-8 sm:p-12 lg:p-16 flex flex-col justify-center items-center relative">
        <div className="w-full max-w-md space-y-6">

          {/* Header */}
          <div className="text-center sm:text-left">
            <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">
              Log in to your account
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-1">
              Or select a <span className="text-[#00078b] font-bold underline">quick demo account</span> below
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleManualSubmit} className="space-y-4 pt-2">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                EMAIL ADDRESS
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                className="w-full rounded-2xl px-4 py-3.5 text-sm bg-white border border-slate-200 text-slate-900 placeholder-slate-400 focus:border-[#00078b] focus:ring-4 focus:ring-[#00078b]/10 transition-all outline-none font-medium shadow-sm"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                PASSWORD
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="w-full rounded-2xl px-4 py-3.5 text-sm bg-white border border-slate-200 text-slate-900 placeholder-slate-400 focus:border-[#00078b] focus:ring-4 focus:ring-[#00078b]/10 transition-all outline-none font-medium shadow-sm"
              />
            </div>

            {error && (
              <div className="flex items-center space-x-2 text-rose-700 text-xs bg-rose-50 border border-rose-200 rounded-xl px-3.5 py-3 font-medium">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center space-x-2 bg-[#4f46e5] hover:bg-[#4338ca] active:scale-[0.99] disabled:opacity-50 text-white font-bold rounded-2xl px-4 py-3.5 text-base transition-all shadow-lg shadow-indigo-500/25"
            >
              {loading && activeAccountId === "manual" ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin text-white" />
                  <span>Signing in...</span>
                </>
              ) : (
                <span>Log in</span>
              )}
            </button>
          </form>

          {/* Forgot Password */}
          <div className="text-center">
            <button
              type="button"
              onClick={() => executeLogin(QUICK_ACCOUNTS[0].email, QUICK_ACCOUNTS[0].password, "admin")}
              className="text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
            >
              Forgot your password?
            </button>
          </div>

          {/* Divider */}
          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-[11px] font-bold uppercase tracking-wider">
              <span className="bg-white px-4 text-slate-400">
                OR
              </span>
            </div>
          </div>

          {/* Quick Demo Access Header */}
          <div>
            <p className="text-xs font-bold text-slate-700 mb-2.5 flex items-center space-x-1.5">
              <Sparkles className="h-3.5 w-3.5 text-[#fdb813]" />
              <span>Instant Quick Access (1-Click Demo Login)</span>
            </p>

            {/* Quick Demo Accounts */}
            <div className="space-y-2">
              {/* Admin Button */}
              <button
                type="button"
                disabled={loading}
                onClick={() => executeLogin(QUICK_ACCOUNTS[0].email, QUICK_ACCOUNTS[0].password, QUICK_ACCOUNTS[0].id)}
                className="w-full flex items-center justify-between px-4 py-3 rounded-2xl border border-slate-200 bg-slate-50 hover:bg-[#00078b]/5 hover:border-[#00078b] text-xs font-bold text-slate-800 transition-all group disabled:opacity-50 shadow-sm"
              >
                <div className="flex items-center space-x-2.5 min-w-0">
                  <Shield className="h-4 w-4 text-[#00078b] shrink-0" />
                  <span className="truncate">
                    {QUICK_ACCOUNTS[0].name}
                  </span>
                </div>
                <div className="flex items-center space-x-2 shrink-0">
                  {loading && activeAccountId === QUICK_ACCOUNTS[0].id ? (
                    <Loader2 className="h-4 w-4 animate-spin text-[#00078b]" />
                  ) : (
                    <>
                      <span className="text-[10px] font-bold px-2.5 py-1 rounded-md bg-[#fdb813] text-[#00078b]">
                        Admin
                      </span>
                      <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-[#00078b] transition-colors" />
                    </>
                  )}
                </div>
              </button>

              {/* 4 Faculty Grid */}
              <div className="grid grid-cols-2 gap-2">
                {QUICK_ACCOUNTS.slice(1).map((acc) => {
                  const isThisActive = loading && activeAccountId === acc.id;

                  return (
                    <button
                      key={acc.id}
                      type="button"
                      disabled={loading}
                      onClick={() => executeLogin(acc.email, acc.password, acc.id)}
                      className="flex items-center justify-between px-3.5 py-2.5 rounded-2xl border border-slate-200 bg-slate-50 hover:bg-[#00078b]/5 hover:border-[#00078b] text-xs font-semibold text-slate-800 transition-all group disabled:opacity-50 min-w-0 shadow-sm"
                    >
                      <div className="flex items-center space-x-1.5 truncate">
                        <User className="h-3.5 w-3.5 text-slate-400 group-hover:text-[#00078b] shrink-0" />
                        <span className="truncate">
                          {acc.name}
                        </span>
                      </div>
                      {isThisActive ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-[#00078b] shrink-0 ml-1" />
                      ) : (
                        <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-[#00078b] shrink-0 ml-1 transition-colors" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Terms Footer */}
          <p className="text-[11px] text-slate-400 text-center pt-2">
            By logging in, you agree to our <span className="underline cursor-pointer">Terms of Service</span> and <span className="underline cursor-pointer">Privacy Policy</span>
          </p>

        </div>
      </div>

    </div>
  );
}
