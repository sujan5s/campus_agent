"use client";

import React, { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { getToken, getUser, clearAuth, AuthUser } from "../lib/api";
import {
  LayoutDashboard,
  MessageSquare,
  CalendarDays,
  Building2,
  Sparkles,
  User,
  LogOut,
  CalendarX,
  ClipboardCheck,
  ArrowLeftRight,
  Inbox,
  Database,
  SlidersHorizontal,
  Loader2,
} from "lucide-react";
import CampusLogo from "./CampusLogo";

interface AppLayoutProps {
  children: React.ReactNode;
  activeHomeTab?: "overview" | "chat" | "scheduler" | "facilities";
  onSelectHomeTab?: (tab: "overview" | "chat" | "scheduler" | "facilities") => void;
  title?: string;
  subtitle?: string;
}

export default function AppLayout({
  children,
  activeHomeTab = "overview",
  onSelectHomeTab,
  title = "Smart Campus Operations",
  subtitle = "Official Academic & Administrative Operations Portal",
}: AppLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [backendConnected, setBackendConnected] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setCurrentUser(getUser());
    setAuthChecked(true);
  }, [router]);

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/health");
        if (res.ok) setBackendConnected(true);
      } catch {
        setBackendConnected(false);
      }
    };
    checkBackend();
    const interval = setInterval(checkBackend, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleNavHome = (tab: "overview" | "chat" | "scheduler" | "facilities") => {
    if (pathname === "/") {
      if (onSelectHomeTab) onSelectHomeTab(tab);
    } else {
      router.push(`/?tab=${tab}`);
    }
  };

  const isHome = pathname === "/";
  const isTimetable = pathname === "/timetable";
  const isConstraints = pathname === "/constraints";
  const isLeaves = pathname === "/leaves";
  const isApprovals = pathname === "/approvals";
  const isExchanges = pathname === "/exchanges";
  const isInbox = pathname === "/inbox";
  const isSetup = pathname === "/setup";

  if (!authChecked) {
    return (
      <div className="min-h-screen bg-[#00078b] flex items-center justify-center font-sans text-white">
        <div className="flex flex-col items-center space-y-3">
          <Loader2 className="h-8 w-8 animate-spin text-[#fdb813]" />
          <span className="text-xs font-bold uppercase tracking-wider text-white/80">Checking Authentication...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#f6f6f6] text-[#00078b] font-sans overflow-hidden">
      {/* PERSISTENT SIDEBAR */}
      <aside className="w-64 bg-[#00078b] text-white flex flex-col justify-between shrink-0 border-r border-[#00078b]/20 shadow-xl z-20">
        <div>
          {/* Logo Header */}
          <div className="p-6 flex items-center space-x-3 border-b border-white/10">
            <div className="bg-[#fdb813] p-1.5 rounded-xl shadow-md font-bold flex items-center justify-center">
              <CampusLogo variant="dark" className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight tracking-wider text-white">
                CAMPUS OPS
              </h1>
              <span className="text-[10px] text-[#fdb813] uppercase tracking-widest font-bold">
                Operations Portal
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1.5 overflow-y-auto max-h-[calc(100vh-140px)]">
            <button
              type="button"
              onClick={() => handleNavHome("overview")}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                isHome && activeHomeTab === "overview"
                  ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                  : "text-white/80 hover:bg-white/10 hover:text-white"
              }`}
            >
              <LayoutDashboard className="h-5 w-5" />
              <span className="text-sm font-medium">Overview</span>
            </button>

            <button
              type="button"
              onClick={() => handleNavHome("chat")}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                isHome && activeHomeTab === "chat"
                  ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                  : "text-white/80 hover:bg-white/10 hover:text-white"
              }`}
            >
              <MessageSquare className="h-5 w-5" />
              <span className="text-sm font-medium">Agent Chat</span>
            </button>

            <button
              type="button"
              onClick={() => handleNavHome("scheduler")}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                isHome && activeHomeTab === "scheduler"
                  ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                  : "text-white/80 hover:bg-white/10 hover:text-white"
              }`}
            >
              <CalendarDays className="h-5 w-5" />
              <span className="text-sm font-medium">Task Scheduler</span>
            </button>

            <button
              type="button"
              onClick={() => handleNavHome("facilities")}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                isHome && activeHomeTab === "facilities"
                  ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                  : "text-white/80 hover:bg-white/10 hover:text-white"
              }`}
            >
              <Building2 className="h-5 w-5" />
              <span className="text-sm font-medium">Facilities</span>
            </button>

            <div className="pt-3 mt-3 border-t border-white/10 space-y-1">
              <Link
                href="/timetable"
                className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                  isTimetable
                    ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                }`}
              >
                <CalendarDays className="h-5 w-5" />
                <span className="text-sm font-medium">Timetable</span>
              </Link>

              <Link
                href="/constraints"
                className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                  isConstraints
                    ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                }`}
              >
                <SlidersHorizontal className="h-5 w-5" />
                <span className="text-sm font-medium">Constraints</span>
              </Link>

              <Link
                href="/leaves"
                className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                  isLeaves
                    ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                }`}
              >
                <CalendarX className="h-5 w-5" />
                <span className="text-sm font-medium">Leaves</span>
              </Link>

              <Link
                href="/approvals"
                className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                  isApprovals
                    ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                }`}
              >
                <ClipboardCheck className="h-5 w-5" />
                <span className="text-sm font-medium">Approvals</span>
              </Link>

              <Link
                href="/exchanges"
                className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                  isExchanges
                    ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                }`}
              >
                <ArrowLeftRight className="h-5 w-5" />
                <span className="text-sm font-medium">Exchanges</span>
              </Link>

              <Link
                href="/inbox"
                className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                  isInbox
                    ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                }`}
              >
                <Inbox className="h-5 w-5" />
                <span className="text-sm font-medium">Inbox</span>
              </Link>

              <Link
                href="/setup"
                className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 ${
                  isSetup
                    ? "bg-[#fdb813] text-[#00078b] font-bold shadow-md"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                }`}
              >
                <Database className="h-5 w-5" />
                <span className="text-sm font-medium">Data Setup</span>
              </Link>

              <button
                type="button"
                onClick={() => {
                  clearAuth();
                  router.push("/login");
                }}
                className="w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-200 text-rose-300 hover:bg-rose-500/20 hover:text-white text-left font-semibold"
              >
                <LogOut className="h-5 w-5" />
                <span className="text-sm font-medium">Sign Out</span>
              </button>
            </div>
          </nav>
        </div>

        {/* System Status Foot */}
        <div className="p-4 border-t border-white/10 bg-[#000450]">
          <div className="flex items-center justify-between text-xs">
            <span className="text-white/70 font-medium">System Status</span>
            <div className="flex items-center space-x-1.5">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  backendConnected ? "bg-emerald-400 animate-pulse" : "bg-[#fdb813]"
                }`}
              ></span>
              <span className="font-bold text-white">
                {backendConnected ? "Online" : "Active"}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN CONTAINER */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#f6f6f6] relative">
        {/* HEADER */}
        <header className="h-20 bg-white border-b border-[#00078b]/15 flex items-center justify-between px-8 z-10 shrink-0 shadow-sm">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-[#00078b] flex items-center space-x-2">
              <span>{title}</span>
            </h2>
            <p className="text-xs text-[#00078b]/70 font-medium mt-0.5">{subtitle}</p>
          </div>
          <div className="flex items-center space-x-4">
            {currentUser && (
              <div className="flex items-center space-x-2 bg-[#f6f6f6] px-4 py-2 rounded-xl border border-[#00078b]/15 text-xs text-[#00078b] shadow-sm font-semibold">
                <User className="h-4 w-4 text-[#00078b]" />
                <span>{currentUser.name}</span>
                <span className="text-[#00078b]/30">&bull;</span>
                <span className="uppercase text-[10px] tracking-wider font-bold text-[#00078b] bg-[#fdb813] px-2 py-0.5 rounded-md">
                  {currentUser.role}
                </span>
              </div>
            )}
          </div>
        </header>

        {/* PAGE CONTENT */}
        <div className="flex-1 overflow-y-auto p-8 z-10">{children}</div>
      </main>
    </div>
  );
}
