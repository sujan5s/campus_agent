"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, ClipboardCheck, CheckCircle2, XCircle, Bot, RefreshCw, FlaskConical,
} from "lucide-react";
import { api, getToken, getUser } from "../../lib/api";

interface PlanItem {
  leave_date: string; leave_day: string; leave_period: number; leave_time: string;
  section: string; room: string;
  missed_subject: string; missed_subject_name: string;
  partner: string | null; partner_subject: string | null; partner_subject_name: string | null;
  recovery_date: string | null; recovery_day: string | null;
  recovery_period: number | null; recovery_time: string | null;
  rationale: string;
  warning?: boolean;
}
interface ApprovalCard {
  id: number;
  kind: string;
  ref_id: number;
  status: string;
  plan?: {
    teacher: string; from_date: string; to_date: string; reason: string;
    lessons_affected: number; exchanged: number; items: PlanItem[];
  };
}
interface DecideResult {
  approval_id: number; status: string; agent_response: string; steps: string[];
}

export default function ApprovalsPage() {
  const router = useRouter();
  const [cards, setCards] = useState<ApprovalCard[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [result, setResult] = useState<DecideResult | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setCards(await api<ApprovalCard[]>("/approvals?status=pending"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Load failed");
    }
  }, []);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    if (getUser()?.role !== "admin") { router.replace("/"); return; }
    load();
  }, [router, load]);

  const decide = async (id: number, action: "approve" | "reject") => {
    setBusyId(id);
    setResult(null);
    setError("");
    try {
      const r = await api<DecideResult>(`/approvals/${id}/decide`, {
        method: "POST", body: JSON.stringify({ action }),
      });
      setResult(r);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="min-h-screen p-6 relative overflow-x-hidden">
      <div className="absolute top-0 right-1/3 w-[500px] h-[300px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="max-w-4xl mx-auto relative">
        <div className="flex items-center space-x-4 mb-6">
          <Link href="/" className="glass-card rounded-xl p-2.5 text-slate-400 hover:text-slate-200"><ArrowLeft className="h-5 w-5" /></Link>
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-500/10 p-2 rounded-xl border border-indigo-500/20 text-indigo-400">
              <ClipboardCheck className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-slate-100">Approvals</h1>
              <p className="text-xs text-slate-400">
                Human-in-the-loop: the agent proposed these plans and is paused until you decide.
              </p>
            </div>
          </div>
        </div>

        {error && (
          <div className="text-amber-400 text-sm bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 mb-4">{error}</div>
        )}

        {result && (
          <div className="glass-panel rounded-2xl p-5 mb-5 border border-indigo-500/20">
            <div className="flex items-center space-x-2 text-indigo-300 text-sm font-semibold mb-2">
              <Bot className="h-4 w-4" /><span>Substitution Agent — workflow resumed &amp; completed</span>
            </div>
            <p className="text-sm text-slate-300 whitespace-pre-wrap">{result.agent_response}</p>
          </div>
        )}

        {cards.length === 0 && !result && (
          <div className="glass-panel rounded-2xl p-12 text-center">
            <ClipboardCheck className="h-8 w-8 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 text-sm">No pending approvals.</p>
            <p className="text-slate-500 text-xs mt-2">Approve a leave in <Link href="/leaves" className="text-indigo-400 underline">Leaves</Link> and the agent&apos;s plan will appear here.</p>
          </div>
        )}

        {cards.map((c) => (
          <div key={c.id} className="glass-panel rounded-2xl p-5 mb-5">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-3">
              <div>
                <div className="flex items-center space-x-2">
                  <Bot className="h-4 w-4 text-indigo-400" />
                  <h2 className="text-sm font-semibold text-slate-100">
                    Period-exchange plan — {c.plan?.teacher}
                  </h2>
                  <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                    awaiting approval
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Leave {c.plan?.from_date} → {c.plan?.to_date} · {c.plan?.reason} ·{" "}
                  <span className="text-emerald-400 font-semibold">{c.plan?.exchanged}/{c.plan?.lessons_affected} lessons exchanged</span>
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button onClick={() => decide(c.id, "approve")} disabled={busyId === c.id}
                  className="flex items-center space-x-1.5 bg-emerald-600/80 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl px-4 py-2">
                  {busyId === c.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  <span>Approve plan</span>
                </button>
                <button onClick={() => decide(c.id, "reject")} disabled={busyId === c.id}
                  className="flex items-center space-x-1.5 bg-rose-600/70 hover:bg-rose-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl px-4 py-2">
                  <XCircle className="h-4 w-4" /><span>Reject</span>
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-slate-800">
                <tr>
                  {["Leave date", "Class", "Missed subject", "Partner teaches", "Recovery", "Why"].map((h) => (
                    <th key={h} className="text-left text-[10px] text-slate-400 uppercase tracking-wider font-semibold px-3 py-2 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {c.plan?.items.map((it, i) => (
                  <tr key={i} className={it.warning ? "bg-amber-500/[0.07]" : ""}>
                    <td className="px-3 py-2.5 text-sm text-slate-300 whitespace-nowrap">
                      {it.leave_date}
                      <div className="text-[10px] text-slate-500">{it.leave_day} P{it.leave_period} · {it.leave_time}</div>
                    </td>
                    <td className="px-3 py-2.5 text-sm">
                      <span className="text-slate-300 font-medium">{it.section}</span>
                      <div className="text-[10px] text-slate-500">{it.room}</div>
                    </td>
                    <td className="px-3 py-2.5 text-sm">
                      <span className="font-mono text-indigo-300 font-bold text-xs">{it.missed_subject}</span>
                      <div className="text-[10px] text-slate-500">{it.missed_subject_name}</div>
                    </td>
                    <td className="px-3 py-2.5 text-sm">
                      {it.partner ? (
                        <>
                          <span className="text-emerald-300 font-medium">{it.partner}</span>
                          <div className="text-[10px] text-slate-500 font-mono">{it.partner_subject}</div>
                        </>
                      ) : <span className="text-rose-400 font-medium">no exchange</span>}
                    </td>
                    <td className="px-3 py-2.5 text-sm text-slate-300 whitespace-nowrap">
                      {it.recovery_date ? (
                        <>
                          {it.recovery_date}
                          <div className="text-[10px] text-slate-500">{it.recovery_day} P{it.recovery_period} · {it.recovery_time}</div>
                        </>
                      ) : <span className="text-slate-600">—</span>}
                    </td>
                    <td className={`px-3 py-2.5 text-xs max-w-[200px] ${it.warning ? "text-amber-400/90" : "text-slate-500"}`}>{it.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
