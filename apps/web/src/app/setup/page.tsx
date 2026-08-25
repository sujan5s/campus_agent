"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Sparkles,
  BookOpen,
  Users,
  School,
  Building2,
  Plus,
  Trash2,
  Pencil,
  Upload,
  Download,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  X,
  LogOut,
} from "lucide-react";
import { api, getUser, getToken, clearAuth, AuthUser } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

/* ---------- types mirroring the backend schemas ---------- */
interface Subject {
  id: number;
  code: string;
  name: string;
  dept: string;
  semester: number;
  periods_per_week: number;
  needs_lab: boolean;
}
interface Teacher {
  id: number;
  name: string;
  email: string;
  dept: string;
  max_hours_per_day: number;
  subject_ids: number[];
  subject_codes: string[];
}
interface Section {
  id: number;
  name: string;
  dept: string;
  semester: number;
  strength: number;
}
interface Room {
  id: number;
  name: string;
  type: string;
  capacity: number;
}
interface ImportResult {
  created: number;
  updated: number;
  errors: string[];
}

type TabKey = "subjects" | "teachers" | "sections" | "rooms";

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: "subjects", label: "Subjects", icon: <BookOpen className="h-4 w-4" /> },
  { key: "teachers", label: "Teachers", icon: <Users className="h-4 w-4" /> },
  { key: "sections", label: "Sections", icon: <School className="h-4 w-4" /> },
  { key: "rooms", label: "Rooms", icon: <Building2 className="h-4 w-4" /> },
];

const CSV_TEMPLATES: Record<TabKey, string> = {
  subjects:
    "code,name,dept,semester,periods_per_week,needs_lab\nCS801,Deep Learning,CSE,8,4,false\nCS803,NLP Lab,CSE,8,2,true",
  teachers:
    "name,email,dept,max_hours_per_day,subject_codes\nDr. New Teacher,new.teacher@campus.edu,CSE,5,CS701;CS704",
  sections: "name,dept,semester,strength\nCSE-8A,CSE,8,60",
  rooms: "name,type,capacity\nLT-401,classroom,70\nAI Lab,lab,60",
};

const ROOM_TYPES = ["classroom", "lab", "auditorium", "seminar", "ground"];

export default function SetupPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [tab, setTab] = useState<TabKey>("subjects");

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);

  const [flash, setFlash] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [formSubjects, setFormSubjects] = useState<number[]>([]); // teacher subject picks
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const notify = (kind: "ok" | "err", text: string) => {
    setFlash({ kind, text });
    setTimeout(() => setFlash(null), 5000);
  };

  const loadAll = useCallback(async () => {
    try {
      const [su, te, se, ro] = await Promise.all([
        api<Subject[]>("/setup/subjects"),
        api<Teacher[]>("/setup/teachers"),
        api<Section[]>("/setup/sections"),
        api<Room[]>("/setup/rooms"),
      ]);
      setSubjects(su);
      setTeachers(te);
      setSections(se);
      setRooms(ro);
    } catch (e: unknown) {
      notify("err", e instanceof Error ? e.message : "Failed to load data");
    }
  }, []);

  // auth guard
  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setUser(getUser());
    loadAll();
  }, [router, loadAll]);

  const isAdmin = user?.role === "admin";

  const resetForm = () => {
    setForm({});
    setFormSubjects([]);
    setEditingId(null);
  };

  const switchTab = (t: TabKey) => {
    setTab(t);
    resetForm();
  };

  /* ---------- create / update ---------- */
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      let path = `/setup/${tab}`;
      let payload: Record<string, unknown> = {};
      if (tab === "subjects") {
        payload = {
          code: form.code,
          name: form.name,
          dept: form.dept || "CSE",
          semester: Number(form.semester || 7),
          periods_per_week: Number(form.periods_per_week || 4),
          needs_lab: form.needs_lab === "true",
        };
      } else if (tab === "teachers") {
        payload = {
          name: form.name,
          email: form.email,
          dept: form.dept || "CSE",
          max_hours_per_day: Number(form.max_hours_per_day || 5),
          subject_ids: formSubjects,
        };
      } else if (tab === "sections") {
        payload = {
          name: form.name,
          dept: form.dept || "CSE",
          semester: Number(form.semester || 7),
          strength: Number(form.strength || 60),
        };
      } else {
        payload = {
          name: form.name,
          type: form.type || "classroom",
          capacity: Number(form.capacity || 60),
        };
      }
      if (editingId !== null) path += `/${editingId}`;
      await api(path, {
        method: editingId !== null ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      notify("ok", editingId !== null ? "Updated." : "Added.");
      resetForm();
      await loadAll();
    } catch (e: unknown) {
      notify("err", e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this entry?")) return;
    try {
      await api(`/setup/${tab}/${id}`, { method: "DELETE" });
      notify("ok", "Deleted.");
      await loadAll();
    } catch (e: unknown) {
      notify("err", e instanceof Error ? e.message : "Delete failed");
    }
  };

  const startEdit = (row: Subject | Teacher | Section | Room) => {
    setEditingId(row.id);
    if (tab === "subjects") {
      const s = row as Subject;
      setForm({
        code: s.code, name: s.name, dept: s.dept,
        semester: String(s.semester),
        periods_per_week: String(s.periods_per_week),
        needs_lab: String(s.needs_lab),
      });
    } else if (tab === "teachers") {
      const t = row as Teacher;
      setForm({
        name: t.name, email: t.email, dept: t.dept,
        max_hours_per_day: String(t.max_hours_per_day),
      });
      setFormSubjects(t.subject_ids);
    } else if (tab === "sections") {
      const s = row as Section;
      setForm({
        name: s.name, dept: s.dept,
        semester: String(s.semester), strength: String(s.strength),
      });
    } else {
      const r = row as Room;
      setForm({ name: r.name, type: r.type, capacity: String(r.capacity) });
    }
  };

  /* ---------- CSV ---------- */
  const uploadCsv = async (file: File) => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api<ImportResult>(`/setup/import/${tab}`, {
        method: "POST",
        body: fd,
      });
      const errs = res.errors.length ? ` · ${res.errors.length} row error(s): ${res.errors[0]}` : "";
      notify(res.errors.length ? "err" : "ok", `Imported: ${res.created} created, ${res.updated} updated${errs}`);
      await loadAll();
    } catch (e: unknown) {
      notify("err", e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const downloadTemplate = () => {
    const blob = new Blob([CSV_TEMPLATES[tab]], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${tab}-template.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  /* ---------- small UI helpers ---------- */
  const inputCls = "bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] placeholder-[#00078b]/40 rounded-xl px-3.5 py-2 text-sm w-full focus:border-[#00078b] outline-none font-medium";
  const labelCls = "block text-[10px] text-[#00078b] uppercase tracking-wider font-bold mb-1";
  const thCls = "text-left text-[10px] text-[#00078b] uppercase tracking-wider font-bold px-4 py-3";
  const tdCls = "px-4 py-3 text-sm text-[#00078b] font-semibold";

  const counts: Record<TabKey, number> = {
    subjects: subjects.length,
    teachers: teachers.length,
    sections: sections.length,
    rooms: rooms.length,
  };

  return (
    <AppLayout title="Data Setup" subtitle="Master academic data — Subjects, Teachers, Sections & Rooms.">
      <div className="max-w-6xl mx-auto relative">
        {/* header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="bg-[#00078b] p-2 rounded-xl text-[#fdb813] shadow-md">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-[#00078b]">Academic Data Setup</h1>
              <p className="text-xs text-[#00078b]/70 font-medium">
                Master academic database for solver and campus agents.
              </p>
            </div>
          </div>
        </div>

        {!isAdmin && user && (
          <div className="flex items-center space-x-2 text-amber-700 text-sm bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-4 font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
            <span>You are signed in as <b>{user.role}</b> — data is read-only. Sign in as admin to edit.</span>
          </div>
        )}

        {/* tabs */}
        <div className="flex space-x-2 mb-5">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => switchTab(t.key)}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${tab === t.key
                  ? "bg-[#00078b] text-white shadow-md"
                  : "bg-white text-[#00078b] border border-[#00078b]/15 hover:bg-[#f6f6f6] shadow-sm"
                }`}
            >
              {t.icon}
              <span>{t.label}</span>
              <span className={`text-[10px] rounded-full px-2 py-0.5 font-bold ${tab === t.key ? "bg-[#fdb813] text-[#00078b]" : "bg-[#f6f6f6] text-[#00078b]"}`}>{counts[t.key]}</span>
            </button>
          ))}
        </div>

        {flash && (
          <div
            className={`flex items-center space-x-2 text-sm rounded-xl px-4 py-2.5 mb-4 border font-medium ${flash.kind === "ok"
                ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                : "text-amber-700 bg-amber-50 border-amber-200"
              }`}
          >
            {flash.kind === "ok" ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />}
            <span className="truncate">{flash.text}</span>
          </div>
        )}

        {/* add / edit form */}
        {isAdmin && (
          <form onSubmit={submit} className="bg-white border border-[#00078b]/15 rounded-2xl p-5 mb-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-[#00078b] flex items-center space-x-2">
                {editingId !== null ? <Pencil className="h-4 w-4 text-[#00078b]" /> : <Plus className="h-4 w-4 text-[#00078b]" />}
                <span>{editingId !== null ? `Edit ${tab.slice(0, -1)} #${editingId}` : `Add ${tab.slice(0, -1)}`}</span>
              </h2>
              <div className="flex items-center space-x-2">
                {editingId !== null && (
                  <button type="button" onClick={resetForm} className="text-xs text-[#00078b]/60 hover:text-[#00078b] flex items-center space-x-1 font-semibold">
                    <X className="h-3.5 w-3.5" /><span>Cancel edit</span>
                  </button>
                )}
                <button type="button" onClick={downloadTemplate} className="bg-white border border-[#00078b]/20 rounded-lg px-3 py-1.5 text-xs text-[#00078b] font-semibold flex items-center space-x-1.5 shadow-sm hover:bg-[#f6f6f6]">
                  <Download className="h-3.5 w-3.5" /><span>CSV template</span>
                </button>
                <label className="bg-white border border-[#00078b]/20 rounded-lg px-3 py-1.5 text-xs text-[#00078b] font-semibold flex items-center space-x-1.5 cursor-pointer shadow-sm hover:bg-[#f6f6f6]">
                  <Upload className="h-3.5 w-3.5" /><span>Import CSV</span>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".csv"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && uploadCsv(e.target.files[0])}
                  />
                </label>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {tab === "subjects" && (
                <>
                  <div><label className={labelCls}>Code</label>
                    <input required className={inputCls} placeholder="CS801" value={form.code || ""} onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
                  <div className="col-span-2"><label className={labelCls}>Name</label>
                    <input required className={inputCls} placeholder="Deep Learning" value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                  <div><label className={labelCls}>Dept</label>
                    <input className={inputCls} placeholder="CSE" value={form.dept || ""} onChange={(e) => setForm({ ...form, dept: e.target.value })} /></div>
                  <div><label className={labelCls}>Semester</label>
                    <input type="number" min={1} max={8} className={inputCls} placeholder="7" value={form.semester || ""} onChange={(e) => setForm({ ...form, semester: e.target.value })} /></div>
                  <div><label className={labelCls}>Periods/wk</label>
                    <input type="number" min={1} max={10} className={inputCls} placeholder="4" value={form.periods_per_week || ""} onChange={(e) => setForm({ ...form, periods_per_week: e.target.value })} /></div>
                  <div><label className={labelCls}>Needs lab?</label>
                    <select className={inputCls} value={form.needs_lab || "false"} onChange={(e) => setForm({ ...form, needs_lab: e.target.value })}>
                      <option value="false">No</option><option value="true">Yes</option>
                    </select></div>
                </>
              )}

              {tab === "teachers" && (
                <>
                  <div className="col-span-2"><label className={labelCls}>Name</label>
                    <input required className={inputCls} placeholder="Dr. Jane Doe" value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                  <div className="col-span-2"><label className={labelCls}>Email</label>
                    <input required type="email" className={inputCls} placeholder="jane.doe@campus.edu" value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
                  <div><label className={labelCls}>Dept</label>
                    <input className={inputCls} placeholder="CSE" value={form.dept || ""} onChange={(e) => setForm({ ...form, dept: e.target.value })} /></div>
                  <div><label className={labelCls}>Max hrs/day</label>
                    <input type="number" min={1} max={8} className={inputCls} placeholder="5" value={form.max_hours_per_day || ""} onChange={(e) => setForm({ ...form, max_hours_per_day: e.target.value })} /></div>
                  <div className="col-span-2 md:col-span-4 lg:col-span-6">
                    <label className={labelCls}>Can teach (select subjects)</label>
                    <div className="flex flex-wrap gap-2">
                      {subjects.map((s) => {
                        const on = formSubjects.includes(s.id);
                        return (
                          <button
                            type="button"
                            key={s.id}
                            onClick={() =>
                              setFormSubjects(on ? formSubjects.filter((x) => x !== s.id) : [...formSubjects, s.id])
                            }
                            className={`text-xs px-3 py-1.5 rounded-lg border font-bold transition-all ${on
                                ? "bg-[#00078b] text-white border-[#00078b]"
                                : "bg-[#f6f6f6] text-[#00078b] border-[#00078b]/20 hover:bg-[#00078b]/10"
                              }`}
                          >
                            {s.code}
                          </button>
                        );
                      })}
                      {subjects.length === 0 && (
                        <span className="text-xs text-[#00078b]/50">Add subjects first.</span>
                      )}
                    </div>
                  </div>
                </>
              )}

              {tab === "sections" && (
                <>
                  <div><label className={labelCls}>Name</label>
                    <input required className={inputCls} placeholder="CSE-8A" value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                  <div><label className={labelCls}>Dept</label>
                    <input className={inputCls} placeholder="CSE" value={form.dept || ""} onChange={(e) => setForm({ ...form, dept: e.target.value })} /></div>
                  <div><label className={labelCls}>Semester</label>
                    <input type="number" min={1} max={8} className={inputCls} placeholder="7" value={form.semester || ""} onChange={(e) => setForm({ ...form, semester: e.target.value })} /></div>
                  <div><label className={labelCls}>Strength</label>
                    <input type="number" min={1} className={inputCls} placeholder="60" value={form.strength || ""} onChange={(e) => setForm({ ...form, strength: e.target.value })} /></div>
                </>
              )}

              {tab === "rooms" && (
                <>
                  <div className="col-span-2"><label className={labelCls}>Name</label>
                    <input required className={inputCls} placeholder="LT-401" value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                  <div><label className={labelCls}>Type</label>
                    <select className={inputCls} value={form.type || "classroom"} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                      {ROOM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select></div>
                  <div><label className={labelCls}>Capacity</label>
                    <input type="number" min={1} className={inputCls} placeholder="70" value={form.capacity || ""} onChange={(e) => setForm({ ...form, capacity: e.target.value })} /></div>
                </>
              )}
            </div>

            <div className="mt-4">
              <button
                type="submit"
                disabled={busy}
                className="bg-[#00078b] hover:bg-[#000566] disabled:opacity-50 text-white text-sm font-bold rounded-xl px-5 py-2.5 transition-colors shadow-md"
              >
                {busy ? "Saving..." : editingId !== null ? "Save changes" : `Add ${tab.slice(0, -1)}`}
              </button>
            </div>
          </form>
        )}

        {/* data table */}
        <div className="bg-white border border-[#00078b]/15 rounded-2xl overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="border-b border-[#00078b]/15 bg-[#f6f6f6]">
              <tr>
                {tab === "subjects" && (<><th className={thCls}>Code</th><th className={thCls}>Name</th><th className={thCls}>Dept</th><th className={thCls}>Sem</th><th className={thCls}>Periods/wk</th><th className={thCls}>Lab</th></>)}
                {tab === "teachers" && (<><th className={thCls}>Name</th><th className={thCls}>Email</th><th className={thCls}>Dept</th><th className={thCls}>Max hrs/day</th><th className={thCls}>Can teach</th></>)}
                {tab === "sections" && (<><th className={thCls}>Name</th><th className={thCls}>Dept</th><th className={thCls}>Sem</th><th className={thCls}>Strength</th></>)}
                {tab === "rooms" && (<><th className={thCls}>Name</th><th className={thCls}>Type</th><th className={thCls}>Capacity</th></>)}
                {isAdmin && <th className={`${thCls} text-right`}>Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#00078b]/10">
              {tab === "subjects" && subjects.map((s) => (
                <tr key={s.id} className="hover:bg-[#f6f6f6]/60 transition">
                  <td className={`${tdCls} font-mono text-[#00078b] font-bold`}>{s.code}</td>
                  <td className={tdCls}>{s.name}</td>
                  <td className={tdCls}>{s.dept}</td>
                  <td className={tdCls}>{s.semester}</td>
                  <td className={tdCls}>{s.periods_per_week}</td>
                  <td className={tdCls}>{s.needs_lab ? <span className="text-emerald-700 font-extrabold text-xs bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">LAB</span> : <span className="text-[#00078b]/40">—</span>}</td>
                  {isAdmin && <RowActions onEdit={() => startEdit(s)} onDelete={() => remove(s.id)} />}
                </tr>
              ))}
              {tab === "teachers" && teachers.map((t) => (
                <tr key={t.id} className="hover:bg-[#f6f6f6]/60 transition">
                  <td className={tdCls}>{t.name}</td>
                  <td className={`${tdCls} text-[#00078b]/70 font-medium`}>{t.email}</td>
                  <td className={tdCls}>{t.dept}</td>
                  <td className={tdCls}>{t.max_hours_per_day}</td>
                  <td className={tdCls}>
                    <div className="flex flex-wrap gap-1">
                      {t.subject_codes.map((c) => (
                        <span key={c} className="text-[10px] font-mono bg-[#f6f6f6] text-[#00078b] border border-[#00078b]/20 font-bold rounded px-1.5 py-0.5">{c}</span>
                      ))}
                      {t.subject_codes.length === 0 && <span className="text-[#00078b]/40 text-xs italic">none</span>}
                    </div>
                  </td>
                  {isAdmin && <RowActions onEdit={() => startEdit(t)} onDelete={() => remove(t.id)} />}
                </tr>
              ))}
              {tab === "sections" && sections.map((s) => (
                <tr key={s.id} className="hover:bg-[#f6f6f6]/60 transition">
                  <td className={`${tdCls} font-bold`}>{s.name}</td>
                  <td className={tdCls}>{s.dept}</td>
                  <td className={tdCls}>{s.semester}</td>
                  <td className={tdCls}>{s.strength}</td>
                  {isAdmin && <RowActions onEdit={() => startEdit(s)} onDelete={() => remove(s.id)} />}
                </tr>
              ))}
              {tab === "rooms" && rooms.map((r) => (
                <tr key={r.id} className="hover:bg-[#f6f6f6]/60 transition">
                  <td className={`${tdCls} font-bold`}>{r.name}</td>
                  <td className={tdCls}><span className="text-xs uppercase tracking-wider font-bold text-[#00078b]/70">{r.type}</span></td>
                  <td className={tdCls}>{r.capacity}</td>
                  {isAdmin && <RowActions onEdit={() => startEdit(r)} onDelete={() => remove(r.id)} />}
                </tr>
              ))}
              {counts[tab] === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-[#00078b]/60 font-medium">
                    No {tab} yet — add one above or import a CSV.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="text-[11px] text-[#00078b]/70 font-medium mt-4 leading-relaxed">
          CSV import upserts by unique key (subject <b>code</b>, teacher <b>email</b>, section/room <b>name</b>).
          New teachers get the default password <code className="bg-white border border-[#00078b]/15 px-1 rounded text-[#00078b] font-bold">faculty123</code>.
          Once this data is complete, Phase 1&apos;s <b>Generate Timetable</b> reads it directly — nothing is re-entered.
        </p>
      </div>
    </AppLayout>
  );
}

function RowActions({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <td className="px-4 py-3 text-right whitespace-nowrap">
      <button onClick={onEdit} className="text-[#00078b]/60 hover:text-[#00078b] p-1.5 transition-colors" title="Edit">
        <Pencil className="h-4 w-4" />
      </button>
      <button onClick={onDelete} className="text-rose-500 hover:text-rose-700 p-1.5 transition-colors" title="Delete">
        <Trash2 className="h-4 w-4" />
      </button>
    </td>
  );
}
