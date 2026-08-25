"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, CalendarX, Send, CheckCircle2, XCircle, AlertTriangle,
  Bot, RefreshCw, ClipboardCheck,
} from "lucide-react";
import { api, getToken, getUser, AuthUser } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

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
  pending: "bg-[#fdb813] text-[#00078b] font-bold",
  approved: "bg-emerald-100 text-emerald-800 font-bold border border-emerald-300",
  rejected: "bg-rose-100 text-rose-800 font-bold border border-rose-300",
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
  const inputCls = "bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] placeholder-[#00078b]/40 rounded-xl px-3.5 py-2 text-sm w-full outline-none font-medium focus:border-[#00078b]";
  const labelCls = "block text-[10px] text-[#00078b] uppercase tracking-wider font-bold mb-1";

  return (
    <AppLayout title="Leave Management" subtitle="Submit applications and approve faculty leaves.">
      <div className="max-w-4xl mx-auto relative">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="bg-[#00078b] p-2 rounded-xl text-[#fdb813] shadow-md">
              <CalendarX className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-[#00078b]">Leave Portal</h1>
              <p className="text-xs text-[#00078b]/70 font-medium">
                Approving a leave triggers the Substitution Agent automatically.
              </p>
            </div>
          </div>
          {isAdmin && (
            <Link href="/approvals" className="flex items-center space-x-2 bg-white border border-[#00078b]/20 shadow-sm rounded-xl px-4 py-2.5 text-sm font-bold text-[#00078b] hover:bg-[#f6f6f6] transition-colors">
              <ClipboardCheck className="h-4 w-4 text-[#00078b]" /><span>Approvals</span>
            </Link>
          )}
        </div>

        {flash && (
          <div className={`flex items-start space-x-2 text-sm rounded-xl px-4 py-3 mb-4 border font-medium ${
            flash.kind === "ok" ? "text-emerald-800 bg-emerald-50 border-emerald-200"
            : flash.kind === "agent" ? "text-[#00078b] bg-[#fdb813]/20 border-[#fdb813]/50 font-semibold"
            : "text-amber-800 bg-amber-50 border-amber-200"}`}>
            {flash.kind === "agent" ? <Bot className="h-4 w-4 shrink-0 mt-0.5 text-[#00078b]" />
              : flash.kind === "ok" ? <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-600" />
              : <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" />}
            <span>{flash.text}</span>
          </div>
        )}

        {isFaculty && (
          <form onSubmit={applyLeave} className="bg-white border border-[#00078b]/15 rounded-2xl p-5 mb-5 shadow-sm">
            <h2 className="text-sm font-bold text-[#00078b] mb-4">Apply for leave</h2>
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
              className="mt-4 flex items-center space-x-2 bg-[#00078b] hover:bg-[#000566] disabled:opacity-50 text-white text-sm font-bold rounded-xl px-5 py-2.5 shadow-md">
              <Send className="h-4 w-4 text-[#fdb813]" /><span>{submitting ? "Submitting…" : "Submit application"}</span>
            </button>
          </form>
        )}

        <div className="bg-white border border-[#00078b]/15 rounded-2xl overflow-hidden shadow-sm">
          <h2 className="text-sm font-bold text-[#00078b] px-5 pt-4 pb-1">
            {isAdmin ? "All leave applications" : "My leave applications"}
          </h2>
          <table className="w-full mt-2">
            <thead className="border-b border-[#00078b]/15 bg-[#f6f6f6]">
              <tr>
                {["Teacher", "From", "To", "Reason", "Status", isAdmin ? "Actions" : ""].filter(Boolean).map((h) => (
                  <th key={h} className="text-left text-[10px] text-[#00078b] uppercase tracking-wider font-bold px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#00078b]/10">
              {leaves.map((lv) => (
                <tr key={lv.id} className="hover:bg-[#f6f6f6]/60 transition">
                  <td className="px-4 py-3 text-sm text-[#00078b] font-bold">{lv.teacher}</td>
                  <td className="px-4 py-3 text-sm text-[#00078b] font-semibold">{lv.from_date}</td>
                  <td className="px-4 py-3 text-sm text-[#00078b] font-semibold">{lv.to_date}</td>
                  <td className="px-4 py-3 text-sm text-[#00078b]/70 max-w-[200px] truncate font-medium">{lv.reason}</td>
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
                            className="flex items-center space-x-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg px-3 py-1.5 shadow-sm">
                            {busyId === lv.id ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                            <span>Approve</span>
                          </button>
                          <button onClick={() => decide(lv.id, "reject")} disabled={busyId === lv.id}
                            className="flex items-center space-x-1 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg px-3 py-1.5 shadow-sm">
                            <XCircle className="h-3.5 w-3.5" /><span>Reject</span>
                          </button>
                        </div>
                      ) : <span className="text-[#00078b]/40 text-xs">—</span>}
                    </td>
                  )}
                </tr>
              ))}
              {leaves.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-[#00078b]/60 font-medium">No leave applications yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppLayout>
  );
}
