"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, CalendarX, Send, CheckCircle2, XCircle, AlertTriangle,
  Bot, RefreshCw, ClipboardCheck,
} from "lucide-react";
import { api, getToken, getUser, AuthUser } from "../../lib/api";

interface LeaveRow {
  id: number;
  teacher: string;
  from_date: string;
  to_date: string;
  reason: string;
  status: string;
  created_at: string;
}
interface PlanItem {
  date: string; day: string; period: number; subject: string; section: string;
  original: string; substitute: string | null; rationale: string;
}
interface DecideResponse {
  leave: LeaveRow;
  agent: {
    status: string;
    approval_id?: number;
    plan?: { lessons_affected: number; covered: number; items: PlanItem[] };
    response?: string;
  } | null;
}

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  rejected: "bg-rose-500/15 text-rose-300 border-rose-500/30",
};

export default function LeavesPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [leaves, setLeaves] = useState<LeaveRow[]>([]);
  const [form, setForm] = useState({ from_date: "", to_date: "", reason: "" });
  const [busyId, setBusyId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [flash, setFlash] = useState<{ kind: "ok" | "err" | "agent"; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setLeaves(await api<LeaveRow[]>("/leaves"));
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Load failed" });
    }
  }, []);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    setUser(getUser());
    load();
  }, [router, load]);

  const applyLeave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("/leaves", { method: "POST", body: JSON.stringify(form) });
      setFlash({ kind: "ok", text: "Leave application submitted — awaiting HOD approval." });
      setForm({ from_date: "", to_date: "", reason: "" });
      await load();
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Submit failed" });
    } finally {
      setSubmitting(false);
    }
  };

  const decide = async (id: number, action: "approve" | "reject") => {
    setBusyId(id);
    setFlash(action === "approve"
      ? { kind: "agent", text: "Leave approved — Substitution Agent is planning cover autonomously…" }
      : null);
    try {
      const r = await api<DecideResponse>(`/leaves/${id}/decide`, {
        method: "POST", body: JSON.stringify({ action }),
      });
      if (action === "reject") {
        setFlash({ kind: "ok", text: "Leave rejected." });
      } else if (r.agent?.status === "awaiting_approval" && r.agent.plan) {
        const p = r.agent.plan;
        setFlash({
          kind: "agent",
          text: `Substitution Agent drafted a plan: ${p.covered}/${p.lessons_affected} lessons covered — review it in Approvals.`,
        });
      } else {
        setFlash({ kind: "ok", text: r.agent?.response || "Leave approved." });
      }
      await load();
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Action failed" });
    } finally {
      setBusyId(null);
    }
  };

  const isAdmin = user?.role === "admin";
  const isFaculty = user?.role === "faculty";
  const inputCls = "glass-input rounded-lg px-3 py-2 text-sm w-full";
  const labelCls = "block text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-1";

  return (
    <div className="min-h-screen p-6 relative overflow-x-hidden">
      <div className="absolute top-0 left-1/3 w-[500px] h-[300px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="max-w-4xl mx-auto relative">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-4">
            <Link href="/" className="glass-card rounded-xl p-2.5 text-slate-400 hover:text-slate-200"><ArrowLeft className="h-5 w-5" /></Link>
            <div className="flex items-center space-x-3">
              <div className="bg-indigo-500/10 p-2 rounded-xl border border-indigo-500/20 text-indigo-400">
                <CalendarX className="h-5 w-5" />
              </div>
              <div>
                <h1 className="font-bold text-xl text-slate-100">Leave Management</h1>
                <p className="text-xs text-slate-400">
                  Approving a leave triggers the Substitution Agent automatically — no prompting.
                </p>
              </div>
            </div>
          </div>
          {isAdmin && (
            <Link href="/approvals" className="flex items-center space-x-2 glass-card rounded-xl px-4 py-2.5 text-sm text-slate-300 hover:text-white">
              <ClipboardCheck className="h-4 w-4" /><span>Approvals</span>
            </Link>
          )}
        </div>

        {flash && (
          <div className={`flex items-start space-x-2 text-sm rounded-xl px-4 py-3 mb-4 border ${
            flash.kind === "ok" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
            : flash.kind === "agent" ? "text-indigo-300 bg-indigo-500/10 border-indigo-500/20"
            : "text-amber-400 bg-amber-500/10 border-amber-500/20"}`}>
            {flash.kind === "agent" ? <Bot className="h-4 w-4 shrink-0 mt-0.5" />
              : flash.kind === "ok" ? <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              : <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />}
            <span>{flash.text}</span>
          </div>
        )}

        {isFaculty && (
          <form onSubmit={applyLeave} className="glass-panel rounded-2xl p-5 mb-5">
            <h2 className="text-sm font-semibold text-slate-200 mb-4">Apply for leave</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div><label className={labelCls}>From</label>
                <input required type="date" className={inputCls} value={form.from_date}
                  onChange={(e) => setForm({ ...form, from_date: e.target.value })} /></div>
              <div><label className={labelCls}>To</label>
                <input required type="date" className={inputCls} value={form.to_date}
                  onChange={(e) => setForm({ ...form, to_date: e.target.value })} /></div>
              <div className="col-span-2"><label className={labelCls}>Reason</label>
                <input required className={inputCls} placeholder="e.g. Medical"
                  value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></div>
            </div>
            <button type="submit" disabled={submitting}
              className="mt-4 flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl px-5 py-2.5">
              <Send className="h-4 w-4" /><span>{submitting ? "Submitting…" : "Submit application"}</span>
            </button>
          </form>
        )}

        <div className="glass-panel rounded-2xl overflow-hidden">
          <h2 className="text-sm font-semibold text-slate-200 px-5 pt-4 pb-1">
            {isAdmin ? "All leave applications" : "My leave applications"}
          </h2>
          <table className="w-full mt-2">
            <thead className="border-b border-slate-800 bg-slate-900/40">
              <tr>
                {["Teacher", "From", "To", "Reason", "Status", isAdmin ? "Actions" : ""].filter(Boolean).map((h) => (
                  <th key={h} className="text-left text-[10px] text-slate-400 uppercase tracking-wider font-semibold px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {leaves.map((lv) => (
                <tr key={lv.id} className="hover:bg-slate-800/20">
                  <td className="px-4 py-3 text-sm text-slate-200">{lv.teacher}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{lv.from_date}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{lv.to_date}</td>
                  <td className="px-4 py-3 text-sm text-slate-400 max-w-[200px] truncate">{lv.reason}</td>
                  <td className="px-4 py-3">
                    <span className={`text-[10px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-lg border ${STATUS_STYLE[lv.status] || ""}`}>
                      {lv.status}
                    </span>
                  </td>
                  {isAdmin && (
                    <td className="px-4 py-3 whitespace-nowrap">
                      {lv.status === "pending" ? (
                        <div className="flex items-center space-x-2">
                          <button onClick={() => decide(lv.id, "approve")} disabled={busyId === lv.id}
                            className="flex items-center space-x-1 bg-emerald-600/80 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg px-3 py-1.5">
                            {busyId === lv.id ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                            <span>Approve</span>
                          </button>
                          <button onClick={() => decide(lv.id, "reject")} disabled={busyId === lv.id}
                            className="flex items-center space-x-1 bg-rose-600/70 hover:bg-rose-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg px-3 py-1.5">
                            <XCircle className="h-3.5 w-3.5" /><span>Reject</span>
                          </button>
                        </div>
                      ) : <span className="text-slate-600 text-xs">—</span>}
                    </td>
                  )}
                </tr>
              ))}
              {leaves.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-slate-500">No leave applications yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
