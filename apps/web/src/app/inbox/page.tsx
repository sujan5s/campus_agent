"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Inbox, Mail, MailOpen } from "lucide-react";
import { api, getToken } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

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
    <AppLayout title="Campus Inbox" subtitle="Notifications and activity log from campus operations.">
      <div className="max-w-3xl mx-auto relative">
        <div className="flex items-center space-x-3 mb-6">
          <div className="bg-[#00078b] p-2 rounded-xl text-[#fdb813] shadow-md">
            <Inbox className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-bold text-xl text-[#00078b]">
              Inbox {unread > 0 && <span className="text-xs align-middle bg-[#fdb813] text-[#00078b] font-bold rounded-full px-2.5 py-1 ml-2">{unread} unread</span>}
            </h1>
            <p className="text-xs text-[#00078b]/70 font-medium">Notifications from campus agents.</p>
          </div>
        </div>

        {error && (
          <div className="text-amber-700 font-medium text-sm bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-4">{error}</div>
        )}

        <div className="space-y-3">
          {rows.map((n) => (
            <button key={n.id} onClick={() => !n.read && markRead(n.id)}
              className={`w-full text-left bg-white border border-[#00078b]/15 shadow-sm rounded-2xl p-4 flex items-start space-x-3 transition-colors hover:bg-[#f6f6f6]/60 ${!n.read ? "border-[#00078b]" : "opacity-75"}`}>
              {n.read
                ? <MailOpen className="h-5 w-5 text-[#00078b]/40 shrink-0 mt-0.5" />
                : <Mail className="h-5 w-5 text-[#00078b] shrink-0 mt-0.5" />}
              <div className="min-w-0">
                <div className="flex items-center space-x-2">
                  <span className={`text-sm font-bold ${n.read ? "text-[#00078b]/70" : "text-[#00078b]"}`}>{n.title}</span>
                  {!n.read && <span className="h-2 w-2 rounded-full bg-[#fdb813] shrink-0" />}
                </div>
                <p className="text-xs text-[#00078b]/80 mt-1 leading-relaxed font-medium">{n.body}</p>
                <p className="text-[10px] text-[#00078b]/50 mt-1.5 font-medium">{new Date(n.created_at).toLocaleString()}</p>
              </div>
            </button>
          ))}
          {rows.length === 0 && (
            <div className="bg-white border border-[#00078b]/15 rounded-2xl p-12 text-center shadow-sm">
              <Inbox className="h-8 w-8 text-[#00078b]/40 mx-auto mb-3" />
              <p className="text-[#00078b] font-semibold text-sm">No notifications yet.</p>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
