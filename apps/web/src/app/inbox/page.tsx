"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Inbox, Mail, MailOpen } from "lucide-react";
import { api, getToken } from "../../lib/api";

interface NotificationRow {
  id: number;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
}

export default function InboxPage() {
  const router = useRouter();
  const [rows, setRows] = useState<NotificationRow[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api<NotificationRow[]>("/notifications"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Load failed");
    }
  }, []);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    load();
    const t = setInterval(load, 15000); // poll — WebSocket push lands Phase 3
    return () => clearInterval(t);
  }, [router, load]);

  const markRead = async (id: number) => {
    try {
      await api(`/notifications/${id}/read`, { method: "POST" });
      setRows((r) => r.map((n) => (n.id === id ? { ...n, read: true } : n)));
    } catch { /* ignore */ }
  };

  const unread = rows.filter((r) => !r.read).length;

  return (
    <div className="min-h-screen p-6 relative overflow-x-hidden">
      <div className="absolute top-0 left-1/4 w-[500px] h-[300px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="max-w-3xl mx-auto relative">
        <div className="flex items-center space-x-4 mb-6">
          <Link href="/" className="glass-card rounded-xl p-2.5 text-slate-400 hover:text-slate-200"><ArrowLeft className="h-5 w-5" /></Link>
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-500/10 p-2 rounded-xl border border-indigo-500/20 text-indigo-400">
              <Inbox className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-slate-100">
                Inbox {unread > 0 && <span className="text-xs align-middle bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded-full px-2.5 py-1 ml-2">{unread} unread</span>}
              </h1>
              <p className="text-xs text-slate-400">Notifications from campus agents (auto-refreshes).</p>
            </div>
          </div>
        </div>

        {error && (
          <div className="text-amber-400 text-sm bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 mb-4">{error}</div>
        )}

        <div className="space-y-3">
          {rows.map((n) => (
            <button key={n.id} onClick={() => !n.read && markRead(n.id)}
              className={`w-full text-left glass-card rounded-2xl p-4 flex items-start space-x-3 ${!n.read ? "border-indigo-500/30" : "opacity-70"}`}>
              {n.read
                ? <MailOpen className="h-5 w-5 text-slate-500 shrink-0 mt-0.5" />
                : <Mail className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />}
              <div className="min-w-0">
                <div className="flex items-center space-x-2">
                  <span className={`text-sm font-semibold ${n.read ? "text-slate-400" : "text-slate-100"}`}>{n.title}</span>
                  {!n.read && <span className="h-2 w-2 rounded-full bg-indigo-400 shrink-0" />}
                </div>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">{n.body}</p>
                <p className="text-[10px] text-slate-600 mt-1.5">{new Date(n.created_at).toLocaleString()}</p>
              </div>
            </button>
          ))}
          {rows.length === 0 && (
            <div className="glass-panel rounded-2xl p-12 text-center">
              <Inbox className="h-8 w-8 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400 text-sm">No notifications yet.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
