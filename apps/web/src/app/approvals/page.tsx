"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, ClipboardCheck, CheckCircle2, XCircle, Bot, RefreshCw, FlaskConical,
} from "lucide-react";
import { api, getToken, getUser } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

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
    <AppLayout title="Substitution Approvals" subtitle="Review and approve proposed faculty substitution plans.">
      <div className="max-w-4xl mx-auto relative">
        <div className="flex items-center space-x-3 mb-6">
          <div className="bg-[#00078b] p-2 rounded-xl text-[#fdb813] shadow-md">
            <ClipboardCheck className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-bold text-xl text-[#00078b]">Approvals Queue</h1>
            <p className="text-xs text-[#00078b]/70 font-medium">
              Human-in-the-loop: review AI proposed substitution plans.
            </p>
          </div>
        </div>

        {error && (
          <div className="text-amber-700 font-medium text-sm bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-4">{error}</div>
        )}

        {result && (
          <div className="bg-white border border-[#00078b]/15 shadow-sm rounded-2xl p-5 mb-5">
            <div className="flex items-center space-x-2 text-[#00078b] text-sm font-bold mb-2">
              <Bot className="h-4 w-4 text-[#fdb813]" /><span>Substitution Agent — workflow resumed &amp; completed</span>
            </div>
            <p className="text-sm text-[#00078b]/80 font-medium whitespace-pre-wrap">{result.agent_response}</p>
          </div>
        )}

        {cards.length === 0 && !result && (
          <div className="bg-white border border-[#00078b]/15 rounded-2xl p-12 text-center shadow-sm">
            <ClipboardCheck className="h-8 w-8 text-[#00078b]/40 mx-auto mb-3" />
            <p className="text-[#00078b] font-semibold text-sm">No pending approvals.</p>
            <p className="text-[#00078b]/70 text-xs mt-2 font-medium">Approve a leave in <Link href="/leaves" className="text-[#00078b] font-bold underline">Leaves</Link> and the agent&apos;s plan will appear here.</p>
          </div>
        )}

        {cards.map((c) => (
          <div key={c.id} className="bg-white border border-[#00078b]/15 rounded-2xl p-5 mb-5 shadow-sm">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-3">
              <div>
                <div className="flex items-center space-x-2">
                  <Bot className="h-4 w-4 text-[#00078b]" />
                  <h2 className="text-sm font-bold text-[#00078b]">
                    Period-exchange plan — {c.plan?.teacher}
                  </h2>
                  <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-[#fdb813] text-[#00078b]">
                    awaiting approval
                  </span>
                </div>
                <p className="text-xs text-[#00078b]/70 mt-1 font-medium">
                  Leave {c.plan?.from_date} → {c.plan?.to_date} · {c.plan?.reason} ·{" "}
                  <span className="text-emerald-700 font-bold">{c.plan?.exchanged}/{c.plan?.lessons_affected} lessons exchanged</span>
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button onClick={() => decide(c.id, "approve")} disabled={busyId === c.id}
                  className="flex items-center space-x-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-bold rounded-xl px-4 py-2 shadow-sm">
                  {busyId === c.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  <span>Approve plan</span>
                </button>
                <button onClick={() => decide(c.id, "reject")} disabled={busyId === c.id}
                  className="flex items-center space-x-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white text-sm font-bold rounded-xl px-4 py-2 shadow-sm">
                  <XCircle className="h-4 w-4" /><span>Reject</span>
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-[#00078b]/15 bg-[#f6f6f6]">
                <tr>
                  {["Leave date", "Class", "Missed subject", "Partner teaches", "Recovery", "Why"].map((h) => (
                    <th key={h} className="text-left text-[10px] text-[#00078b] uppercase tracking-wider font-bold px-3 py-2 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#00078b]/10">
                {c.plan?.items.map((it, i) => (
                  <tr key={i} className={it.warning ? "bg-amber-50" : "hover:bg-[#f6f6f6]/60 transition"}>
                    <td className="px-3 py-2.5 text-sm text-[#00078b] font-semibold whitespace-nowrap">
                      {it.leave_date}
                      <div className="text-[10px] text-[#00078b]/60 font-medium">{it.leave_day} P{it.leave_period} · {it.leave_time}</div>
                    </td>
                    <td className="px-3 py-2.5 text-sm">
                      <span className="text-[#00078b] font-bold">{it.section}</span>
                      <div className="text-[10px] text-[#00078b]/60 font-medium">{it.room}</div>
                    </td>
                    <td className="px-3 py-2.5 text-sm">
                      <span className="font-mono text-[#00078b] font-bold text-xs">{it.missed_subject}</span>
                      <div className="text-[10px] text-[#00078b]/60 font-medium">{it.missed_subject_name}</div>
                    </td>
                    <td className="px-3 py-2.5 text-sm">
                      {it.partner ? (
                        <>
                          <span className="text-emerald-700 font-bold">{it.partner}</span>
                          <div className="text-[10px] text-[#00078b]/60 font-mono font-medium">{it.partner_subject}</div>
                        </>
                      ) : <span className="text-rose-600 font-bold">no exchange</span>}
                    </td>
                    <td className="px-3 py-2.5 text-sm text-[#00078b] font-semibold whitespace-nowrap">
                      {it.recovery_date ? (
                        <>
                          {it.recovery_date}
                          <div className="text-[10px] text-[#00078b]/60 font-medium">{it.recovery_day} P{it.recovery_period} · {it.recovery_time}</div>
                        </>
                      ) : <span className="text-[#00078b]/40">—</span>}
                    </td>
                    <td className={`px-3 py-2.5 text-xs max-w-[200px] font-medium ${it.warning ? "text-amber-800 font-semibold" : "text-[#00078b]/70"}`}>{it.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        ))}
      </div>
    </AppLayout>
  );
}
