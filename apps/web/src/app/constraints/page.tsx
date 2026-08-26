"use client";

/**
 * Constraints — the editable rulebook behind timetable generation (Phase 2.4).
 *
 * Three tabs, all reading and writing the same registry the solver compiles:
 *   Rules       — every generation rule, grouped by scope, with an "Ask AI" box
 *                 that turns a sentence into typed changes you confirm first.
 *   Assignments — who teaches which subject for which class (a hard pin).
 *   Electives   — open-elective bands: shared periods per semester with the
 *                 parallel baskets that run inside them.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  SlidersHorizontal,
  Sparkles,
  Plus,
  Trash2,
  Pencil,
  Play,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Save,
  X,
  Layers,
  UserCog,
  ListChecks,
  Wand2,
  Info,
} from "lucide-react";
import { api, getToken, getUser, AuthUser } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

// ---------- types mirroring app/api/constraints.py ----------

interface CatalogField {
  name: string;
  type:
    | "day"
    | "period"
    | "days"
    | "periods"
    | "int"
    | "bool"
    | "teacher"
    | "subject"
    | "band";
  label: string;
  min?: number;
  max?: number;
}
interface CatalogKind {
  kind: string;
  label: string;
  help: string;
  scopes: string[];
  fields: CatalogField[];
  priority: "hard" | "soft";
  unique_per_scope: boolean;
}
type Params = Record<string, unknown>;
interface ConstraintRow {
  id: number;
  kind: string;
  label: string;
  scope_type: "global" | "semester" | "section";
  scope_value: string;
  params: Params;
  priority: "hard" | "soft";
  weight: number;
  enabled: boolean;
  source: "seed" | "ui" | "llm";
  origin_prompt: string;
  description: string;
}
interface Ctx {
  days: string[];
  periods: number[];
  sections: { id: number; name: string; semester: number; dept: string }[];
  semesters: number[];
  subjects: { id: number; code: string; name: string; semester: number }[];
  teachers: { id: number; name: string }[];
  bands: {
    id: number;
    name: string;
    semester: number;
    periods_per_week: number;
    active: boolean;
  }[];
}
interface Registry {
  constraints: ConstraintRow[];
  catalog: CatalogKind[];
  context: Ctx;
  llm: boolean;
}
interface OpPreview {
  op: string;
  id?: number | null;
  kind?: string | null;
  scope_type: string;
  scope_value: string;
  params: Params;
  description?: string;
  before?: string;
  ok: boolean;
  error?: string;
}
interface AssignmentSubject {
  subject_id: number;
  subject_code: string;
  subject_name: string;
  needs_lab: boolean;
  periods_per_week: number;
  teacher_id: number | null;
  eligible: { id: number; name: string }[];
}
interface AssignmentSection {
  section_id: number;
  section: string;
  semester: number;
  dept: string;
  subjects: AssignmentSubject[];
}
interface Offering {
  id?: number;
  subject_id: number;
  subject_code?: string;
  teacher_id: number;
  teacher?: string;
  room_id: number;
  room?: string;
  capacity: number;
}
interface ElectiveBand {
  id: number;
  name: string;
  dept: string;
  semester: number;
  periods_per_week: number;
  needs_block: boolean;
  active: boolean;
  offerings: Offering[];
}
interface RoomRow {
  id: number;
  name: string;
  type: string;
  capacity: number;
}

type Flash = { kind: "ok" | "err"; text: string } | null;
type Tab = "rules" | "assignments" | "electives";

const CARD = "bg-white border border-[#00078b]/15 rounded-2xl shadow-sm";
const BTN_PRIMARY =
  "flex items-center space-x-2 bg-[#00078b] hover:bg-[#000566] disabled:opacity-60 text-white text-sm font-bold rounded-xl px-4 py-2.5 transition-colors shadow-md";
const BTN_GHOST =
  "flex items-center space-x-2 bg-white border border-[#00078b]/20 rounded-xl px-3 py-2 text-xs font-bold text-[#00078b] hover:bg-[#f6f6f6] disabled:opacity-50 transition-colors";
const FIELD =
  "bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-[#00078b]";

export default function ConstraintsPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [tab, setTab] = useState<Tab>("rules");
  const [reg, setReg] = useState<Registry | null>(null);
  const [flash, setFlash] = useState<Flash>(null);
  const [busy, setBusy] = useState(false);
  const isAdmin = user?.role === "admin";

  // --- Ask AI ---
  const [prompt, setPrompt] = useState("");
  const [thinking, setThinking] = useState(false);
  const [preview, setPreview] = useState<OpPreview[] | null>(null);
  const [notes, setNotes] = useState("");

  // --- add / edit form ---
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ConstraintRow | null>(null);
  const [fKind, setFKind] = useState("");
  const [fScopeType, setFScopeType] = useState("global");
  const [fScopeValue, setFScopeValue] = useState("");
  const [fParams, setFParams] = useState<Params>({});

  // --- assignments ---
  const [assign, setAssign] = useState<AssignmentSection[] | null>(null);
  const [assignDirty, setAssignDirty] = useState<Record<string, number | null>>({});

  // --- electives ---
  const [bands, setBands] = useState<ElectiveBand[] | null>(null);
  const [rooms, setRooms] = useState<RoomRow[]>([]);
  const [bandDraft, setBandDraft] = useState<ElectiveBand | null>(null);

  const loadRegistry = useCallback(async () => {
    const data = await api<Registry>("/constraints");
    setReg(data);
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setUser(getUser());
    (async () => {
      try {
        const [r, a, b, rm] = await Promise.all([
          api<Registry>("/constraints"),
          api<AssignmentSection[]>("/setup/assignments"),
          api<ElectiveBand[]>("/setup/electives"),
          api<RoomRow[]>("/setup/rooms"),
        ]);
        setReg(r);
        setAssign(a);
        setBands(b);
        setRooms(rm);
      } catch (e: unknown) {
        setFlash({ kind: "err", text: e instanceof Error ? e.message : "Load failed" });
      }
    })();
  }, [router]);

  const catalogByKind = useMemo(() => {
    const m = new Map<string, CatalogKind>();
    reg?.catalog.forEach((k) => m.set(k.kind, k));
    return m;
  }, [reg]);

  const grouped = useMemo(() => {
    const out: { key: string; title: string; rows: ConstraintRow[] }[] = [];
    const push = (key: string, title: string, rows: ConstraintRow[]) => {
      if (rows.length) out.push({ key, title, rows });
    };
    const all = reg?.constraints ?? [];
    push("global", "All classes", all.filter((c) => c.scope_type === "global"));
    (reg?.context.semesters ?? []).forEach((sem) =>
      push(
        `sem-${sem}`,
        `Semester ${sem}`,
        all.filter((c) => c.scope_type === "semester" && c.scope_value === String(sem))
      )
    );
    (reg?.context.sections ?? []).forEach((sec) =>
      push(
        `sec-${sec.id}`,
        `${sec.name} · semester ${sec.semester}`,
        all.filter((c) => c.scope_type === "section" && c.scope_value === sec.name)
      )
    );
    return out;
  }, [reg]);

  // ---------- registry actions ----------

  const refresh = async (msg?: string) => {
    await loadRegistry();
    if (msg) setFlash({ kind: "ok", text: msg });
  };

  const toggle = async (row: ConstraintRow) => {
    setBusy(true);
    try {
      await api(`/constraints/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !row.enabled }),
      });
      await refresh(`${row.enabled ? "Disabled" : "Enabled"} — ${row.description}`);
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Update failed" });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (row: ConstraintRow) => {
    setBusy(true);
    try {
      await api(`/constraints/${row.id}`, { method: "DELETE" });
      await refresh(`Removed — ${row.description}`);
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Delete failed" });
    } finally {
      setBusy(false);
    }
  };

  const openAdd = () => {
    const first = reg?.catalog[0];
    setEditing(null);
    setFKind(first?.kind ?? "");
    setFScopeType(first?.scopes[0] ?? "global");
    setFScopeValue("");
    setFParams({});
    setFormOpen(true);
  };

  const openEdit = (row: ConstraintRow) => {
    setEditing(row);
    setFKind(row.kind);
    setFScopeType(row.scope_type);
    setFScopeValue(row.scope_value);
    setFParams({ ...row.params });
    setFormOpen(true);
  };

  const submitForm = async () => {
    setBusy(true);
    try {
      const body = {
        kind: fKind,
        scope_type: fScopeType,
        scope_value: fScopeValue,
        params: fParams,
      };
      if (editing) {
        await api(`/constraints/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            params: fParams,
            scope_type: fScopeType,
            scope_value: fScopeValue,
          }),
        });
      } else {
        await api("/constraints", { method: "POST", body: JSON.stringify(body) });
      }
      setFormOpen(false);
      await refresh(editing ? "Constraint updated." : "Constraint added.");
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Save failed" });
    } finally {
      setBusy(false);
    }
  };

  // ---------- ask AI ----------

  const askAi = async () => {
    if (!prompt.trim()) return;
    setThinking(true);
    setPreview(null);
    setFlash(null);
    try {
      const r = await api<{ ops: OpPreview[]; notes: string; llm: boolean }>(
        "/constraints/interpret",
        { method: "POST", body: JSON.stringify({ prompt }) }
      );
      setPreview(r.ops);
      setNotes(r.notes);
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Could not read that" });
    } finally {
      setThinking(false);
    }
  };

  const applyAi = async () => {
    const ops = (preview ?? []).filter((o) => o.ok);
    if (!ops.length) return;
    setBusy(true);
    try {
      const r = await api<{ applied: unknown[]; failed: { error: string }[] }>(
        "/constraints/apply",
        { method: "POST", body: JSON.stringify({ ops, prompt }) }
      );
      setPreview(null);
      setPrompt("");
      await loadRegistry();
      setFlash({
        kind: r.failed.length ? "err" : "ok",
        text:
          `${r.applied.length} change(s) applied.` +
          (r.failed.length ? ` ${r.failed.map((f) => f.error).join(" ")}` : ""),
      });
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Apply failed" });
    } finally {
      setBusy(false);
    }
  };

  // ---------- generate ----------

  const generate = async () => {
    setBusy(true);
    setFlash(null);
    try {
      const r = await api<{
        version: number;
        lessons: number;
        load_gap: number;
        wall_time_s: number;
        elective_periods?: number;
      }>("/timetable/generate", { method: "POST" });
      setFlash({
        kind: "ok",
        text:
          `Generated v${r.version} with these rules: ${r.lessons} lessons` +
          (r.elective_periods ? ` + ${r.elective_periods} elective period(s)` : "") +
          `, load gap ${r.load_gap}, solved in ${r.wall_time_s}s (provably clash-free).`,
      });
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Generation failed" });
    } finally {
      setBusy(false);
    }
  };

  // ---------- assignments ----------

  const setPin = (sectionId: number, subjectId: number, teacherId: number | null) => {
    setAssignDirty((d) => ({ ...d, [`${sectionId}:${subjectId}`]: teacherId }));
    setAssign((rows) =>
      (rows ?? []).map((sec) =>
        sec.section_id !== sectionId
          ? sec
          : {
              ...sec,
              subjects: sec.subjects.map((s) =>
                s.subject_id === subjectId ? { ...s, teacher_id: teacherId } : s
              ),
            }
      )
    );
  };

  const saveAssignments = async () => {
    const items = Object.entries(assignDirty).map(([key, teacher_id]) => {
      const [section_id, subject_id] = key.split(":").map(Number);
      return { section_id, subject_id, teacher_id };
    });
    if (!items.length) return;
    setBusy(true);
    try {
      const r = await api<{ saved: number; cleared: number }>("/setup/assignments", {
        method: "PUT",
        body: JSON.stringify({ items }),
      });
      setAssignDirty({});
      setAssign(await api<AssignmentSection[]>("/setup/assignments"));
      setFlash({
        kind: "ok",
        text: `${r.saved} assignment(s) pinned, ${r.cleared} cleared. Regenerate to apply.`,
      });
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Save failed" });
    } finally {
      setBusy(false);
    }
  };

  // ---------- electives ----------

  const newBand = (): ElectiveBand => ({
    id: 0,
    name: `OE-${(bands?.length ?? 0) + 1}`,
    dept: reg?.context.sections[0]?.dept ?? "CSE",
    semester: reg?.context.semesters.find((s) => s >= 6) ?? reg?.context.semesters[0] ?? 7,
    periods_per_week: 3,
    needs_block: false,
    active: true,
    offerings: [],
  });

  const saveBand = async () => {
    if (!bandDraft) return;
    setBusy(true);
    try {
      const body = {
        name: bandDraft.name,
        dept: bandDraft.dept,
        semester: bandDraft.semester,
        periods_per_week: bandDraft.periods_per_week,
        needs_block: bandDraft.needs_block,
        active: bandDraft.active,
        offerings: bandDraft.offerings.map((o) => ({
          subject_id: o.subject_id,
          teacher_id: o.teacher_id,
          room_id: o.room_id,
          capacity: o.capacity,
        })),
      };
      if (bandDraft.id) {
        await api(`/setup/electives/${bandDraft.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
      } else {
        await api("/setup/electives", { method: "POST", body: JSON.stringify(body) });
      }
      setBandDraft(null);
      setBands(await api<ElectiveBand[]>("/setup/electives"));
      setFlash({ kind: "ok", text: "Elective band saved. Regenerate to apply." });
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Save failed" });
    } finally {
      setBusy(false);
    }
  };

  const deleteBand = async (b: ElectiveBand) => {
    setBusy(true);
    try {
      await api(`/setup/electives/${b.id}`, { method: "DELETE" });
      setBands(await api<ElectiveBand[]>("/setup/electives"));
      setFlash({ kind: "ok", text: `Removed ${b.name}.` });
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "Delete failed" });
    } finally {
      setBusy(false);
    }
  };

  // ---------- dynamic param inputs ----------

  const renderField = (f: CatalogField) => {
    const ctx = reg!.context;
    const key =
      f.type === "teacher"
        ? "teacher_id"
        : f.type === "subject"
        ? "subject_id"
        : f.type === "band"
        ? "band_id"
        : f.name;
    const val = fParams[key];
    const set = (v: unknown) => setFParams((p) => ({ ...p, [key]: v }));

    if (f.type === "day") {
      return (
        <select className={FIELD} value={String(val ?? "")} onChange={(e) => set(e.target.value)}>
          <option value="">choose…</option>
          {ctx.days.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      );
    }
    if (f.type === "period") {
      return (
        <select className={FIELD} value={String(val ?? "")} onChange={(e) => set(Number(e.target.value))}>
          <option value="">choose…</option>
          {ctx.periods.map((p) => (
            <option key={p} value={p}>P{p}</option>
          ))}
        </select>
      );
    }
    if (f.type === "days" || f.type === "periods") {
      const opts: (string | number)[] = f.type === "days" ? ctx.days : ctx.periods;
      const cur = Array.isArray(val) ? (val as (string | number)[]) : [];
      return (
        <div className="flex flex-wrap gap-1.5">
          {opts.map((o) => {
            const on = cur.some((c) => String(c) === String(o));
            return (
              <button
                key={String(o)}
                type="button"
                onClick={() =>
                  set(on ? cur.filter((c) => String(c) !== String(o)) : [...cur, o])
                }
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors ${
                  on
                    ? "bg-[#00078b] text-white border-[#00078b]"
                    : "bg-[#f6f6f6] text-[#00078b] border-[#00078b]/20 hover:bg-white"
                }`}
              >
                {f.type === "periods" ? `P${o}` : o}
              </button>
            );
          })}
          {!cur.length && (
            <span className="text-[11px] text-[#00078b]/50 font-medium self-center">
              none picked = {f.type === "days" ? "every day" : "whole day"}
            </span>
          )}
        </div>
      );
    }
    if (f.type === "int") {
      return (
        <input
          type="number"
          min={f.min}
          max={f.max}
          className={`${FIELD} w-20`}
          value={val === undefined || val === null ? "" : String(val)}
          onChange={(e) => set(e.target.value === "" ? undefined : Number(e.target.value))}
        />
      );
    }
    if (f.type === "bool") {
      return (
        <label className="flex items-center space-x-2 cursor-pointer">
          <input
            type="checkbox"
            className="accent-[#00078b]"
            checked={val === undefined ? true : Boolean(val)}
            onChange={(e) => set(e.target.checked)}
          />
          <span className="text-xs font-semibold text-[#00078b]">enforced</span>
        </label>
      );
    }
    if (f.type === "teacher") {
      return (
        <select className={FIELD} value={String(val ?? "")} onChange={(e) => set(Number(e.target.value))}>
          <option value="">choose…</option>
          {ctx.teachers.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      );
    }
    if (f.type === "band") {
      // only the bands of the semester this rule is scoped to can be pinned
      const mine = ctx.bands.filter(
        (b) => !fScopeValue || String(b.semester) === String(fScopeValue)
      );
      return (
        <select className={FIELD} value={String(val ?? "")} onChange={(e) => set(Number(e.target.value))}>
          <option value="">
            {mine.length === 1 ? `${mine[0].name} (only band)` : "choose…"}
          </option>
          {mine.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} · {b.periods_per_week}/wk
            </option>
          ))}
        </select>
      );
    }
    return (
      <select className={FIELD} value={String(val ?? "")} onChange={(e) => set(Number(e.target.value))}>
        <option value="">choose…</option>
        {ctx.subjects.map((s) => (
          <option key={s.id} value={s.id}>
            {s.code} — {s.name}
          </option>
        ))}
      </select>
    );
  };

  const activeKind = catalogByKind.get(fKind);

  // ---------- render ----------

  return (
    <AppLayout
      title="Constraints"
      subtitle="The rules the CP-SAT solver obeys — visible, editable, and changeable in plain English."
    >
      <div className="max-w-6xl mx-auto">
        {/* header */}
        <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
          <div className="flex items-center space-x-3">
            <div className="bg-[#00078b] p-2 rounded-xl text-[#fdb813] shadow-md">
              <SlidersHorizontal className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-[#00078b]">Timetable Constraints</h1>
              <p className="text-xs text-[#00078b]/70 font-medium">
                Every rule below is applied on the next generation — per class, per semester, or campus-wide.
              </p>
            </div>
          </div>
          {isAdmin && (
            <button onClick={generate} disabled={busy} className={BTN_PRIMARY}>
              {busy ? (
                <RefreshCw className="h-4 w-4 animate-spin text-[#fdb813]" />
              ) : (
                <Play className="h-4 w-4 text-[#fdb813]" />
              )}
              <span>{busy ? "Working…" : "Generate with these rules"}</span>
            </button>
          )}
        </div>

        {/* tabs */}
        <div className="flex items-center space-x-2 mb-4">
          {(
            [
              ["rules", "Rules", ListChecks],
              ["assignments", "Teacher assignments", UserCog],
              ["electives", "Open electives", Layers],
            ] as [Tab, string, typeof ListChecks][]
          ).map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-sm font-bold transition-colors border ${
                tab === key
                  ? "bg-[#00078b] text-white border-[#00078b] shadow-md"
                  : "bg-white text-[#00078b] border-[#00078b]/20 hover:bg-[#f6f6f6]"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </button>
          ))}
        </div>

        {flash && (
          <div
            className={`flex items-start space-x-2 text-sm rounded-xl px-4 py-3 mb-4 border font-medium ${
              flash.kind === "ok"
                ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                : "text-amber-700 bg-amber-50 border-amber-200"
            }`}
          >
            {flash.kind === "ok" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-600" />
            ) : (
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" />
            )}
            <span className="whitespace-pre-wrap">{flash.text}</span>
            <button onClick={() => setFlash(null)} className="ml-auto opacity-60 hover:opacity-100">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {!reg && (
          <div className={`${CARD} p-12 text-center`}>
            <RefreshCw className="h-6 w-6 text-[#00078b]/40 mx-auto mb-3 animate-spin" />
            <p className="text-[#00078b] font-semibold text-sm">Loading the rulebook…</p>
          </div>
        )}

        {/* ---------------- RULES ---------------- */}
        {reg && tab === "rules" && (
          <div className="space-y-4">
            {isAdmin && (
              <div className={`${CARD} p-5`}>
                <div className="flex items-center space-x-2 mb-2">
                  <Wand2 className="h-4 w-4 text-[#00078b]" />
                  <h2 className="text-sm font-bold text-[#00078b]">Ask for a change in plain English</h2>
                  {!reg.llm && (
                    <span className="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
                      no LLM key — simple phrasings only
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[#00078b]/70 mb-3 font-medium">
                  It proposes changes to the rules below — including editing or removing an existing one —
                  and nothing is saved until you confirm.
                </p>
                <div className="flex items-start space-x-2">
                  <textarea
                    rows={2}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="e.g. semester 5 should have at most 5 periods a day, and make Wednesday a half day ending at P4 for CSE-7A"
                    className="flex-1 bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] rounded-xl px-3 py-2 text-sm font-medium outline-none focus:border-[#00078b] resize-none"
                  />
                  <button onClick={askAi} disabled={thinking || !prompt.trim()} className={BTN_PRIMARY}>
                    {thinking ? (
                      <RefreshCw className="h-4 w-4 animate-spin text-[#fdb813]" />
                    ) : (
                      <Sparkles className="h-4 w-4 text-[#fdb813]" />
                    )}
                    <span>{thinking ? "Reading…" : "Propose"}</span>
                  </button>
                </div>

                {preview && (
                  <div className="mt-4 border-t border-[#00078b]/10 pt-4">
                    {notes && (
                      <p className="flex items-start space-x-2 text-[11px] text-[#00078b]/80 font-medium mb-3">
                        <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                        <span>{notes}</span>
                      </p>
                    )}
                    {preview.length === 0 && (
                      <p className="text-xs text-[#00078b]/60 font-semibold">No changes proposed.</p>
                    )}
                    <div className="space-y-2">
                      {preview.map((op, i) => (
                        <div
                          key={i}
                          className={`rounded-xl border px-3 py-2 ${
                            op.ok
                              ? "bg-[#f6f6f6] border-[#00078b]/15"
                              : "bg-amber-50 border-amber-200"
                          }`}
                        >
                          <div className="flex items-center space-x-2">
                            <span
                              className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${
                                op.op === "delete"
                                  ? "bg-rose-100 text-rose-700"
                                  : op.op === "update"
                                  ? "bg-amber-100 text-amber-800"
                                  : "bg-emerald-100 text-emerald-700"
                              }`}
                            >
                              {op.op}
                            </span>
                            <span className="text-xs font-bold text-[#00078b]">
                              {op.ok ? op.description : op.error}
                            </span>
                          </div>
                          {op.ok && op.before && op.op === "update" && (
                            <p className="text-[11px] text-[#00078b]/60 font-medium mt-1 pl-1">
                              was: {op.before}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                    {preview.some((o) => o.ok) && (
                      <div className="flex items-center space-x-2 mt-3">
                        <button onClick={applyAi} disabled={busy} className={BTN_PRIMARY}>
                          <Save className="h-4 w-4 text-[#fdb813]" />
                          <span>Apply {preview.filter((o) => o.ok).length} change(s)</span>
                        </button>
                        <button onClick={() => setPreview(null)} className={BTN_GHOST}>
                          <X className="h-3.5 w-3.5" />
                          <span>Discard</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* add / edit form */}
            {isAdmin && (
              <div className={`${CARD} p-5`}>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-bold text-[#00078b]">
                    {formOpen ? (editing ? "Edit constraint" : "Add a constraint") : "Add a constraint"}
                  </h2>
                  <button
                    onClick={() => (formOpen ? setFormOpen(false) : openAdd())}
                    className={BTN_GHOST}
                  >
                    {formOpen ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
                    <span>{formOpen ? "Close" : "New rule"}</span>
                  </button>
                </div>

                {formOpen && activeKind && (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <label className="flex items-center space-x-2">
                        <span className="text-[11px] font-bold text-[#00078b]/70">Rule</span>
                        <select
                          className={FIELD}
                          value={fKind}
                          disabled={!!editing}
                          onChange={(e) => {
                            const k = catalogByKind.get(e.target.value);
                            setFKind(e.target.value);
                            setFParams({});
                            if (k && !k.scopes.includes(fScopeType)) setFScopeType(k.scopes[0]);
                          }}
                        >
                          {reg.catalog.map((k) => (
                            <option key={k.kind} value={k.kind}>{k.label}</option>
                          ))}
                        </select>
                      </label>

                      <label className="flex items-center space-x-2">
                        <span className="text-[11px] font-bold text-[#00078b]/70">Applies to</span>
                        <select
                          className={FIELD}
                          value={fScopeType}
                          onChange={(e) => {
                            setFScopeType(e.target.value);
                            setFScopeValue("");
                          }}
                        >
                          {activeKind.scopes.map((s) => (
                            <option key={s} value={s}>
                              {s === "global" ? "All classes" : s === "semester" ? "One semester" : "One class"}
                            </option>
                          ))}
                        </select>
                      </label>

                      {fScopeType === "semester" && (
                        <select
                          className={FIELD}
                          value={fScopeValue}
                          onChange={(e) => setFScopeValue(e.target.value)}
                        >
                          <option value="">choose semester…</option>
                          {reg.context.semesters.map((s) => (
                            <option key={s} value={s}>Semester {s}</option>
                          ))}
                        </select>
                      )}
                      {fScopeType === "section" && (
                        <select
                          className={FIELD}
                          value={fScopeValue}
                          onChange={(e) => setFScopeValue(e.target.value)}
                        >
                          <option value="">choose class…</option>
                          {reg.context.sections.map((s) => (
                            <option key={s.id} value={s.name}>{s.name}</option>
                          ))}
                        </select>
                      )}
                    </div>

                    <p className="text-[11px] text-[#00078b]/70 font-medium">{activeKind.help}</p>

                    <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
                      {activeKind.fields.map((f) => (
                        <div key={f.name} className="flex items-center space-x-2">
                          <span className="text-[11px] font-bold text-[#00078b]/70">{f.label}</span>
                          {renderField(f)}
                        </div>
                      ))}
                    </div>

                    <button onClick={submitForm} disabled={busy} className={BTN_PRIMARY}>
                      <Save className="h-4 w-4 text-[#fdb813]" />
                      <span>{editing ? "Save changes" : "Add constraint"}</span>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* the rulebook */}
            {grouped.length === 0 && (
              <div className={`${CARD} p-10 text-center`}>
                <p className="text-[#00078b] font-semibold text-sm">No constraints yet.</p>
              </div>
            )}
            {grouped.map((g) => (
              <div key={g.key} className={`${CARD} overflow-hidden`}>
                <div className="px-5 py-3 bg-[#f6f6f6] border-b border-[#00078b]/10 flex items-center justify-between">
                  <h3 className="text-xs font-bold text-[#00078b] uppercase tracking-wider">{g.title}</h3>
                  <span className="text-[10px] text-[#00078b]/60 font-bold">{g.rows.length} rule(s)</span>
                </div>
                <div className="divide-y divide-[#00078b]/10">
                  {g.rows.map((row) => (
                    <div
                      key={row.id}
                      className={`flex items-start justify-between px-5 py-3 gap-3 ${
                        row.enabled ? "" : "opacity-50"
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center flex-wrap gap-2">
                          <span className="text-sm font-bold text-[#00078b]">{row.description}</span>
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#00078b]/10 text-[#00078b]">
                            {row.label}
                          </span>
                          {row.priority === "soft" && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-100 text-sky-700">
                              preference
                            </span>
                          )}
                          {row.source === "llm" && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
                              from a prompt
                            </span>
                          )}
                        </div>
                        {row.origin_prompt && (
                          <p className="text-[11px] text-[#00078b]/60 font-medium mt-1 italic truncate">
                            “{row.origin_prompt}”
                          </p>
                        )}
                      </div>
                      {isAdmin && (
                        <div className="flex items-center space-x-1.5 shrink-0">
                          <button
                            onClick={() => toggle(row)}
                            disabled={busy}
                            className={BTN_GHOST}
                            title={row.enabled ? "Turn off" : "Turn on"}
                          >
                            <span>{row.enabled ? "On" : "Off"}</span>
                          </button>
                          <button onClick={() => openEdit(row)} className={BTN_GHOST} title="Edit">
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => remove(row)}
                            disabled={busy}
                            className={`${BTN_GHOST} text-rose-700 border-rose-200 hover:bg-rose-50`}
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ---------------- ASSIGNMENTS ---------------- */}
        {reg && tab === "assignments" && (
          <div className="space-y-4">
            <div className={`${CARD} p-5`}>
              <h2 className="text-sm font-bold text-[#00078b] mb-1">Who teaches what, for which class</h2>
              <p className="text-[11px] text-[#00078b]/70 font-medium">
                A pinned teacher is honoured exactly by the solver. Leave a subject on{" "}
                <b>Auto</b> to let it pick any qualified teacher. The same teacher can be pinned in
                several semesters — clash-freedom and daily load are checked across all of them, so an
                impossible combination is reported instead of quietly reshuffled. Only teachers mapped
                to a subject (Data Setup → Teachers) appear in its list.
              </p>
              {Object.keys(assignDirty).length > 0 && isAdmin && (
                <button onClick={saveAssignments} disabled={busy} className={`${BTN_PRIMARY} mt-3`}>
                  <Save className="h-4 w-4 text-[#fdb813]" />
                  <span>Save {Object.keys(assignDirty).length} change(s)</span>
                </button>
              )}
            </div>

            {(assign ?? []).map((sec) => (
              <div key={sec.section_id} className={`${CARD} overflow-hidden`}>
                <div className="px-5 py-3 bg-[#f6f6f6] border-b border-[#00078b]/10">
                  <h3 className="text-xs font-bold text-[#00078b] uppercase tracking-wider">
                    {sec.section} · semester {sec.semester}
                  </h3>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#00078b]/10">
                      <th className="text-left text-[10px] text-[#00078b]/70 uppercase tracking-wider font-bold px-5 py-2">Subject</th>
                      <th className="text-left text-[10px] text-[#00078b]/70 uppercase tracking-wider font-bold px-3 py-2 w-24">Periods</th>
                      <th className="text-left text-[10px] text-[#00078b]/70 uppercase tracking-wider font-bold px-3 py-2 w-72">Teacher</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#00078b]/10">
                    {sec.subjects.map((s) => (
                      <tr key={s.subject_id}>
                        <td className="px-5 py-2">
                          <div className="text-sm font-bold text-[#00078b] font-mono">{s.subject_code}</div>
                          <div className="text-[11px] text-[#00078b]/60 font-medium">
                            {s.subject_name}{s.needs_lab ? " · lab" : ""}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-xs font-bold text-[#00078b]/70">{s.periods_per_week}/wk</td>
                        <td className="px-3 py-2">
                          {s.eligible.length === 0 ? (
                            <span className="text-[11px] font-semibold text-amber-700">
                              no teacher is mapped to this subject
                            </span>
                          ) : (
                            <select
                              className={`${FIELD} w-64`}
                              disabled={!isAdmin}
                              value={s.teacher_id ?? ""}
                              onChange={(e) =>
                                setPin(
                                  sec.section_id,
                                  s.subject_id,
                                  e.target.value === "" ? null : Number(e.target.value)
                                )
                              }
                            >
                              <option value="">Auto — solver picks</option>
                              {s.eligible.map((t) => (
                                <option key={t.id} value={t.id}>{t.name}</option>
                              ))}
                            </select>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}

        {/* ---------------- ELECTIVES ---------------- */}
        {reg && tab === "electives" && (
          <div className="space-y-4">
            <div className={`${CARD} p-5`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-bold text-[#00078b] mb-1">Open-elective bands</h2>
                  <p className="text-[11px] text-[#00078b]/70 font-medium max-w-3xl">
                    A band reserves the same periods for <b>every class of a semester</b> — the usual
                    sem 6/7 arrangement. Inside it the options run in parallel, so students split
                    across baskets; each option needs its own teacher and its own room. Rooms used by
                    a band are reserved for it and are not handed out as a class home room.
                  </p>
                </div>
                {isAdmin && (
                  <button onClick={() => setBandDraft(newBand())} className={BTN_GHOST}>
                    <Plus className="h-3.5 w-3.5" />
                    <span>New band</span>
                  </button>
                )}
              </div>
            </div>

            {(bands ?? []).map((b) => (
              <div key={b.id} className={`${CARD} overflow-hidden`}>
                <div className="px-5 py-3 bg-[#f6f6f6] border-b border-[#00078b]/10 flex items-center justify-between">
                  <h3 className="text-xs font-bold text-[#00078b] uppercase tracking-wider">
                    {b.name} · semester {b.semester} · {b.periods_per_week} period(s)/week
                    {b.needs_block ? " · consecutive block" : ""}
                    {b.active ? "" : " · inactive"}
                  </h3>
                  {isAdmin && (
                    <div className="flex items-center space-x-1.5">
                      <button onClick={() => setBandDraft({ ...b })} className={BTN_GHOST}>
                        <Pencil className="h-3.5 w-3.5" />
                        <span>Edit</span>
                      </button>
                      <button
                        onClick={() => deleteBand(b)}
                        disabled={busy}
                        className={`${BTN_GHOST} text-rose-700 border-rose-200 hover:bg-rose-50`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
                <div className="divide-y divide-[#00078b]/10">
                  {b.offerings.map((o) => (
                    <div key={o.id} className="px-5 py-2.5 flex items-center justify-between">
                      <div>
                        <span className="text-sm font-bold text-[#00078b] font-mono">{o.subject_code}</span>
                        <span className="text-[11px] text-[#00078b]/60 font-medium ml-2">{o.teacher}</span>
                      </div>
                      <span className="text-[11px] text-[#00078b]/60 font-semibold">
                        {o.room} · {o.capacity} seats
                      </span>
                    </div>
                  ))}
                  {b.offerings.length === 0 && (
                    <p className="px-5 py-3 text-[11px] text-amber-700 font-semibold">
                      No options yet — a band with no options is ignored by the solver.
                    </p>
                  )}
                </div>
              </div>
            ))}

            {bandDraft && (
              <div className={`${CARD} p-5 border-[#00078b]/40`}>
                <h3 className="text-sm font-bold text-[#00078b] mb-3">
                  {bandDraft.id ? `Edit ${bandDraft.name}` : "New elective band"}
                </h3>
                <div className="flex flex-wrap items-center gap-x-5 gap-y-3 mb-4">
                  <label className="flex items-center space-x-2">
                    <span className="text-[11px] font-bold text-[#00078b]/70">Name</span>
                    <input
                      className={`${FIELD} w-28`}
                      value={bandDraft.name}
                      onChange={(e) => setBandDraft({ ...bandDraft, name: e.target.value })}
                    />
                  </label>
                  <label className="flex items-center space-x-2">
                    <span className="text-[11px] font-bold text-[#00078b]/70">Semester</span>
                    <select
                      className={FIELD}
                      value={bandDraft.semester}
                      onChange={(e) => setBandDraft({ ...bandDraft, semester: Number(e.target.value) })}
                    >
                      {reg.context.semesters.map((s) => (
                        <option key={s} value={s}>Semester {s}</option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center space-x-2">
                    <span className="text-[11px] font-bold text-[#00078b]/70">Periods / week</span>
                    <input
                      type="number"
                      min={1}
                      max={8}
                      className={`${FIELD} w-16`}
                      value={bandDraft.periods_per_week}
                      onChange={(e) =>
                        setBandDraft({ ...bandDraft, periods_per_week: Number(e.target.value) })
                      }
                    />
                  </label>
                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      className="accent-[#00078b]"
                      checked={bandDraft.needs_block}
                      onChange={(e) => setBandDraft({ ...bandDraft, needs_block: e.target.checked })}
                    />
                    <span className="text-xs font-bold text-[#00078b]">Needs a consecutive block</span>
                  </label>
                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      className="accent-[#00078b]"
                      checked={bandDraft.active}
                      onChange={(e) => setBandDraft({ ...bandDraft, active: e.target.checked })}
                    />
                    <span className="text-xs font-bold text-[#00078b]">Active</span>
                  </label>
                </div>

                <p className="text-[11px] font-bold text-[#00078b] mb-2">Parallel options</p>
                <div className="space-y-2 mb-3">
                  {bandDraft.offerings.map((o, i) => (
                    <div key={i} className="flex flex-wrap items-center gap-2">
                      <select
                        className={`${FIELD} w-56`}
                        value={o.subject_id || ""}
                        onChange={(e) => {
                          const next = [...bandDraft.offerings];
                          next[i] = { ...o, subject_id: Number(e.target.value) };
                          setBandDraft({ ...bandDraft, offerings: next });
                        }}
                      >
                        <option value="">subject…</option>
                        {reg.context.subjects.map((s) => (
                          <option key={s.id} value={s.id}>{s.code} — {s.name}</option>
                        ))}
                      </select>
                      <select
                        className={`${FIELD} w-48`}
                        value={o.teacher_id || ""}
                        onChange={(e) => {
                          const next = [...bandDraft.offerings];
                          next[i] = { ...o, teacher_id: Number(e.target.value) };
                          setBandDraft({ ...bandDraft, offerings: next });
                        }}
                      >
                        <option value="">teacher…</option>
                        {reg.context.teachers.map((t) => (
                          <option key={t.id} value={t.id}>{t.name}</option>
                        ))}
                      </select>
                      <select
                        className={`${FIELD} w-44`}
                        value={o.room_id || ""}
                        onChange={(e) => {
                          const next = [...bandDraft.offerings];
                          next[i] = { ...o, room_id: Number(e.target.value) };
                          setBandDraft({ ...bandDraft, offerings: next });
                        }}
                      >
                        <option value="">room…</option>
                        {rooms.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name} ({r.type}, {r.capacity})
                          </option>
                        ))}
                      </select>
                      <input
                        type="number"
                        min={1}
                        className={`${FIELD} w-20`}
                        value={o.capacity}
                        onChange={(e) => {
                          const next = [...bandDraft.offerings];
                          next[i] = { ...o, capacity: Number(e.target.value) };
                          setBandDraft({ ...bandDraft, offerings: next });
                        }}
                      />
                      <button
                        onClick={() =>
                          setBandDraft({
                            ...bandDraft,
                            offerings: bandDraft.offerings.filter((_, j) => j !== i),
                          })
                        }
                        className={`${BTN_GHOST} text-rose-700 border-rose-200 hover:bg-rose-50`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() =>
                      setBandDraft({
                        ...bandDraft,
                        offerings: [
                          ...bandDraft.offerings,
                          { subject_id: 0, teacher_id: 0, room_id: 0, capacity: 60 },
                        ],
                      })
                    }
                    className={BTN_GHOST}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Add option</span>
                  </button>
                  <button onClick={saveBand} disabled={busy} className={BTN_PRIMARY}>
                    <Save className="h-4 w-4 text-[#fdb813]" />
                    <span>Save band</span>
                  </button>
                  <button onClick={() => setBandDraft(null)} className={BTN_GHOST}>
                    <X className="h-3.5 w-3.5" />
                    <span>Cancel</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
