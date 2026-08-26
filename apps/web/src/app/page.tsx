"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { getToken, getUser, clearAuth, AuthUser } from "../lib/api";
import {
  LayoutDashboard,
  MessageSquare,
  CalendarDays,
  Building2,
  Send,
  Bot,
  User,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
  Zap,
  Database,
  LogIn,
  LogOut,
  CalendarX,
  ClipboardCheck,
  ArrowLeftRight,
  Inbox,
} from "lucide-react";

import AppLayout from "../components/AppLayout";

// Types
interface Message {
  sender: "user" | "agent";
  agentName?: string;
  text: string;
  timestamp: string;
  steps?: string[];
}

interface Task {
  id: string;
  name: string;
  trigger: string;
  status: "idle" | "running" | "completed" | "failed";
  lastRun: string;
}

interface Facility {
  id: string;
  name: string;
  type: string;
  status: "Available" | "Occupied" | "Reserved";
  currentReservation?: string;
  capacity: number;
}

export default function Dashboard() {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const [activeTab, setActiveTab] = useState<"overview" | "chat" | "scheduler" | "facilities">("overview");
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "agent",
      agentName: "Campus Router",
      text: "Hello! I am the Smart Campus Agent Orchestrator. How can I help you manage the campus operations today?",
      timestamp: "17:00",
    },
  ]);
  const [inputVal, setInputVal] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [activeWorkflowSteps, setActiveWorkflowSteps] = useState<string[]>([]);
  const [backendConnected, setBackendConnected] = useState(false);

  // Check auth on mount
  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setCurrentUser(getUser());
    setAuthChecked(true);
  }, [router]);

  // Scheduler State
  const [tasks, setTasks] = useState<Task[]>([
    { id: "1", name: "Daily Timetable Synchronization", trigger: "Every day at 06:00", status: "completed", lastRun: "Today, 06:00" },
    { id: "2", name: "Faculty Substitution Auto-Solver", trigger: "On Leave Approval", status: "running", lastRun: "Today, 17:00" },
    { id: "3", name: "Room Allocation & Facility Check", trigger: "Every day at 08:00", status: "idle", lastRun: "Today, 08:00" },
    { id: "4", name: "Daily Attendance & Leave Backup", trigger: "Every day at 22:00", status: "idle", lastRun: "Yesterday, 22:00" },
  ]);
  const [showNewTaskModal, setShowNewTaskModal] = useState(false);
  const [newTaskName, setNewTaskName] = useState("");
  const [newTaskTrigger, setNewTaskTrigger] = useState("");

  // Facility State
  const [facilities, setFacilities] = useState<Facility[]>([
    { id: "F1", name: "Main Seminar Hall", type: "Conference Room", status: "Reserved", currentReservation: "Tech Symposium (14:00 - 18:00)", capacity: 250 },
    { id: "F2", name: "Advanced Robotics Lab", type: "Laboratory", status: "Occupied", currentReservation: "Robotics Research Group", capacity: 40 },
    { id: "F3", name: "Lecture Theater 302", type: "Classroom", status: "Available", capacity: 120 },
    { id: "F4", name: "Computer Center B", type: "Laboratory", status: "Available", capacity: 60 },
    { id: "F5", name: "MBA Seminar Hall", type: "Conference Room", status: "Available", capacity: 150 },
  ]);
  const [showNewBookingModal, setShowNewBookingModal] = useState(false);
  const [selectedFacilityId, setSelectedFacilityId] = useState("");
  const [bookingDetails, setBookingDetails] = useState("");

  const chatEndRef = useRef<HTMLDivElement>(null);


  // Check backend health on mount
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/health");
        if (res.ok) setBackendConnected(true);
      } catch (err) {
        setBackendConnected(false);
      }
    };
    checkBackend();
    const interval = setInterval(checkBackend, 10000);
    return () => clearInterval(interval);
  }, []);

  // Auto scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Handle Send Message to Backend/Mock Agent
  const handleSendMessage = async () => {
    if (!inputVal.trim()) return;

    const userMsg = inputVal;
    setInputVal("");

    // Add user message
    setMessages((prev) => [
      ...prev,
      { sender: "user", text: userMsg, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
    ]);

    setIsTyping(true);
    setActiveWorkflowSteps(["RouterNode: Analyzing intent..."]);

    // If backend is connected, perform actual request, else fallback to mock simulation
    if (backendConnected) {
      try {
        // Send the bearer token: the Booking Agent needs to know who is asking
        // before it can hold a venue in their name (Phase 3, F3).
        const token = getToken();
        const response = await fetch("http://localhost:8000/api/agent/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ message: userMsg }),
        });
        const data = await response.json();

        setActiveWorkflowSteps(data.steps || ["RouterNode", "Completed"]);

        setTimeout(() => {
          setMessages((prev) => [
            ...prev,
            {
              sender: "agent",
              agentName: data.agent || "Campus Agent",
              text: data.response || "I processed your request, but empty response returned.",
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              steps: data.steps,
            },
          ]);
          setIsTyping(false);
        }, 1200);
      } catch (err) {
        setBackendConnected(false);
        simulateMockResponse(userMsg);
      }
    } else {
      simulateMockResponse(userMsg);
    }
  };

  const simulateMockResponse = (userMsg: string) => {
    const msgLower = userMsg.toLowerCase();
    let responseText = "I've received your query but since my backend services are not running, I'm running in demo mode. Please launch the FastAPI backend to use full LangGraph orchestrations!";
    let responseAgent = "Demo Router";
    let workflowSteps = ["RouterNode: Identifying intent..."];

    if (msgLower.includes("book") || msgLower.includes("reserve") || msgLower.includes("facility")) {
      responseAgent = "Facility Agent";
      workflowSteps = [
        "RouterNode: Routing to Facility Agent...",
        "FacilityAgent: Checking room availability...",
        "FacilityAgent: Processing mock reservation..."
      ];
      responseText = "I see you want to reserve a facility. In demo mode, I can help mock book room space. For example, Lecture Theater 302 has been marked as reserved for you!";

      // Reserve LT 302 mock
      setFacilities(prev => prev.map(f => f.id === 'F3' ? { ...f, status: 'Reserved', currentReservation: 'Ad-hoc Reservation (Requested by Admin)' } : f));
    } else if (msgLower.includes("schedule") || msgLower.includes("task") || msgLower.includes("timetable")) {
      responseAgent = "Scheduler Agent";
      workflowSteps = [
        "RouterNode: Routing to Scheduler Agent...",
        "SchedulerAgent: Scanning daily timetables...",
        "SchedulerAgent: Executing dynamic calendar adjustment..."
      ];
      responseText = "Understood. The Scheduler Agent has checked the current classroom occupancy. There are no timetable overlaps for the requested schedule.";
    }

    setTimeout(() => {
      setActiveWorkflowSteps(workflowSteps);
    }, 400);

    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          sender: "agent",
          agentName: responseAgent,
          text: responseText,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          steps: workflowSteps,
        },
      ]);
      setIsTyping(false);
    }, 1800);
  };

  const handleAddNewTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskName.trim() || !newTaskTrigger.trim()) return;
    const newTask: Task = {
      id: Date.now().toString(),
      name: newTaskName,
      trigger: newTaskTrigger,
      status: "idle",
      lastRun: "Never",
    };
    setTasks([...tasks, newTask]);
    setNewTaskName("");
    setNewTaskTrigger("");
    setShowNewTaskModal(false);
  };

  const triggerTaskRun = (id: string) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, status: "running" } : t));
    setTimeout(() => {
      setTasks(prev => prev.map(t => t.id === id ? { ...t, status: "completed", lastRun: "Just now" } : t));
    }, 2000);
  };

  const handleCreateBooking = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFacilityId || !bookingDetails.trim()) return;
    setFacilities(prev => prev.map(f => f.id === selectedFacilityId ? { ...f, status: "Reserved", currentReservation: bookingDetails } : f));
    setShowNewBookingModal(false);
    setBookingDetails("");
    setSelectedFacilityId("");
  };

  return (
    <AppLayout activeHomeTab={activeTab} onSelectHomeTab={setActiveTab}>
      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && (
            <div className="space-y-8 animate-fadeIn">

              {/* Stat Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-white border border-[#00078b]/15 p-6 rounded-2xl relative overflow-hidden shadow-sm hover:border-[#fdb813] transition-all">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-[#00078b]/60">Active Modules</p>
                      <h3 className="text-3xl font-extrabold mt-2 text-[#00078b]">4 Core</h3>
                    </div>
                    <span className="bg-[#00078b] p-2.5 rounded-xl text-[#fdb813] shadow-md">
                      <LayoutDashboard className="h-5 w-5" />
                    </span>
                  </div>
                  <p className="text-[11px] text-[#00078b]/70 mt-4 flex items-center space-x-1.5 font-medium">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
                    <span>Timetable, Leaves, Facilities, Swaps</span>
                  </p>
                </div>

                <div className="bg-white border border-[#00078b]/15 p-6 rounded-2xl relative overflow-hidden shadow-sm hover:border-[#fdb813] transition-all">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-[#00078b]/60">Scheduled Tasks</p>
                      <h3 className="text-3xl font-extrabold mt-2 text-[#00078b]">{tasks.length} Active</h3>
                    </div>
                    <span className="bg-emerald-500/10 p-2.5 rounded-xl border border-emerald-500/20 text-emerald-700">
                      <CalendarDays className="h-5 w-5" />
                    </span>
                  </div>
                  <p className="text-[11px] text-emerald-700 mt-4 font-bold">
                    1 running currently
                  </p>
                </div>

                <div className="bg-white border border-[#00078b]/15 p-6 rounded-2xl relative overflow-hidden shadow-sm hover:border-[#fdb813] transition-all">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-[#00078b]/60">Facility Occupancy</p>
                      <h3 className="text-3xl font-extrabold mt-2 text-[#00078b]">
                        {facilities.filter(f => f.status === "Reserved" || f.status === "Occupied").length} / {facilities.length}
                      </h3>
                    </div>
                    <span className="bg-amber-500/10 p-2.5 rounded-xl border border-amber-500/20 text-amber-700">
                      <Building2 className="h-5 w-5" />
                    </span>
                  </div>
                  <p className="text-[11px] text-[#00078b]/70 mt-4 font-medium">
                    Rooms allocated for today
                  </p>
                </div>

                <div className="bg-white border border-[#00078b]/15 p-6 rounded-2xl relative overflow-hidden shadow-sm hover:border-[#fdb813] transition-all">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-[#00078b]/60">Academic Solver</p>
                      <h3 className="text-3xl font-extrabold mt-2 text-[#00078b]">Clash-Free</h3>
                    </div>
                    <span className="bg-[#00078b] p-2.5 rounded-xl text-[#fdb813] shadow-md">
                      <CheckCircle2 className="h-5 w-5" />
                    </span>
                  </div>
                  <p className="text-[11px] text-[#00078b]/70 mt-4 font-medium">
                    OR-Tools CP-SAT Active
                  </p>
                </div>
              </div>

              {/* Dynamic Operations Overview Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* Quick Launch & Operational Modules */}
                <div className="lg:col-span-2 bg-white border border-[#00078b]/15 p-6 rounded-2xl flex flex-col shadow-sm">
                  <div className="flex items-center justify-between mb-5">
                    <h4 className="font-bold text-sm uppercase tracking-wider text-[#00078b]">
                      Operational Hub &amp; Quick Access
                    </h4>
                    <span className="text-xs bg-[#fdb813] text-[#00078b] px-2.5 py-0.5 rounded-md font-bold">
                      Campus Portal
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 flex-1">
                    <a
                      href="/setup"
                      className="p-4 rounded-xl border border-[#00078b]/15 bg-[#f6f6f6] hover:bg-[#00078b]/5 hover:border-[#00078b] transition-all group flex flex-col justify-between"
                    >
                      <div className="bg-[#00078b] p-2.5 rounded-xl text-[#fdb813] w-fit mb-3 shadow-sm group-hover:scale-105 transition-transform">
                        <Database className="h-5 w-5" />
                      </div>
                      <div>
                        <h5 className="font-bold text-sm text-[#00078b] group-hover:text-[#00078b]">Data Setup</h5>
                        <p className="text-[11px] text-[#00078b]/70 font-medium mt-1">Subjects, Teachers, Sections &amp; Rooms</p>
                      </div>
                    </a>

                    <a
                      href="/timetable"
                      className="p-4 rounded-xl border border-[#00078b]/15 bg-[#f6f6f6] hover:bg-[#00078b]/5 hover:border-[#00078b] transition-all group flex flex-col justify-between"
                    >
                      <div className="bg-[#00078b] p-2.5 rounded-xl text-[#fdb813] w-fit mb-3 shadow-sm group-hover:scale-105 transition-transform">
                        <CalendarDays className="h-5 w-5" />
                      </div>
                      <div>
                        <h5 className="font-bold text-sm text-[#00078b] group-hover:text-[#00078b]">Timetable</h5>
                        <p className="text-[11px] text-[#00078b]/70 font-medium mt-1">Class Schedules &amp; PDF Export</p>
                      </div>
                    </a>

                    <a
                      href="/leaves"
                      className="p-4 rounded-xl border border-[#00078b]/15 bg-[#f6f6f6] hover:bg-[#00078b]/5 hover:border-[#00078b] transition-all group flex flex-col justify-between"
                    >
                      <div className="bg-[#00078b] p-2.5 rounded-xl text-[#fdb813] w-fit mb-3 shadow-sm group-hover:scale-105 transition-transform">
                        <CalendarX className="h-5 w-5" />
                      </div>
                      <div>
                        <h5 className="font-bold text-sm text-[#00078b] group-hover:text-[#00078b]">Leave Portal</h5>
                        <p className="text-[11px] text-[#00078b]/70 font-medium mt-1">Apply &amp; Approve Faculty Leaves</p>
                      </div>
                    </a>

                    <a
                      href="/approvals"
                      className="p-4 rounded-xl border border-[#00078b]/15 bg-[#f6f6f6] hover:bg-[#00078b]/5 hover:border-[#00078b] transition-all group flex flex-col justify-between"
                    >
                      <div className="bg-[#00078b] p-2.5 rounded-xl text-[#fdb813] w-fit mb-3 shadow-sm group-hover:scale-105 transition-transform">
                        <ClipboardCheck className="h-5 w-5" />
                      </div>
                      <div>
                        <h5 className="font-bold text-sm text-[#00078b] group-hover:text-[#00078b]">Approvals</h5>
                        <p className="text-[11px] text-[#00078b]/70 font-medium mt-1">Review Substitution Plans</p>
                      </div>
                    </a>

                    <a
                      href="/exchanges"
                      className="p-4 rounded-xl border border-[#00078b]/15 bg-[#f6f6f6] hover:bg-[#00078b]/5 hover:border-[#00078b] transition-all group flex flex-col justify-between"
                    >
                      <div className="bg-[#00078b] p-2.5 rounded-xl text-[#fdb813] w-fit mb-3 shadow-sm group-hover:scale-105 transition-transform">
                        <ArrowLeftRight className="h-5 w-5" />
                      </div>
                      <div>
                        <h5 className="font-bold text-sm text-[#00078b] group-hover:text-[#00078b]">Exchanges</h5>
                        <p className="text-[11px] text-[#00078b]/70 font-medium mt-1">Period Swaps &amp; Daily Schedule</p>
                      </div>
                    </a>

                    <a
                      href="/inbox"
                      className="p-4 rounded-xl border border-[#00078b]/15 bg-[#f6f6f6] hover:bg-[#00078b]/5 hover:border-[#00078b] transition-all group flex flex-col justify-between"
                    >
                      <div className="bg-[#00078b] p-2.5 rounded-xl text-[#fdb813] w-fit mb-3 shadow-sm group-hover:scale-105 transition-transform">
                        <Inbox className="h-5 w-5" />
                      </div>
                      <div>
                        <h5 className="font-bold text-sm text-[#00078b] group-hover:text-[#00078b]">Campus Inbox</h5>
                        <p className="text-[11px] text-[#00078b]/70 font-medium mt-1">Notifications &amp; Activity Log</p>
                      </div>
                    </a>
                  </div>
                </div>

                {/* Operations Summary */}
                <div className="bg-white border border-[#00078b]/15 p-6 rounded-2xl flex flex-col shadow-sm">
                  <h4 className="font-bold text-sm uppercase tracking-wider text-[#00078b] mb-4">
                    Automated Task Queue
                  </h4>
                  <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                    {tasks.map(task => (
                      <div key={task.id} className="p-3 bg-[#f6f6f6] border border-[#00078b]/10 rounded-xl flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-[#00078b]">{task.name}</p>
                          <p className="text-[10px] text-[#00078b]/60 font-medium mt-0.5">{task.trigger}</p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className={`h-2 w-2 rounded-full ${task.status === "running" ? "bg-[#00078b] animate-ping" :
                              task.status === "completed" ? "bg-emerald-500" : "bg-[#00078b]/30"
                            }`}></span>
                          <span className="text-[10px] font-bold uppercase text-[#00078b]">{task.status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={() => setActiveTab("scheduler")}
                    className="w-full mt-4 bg-[#00078b] hover:bg-[#000566] text-white font-bold py-2.5 rounded-xl text-xs transition duration-200 shadow-md"
                  >
                    Manage Task Scheduler
                  </button>
                </div>

              </div>

            </div>
          )}

          {/* TAB 2: AGENT CHAT */}
          {activeTab === "chat" && (
            <div className="h-[calc(100vh-14rem)] flex gap-8 animate-fadeIn">

              {/* Chat Thread */}
              <div className="flex-1 bg-white border border-[#00078b]/15 rounded-2xl flex flex-col overflow-hidden relative shadow-sm">

                {/* Chat Header */}
                <div className="px-6 py-4 border-b border-[#00078b]/15 bg-[#f6f6f6] flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="h-10 w-10 bg-[#00078b] text-[#fdb813] rounded-xl flex items-center justify-center shadow-sm font-bold">
                      <Bot className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-[#00078b]">Campus Orchestrator Agent</h4>
                      <p className="text-[11px] text-[#00078b]/70 font-semibold">Active Node State Listener</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-1 bg-emerald-50 border border-emerald-200 text-emerald-700 px-2.5 py-1 rounded-md text-[10px] font-bold">
                    <span className="h-1.5 w-1.5 bg-emerald-500 rounded-full"></span>
                    <span>LangGraph Mode</span>
                  </div>
                </div>

                {/* Messages Box */}
                <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-[#f8fbfe]">
                  {messages.map((msg, index) => (
                    <div
                      key={index}
                      className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"} items-start gap-3`}
                    >
                      {msg.sender === "agent" && (
                        <div className="h-8 w-8 rounded-lg bg-[#00078b] text-[#fdb813] flex items-center justify-center shrink-0 text-xs font-bold shadow-sm">
                          <Bot className="h-4 w-4" />
                        </div>
                      )}
                      <div className="max-w-[70%]">
                        <div
                          className={`p-4 rounded-2xl text-sm leading-relaxed border ${msg.sender === "user"
                              ? "bg-[#00078b] border-[#00078b] text-white rounded-tr-none shadow-sm font-medium"
                              : "bg-white border-[#00078b]/15 text-[#00078b] rounded-tl-none shadow-sm"
                            }`}
                        >
                          {msg.sender === "agent" && msg.agentName && (
                            <span className="text-[10px] block font-extrabold text-[#00078b] uppercase tracking-wider mb-1">
                              {msg.agentName}
                            </span>
                          )}
                          <p>{msg.text}</p>
                        </div>
                        <span className="text-[10px] text-[#00078b]/60 font-semibold mt-1 block px-2">
                          {msg.timestamp}
                        </span>
                      </div>
                    </div>
                  ))}

                  {isTyping && (
                    <div className="flex justify-start items-center gap-3">
                      <div className="h-8 w-8 rounded-lg bg-[#00078b] text-[#fdb813] flex items-center justify-center shrink-0">
                        <Bot className="h-4 w-4 animate-spin text-[#fdb813]" />
                      </div>
                      <div className="bg-white border border-[#00078b]/15 px-4 py-3 rounded-2xl text-xs text-[#00078b] flex items-center space-x-2 font-medium shadow-sm">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin text-[#00078b]" />
                        <span>LangGraph executing nodes...</span>
                      </div>
                    </div>
                  )}

                  <div ref={chatEndRef} />
                </div>

                {/* Input form */}
                <div className="p-4 border-t border-[#00078b]/15 bg-white flex items-center space-x-2">
                  <input
                    type="text"
                    value={inputVal}
                    onChange={(e) => setInputVal(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                    placeholder="Ask agent: 'Book Room 302 tomorrow' or 'List current scheduling issues'"
                    className="flex-1 bg-[#f6f6f6] border border-[#00078b]/20 px-4 py-3 rounded-xl text-sm text-[#00078b] placeholder-[#00078b]/40 focus:border-[#00078b] focus:ring-2 focus:ring-[#00078b]/20 outline-none font-medium transition-all"
                  />
                  <button
                    onClick={handleSendMessage}
                    className="bg-[#00078b] hover:bg-[#000566] text-white p-3 rounded-xl transition duration-150 shadow-md font-bold"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                </div>

              </div>

              {/* Steps/Trace Sidebar */}
              <div className="w-80 bg-white border border-[#00078b]/15 rounded-2xl p-6 flex flex-col h-full shadow-sm">
                <h4 className="font-bold text-sm uppercase tracking-wider text-[#00078b] mb-4 flex items-center space-x-2">
                  <Zap className="h-4 w-4 text-[#00078b]" />
                  <span>Agent Run Log</span>
                </h4>

                <div className="flex-1 bg-[#f6f6f6] rounded-xl border border-[#00078b]/10 p-4 overflow-y-auto space-y-4">
                  {activeWorkflowSteps.length === 0 ? (
                    <div className="text-center py-12 text-[#00078b]/60 text-xs font-medium">
                      <Clock className="h-8 w-8 mx-auto mb-2 text-[#00078b]" />
                      No active workflow runtime trace. Ask the agent a question to view real-time state routing.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-[11px] font-extrabold text-[#00078b] uppercase tracking-widest">Active State Nodes</p>
                      {activeWorkflowSteps.map((step, idx) => (
                        <div key={idx} className="flex items-start space-x-2 text-xs border-l-2 border-[#00078b] pl-3 py-1">
                          <div>
                            <p className="font-bold text-[#00078b]">{step.split(":")[0]}</p>
                            {step.split(":")[1] && (
                              <p className="text-[10px] text-[#00078b]/70 font-medium mt-0.5">{step.split(":")[1]}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="mt-4 text-[11px] text-[#00078b]/70 font-medium leading-normal">
                  LangGraph maintains a central state. During execution, nodes like the Router node route query payload, updating the central state variables asynchronously.
                </div>
              </div>

            </div>
          )}

          {/* TAB 3: SCHEDULER */}
          {activeTab === "scheduler" && (
            <div className="space-y-6 animate-fadeIn">

              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-lg font-bold text-[#00078b]">Scheduled Operational Scripts</h3>
                  <p className="text-xs text-[#00078b]/70 font-medium mt-0.5">Autonomous routines executed by the Scheduler Agent node</p>
                </div>
                <button
                  onClick={() => setShowNewTaskModal(true)}
                  className="bg-[#00078b] hover:bg-[#000566] text-white font-bold px-4 py-2.5 rounded-xl text-xs flex items-center space-x-2 transition duration-150 shadow-md"
                >
                  <Plus className="h-4 w-4" />
                  <span>Schedule Task</span>
                </button>
              </div>

              {/* Grid of Tasks */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {tasks.map(task => (
                  <div key={task.id} className="bg-white p-6 rounded-2xl flex flex-col justify-between border border-[#00078b]/15 shadow-sm hover:border-[#fdb813] transition-all">
                    <div>
                      <div className="flex justify-between items-start">
                        <h4 className="font-bold text-[#00078b] text-sm">{task.name}</h4>
                        <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold uppercase ${task.status === "completed" ? "bg-emerald-50 border border-emerald-200 text-emerald-700" :
                            task.status === "running" ? "bg-[#fdb813] text-[#00078b] font-bold animate-pulse" :
                              "bg-[#f6f6f6] border border-[#00078b]/15 text-[#00078b]"
                          }`}>
                          {task.status}
                        </span>
                      </div>
                      <p className="text-xs text-[#00078b]/70 font-medium mt-2 flex items-center space-x-1.5">
                        <Clock className="h-3.5 w-3.5 text-[#00078b]" />
                        <span>Trigger: <strong className="text-[#00078b]">{task.trigger}</strong></span>
                      </p>
                    </div>

                    <div className="mt-6 pt-4 border-t border-[#00078b]/10 flex justify-between items-center text-xs text-[#00078b]/60 font-semibold">
                      <span>Last executed: {task.lastRun}</span>
                      <button
                        onClick={() => triggerTaskRun(task.id)}
                        disabled={task.status === "running"}
                        className="bg-[#00078b] hover:bg-[#000566] text-white px-3 py-1.5 rounded-lg font-bold flex items-center space-x-1 transition disabled:opacity-40 shadow-sm"
                      >
                        <Play className="h-3 w-3 text-[#fdb813]" />
                        <span>Execute Now</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Create Task Modal */}
              {showNewTaskModal && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                  <div className="bg-white w-full max-w-md p-6 rounded-2xl border border-[#00078b]/20 shadow-2xl">
                    <h3 className="text-base font-bold text-[#00078b] mb-4">Schedule New Campus Automation</h3>
                    <form onSubmit={handleAddNewTask} className="space-y-4">
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-[#00078b] mb-1">Automation Task Name</label>
                        <input
                          type="text"
                          required
                          value={newTaskName}
                          onChange={(e) => setNewTaskName(e.target.value)}
                          placeholder="e.g. Server Backup, Faculty Timetable Audit"
                          className="w-full bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] px-3.5 py-2.5 rounded-xl text-sm focus:border-[#00078b] outline-none font-medium"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-[#00078b] mb-1">Trigger (Cron / Interval)</label>
                        <input
                          type="text"
                          required
                          value={newTaskTrigger}
                          onChange={(e) => setNewTaskTrigger(e.target.value)}
                          placeholder="e.g. Every day at 04:00, Every 2 hours"
                          className="w-full bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] px-3.5 py-2.5 rounded-xl text-sm focus:border-[#00078b] outline-none font-medium"
                        />
                      </div>
                      <div className="flex justify-end space-x-3 pt-4 border-t border-[#00078b]/10">
                        <button
                          type="button"
                          onClick={() => setShowNewTaskModal(false)}
                          className="text-xs text-[#00078b]/60 hover:text-[#00078b] font-bold px-3 py-2"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="bg-[#00078b] hover:bg-[#000566] text-white font-bold px-4 py-2 rounded-xl text-xs shadow-md"
                        >
                          Schedule
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}

            </div>
          )}

          {/* TAB 4: FACILITIES */}
          {activeTab === "facilities" && (
            <div className="space-y-6 animate-fadeIn">

              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-lg font-bold text-[#00078b]">Campus Facilities Control</h3>
                  <p className="text-xs text-[#00078b]/70 font-medium mt-0.5">Real-time room occupancy and automated allocation tracking</p>
                </div>
                <button
                  onClick={() => setShowNewBookingModal(true)}
                  className="bg-[#00078b] hover:bg-[#000566] text-white font-bold px-4 py-2.5 rounded-xl text-xs flex items-center space-x-2 transition duration-150 shadow-md"
                >
                  <Plus className="h-4 w-4" />
                  <span>Request Booking</span>
                </button>
              </div>

              {/* Facility Table */}
              <div className="bg-white rounded-2xl overflow-hidden border border-[#00078b]/15 shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-[#f6f6f6] border-b border-[#00078b]/15 text-[#00078b] text-xs font-bold uppercase tracking-wider">
                        <th className="p-4 pl-6">Room / Lab</th>
                        <th className="p-4">Type</th>
                        <th className="p-4">Capacity</th>
                        <th className="p-4">Status</th>
                        <th className="p-4 pr-6">Current Reservation / User</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#00078b]/10 text-sm">
                      {facilities.map(facility => (
                        <tr key={facility.id} className="hover:bg-[#f6f6f6]/60 transition">
                          <td className="p-4 pl-6 font-bold text-[#00078b]">{facility.name}</td>
                          <td className="p-4 text-[#00078b]/70 font-medium">{facility.type}</td>
                          <td className="p-4 text-[#00078b]/70 font-medium">{facility.capacity} seats</td>
                          <td className="p-4">
                            <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold uppercase ${facility.status === "Available" ? "bg-emerald-50 border border-emerald-200 text-emerald-700" :
                                facility.status === "Occupied" ? "bg-[#00078b] text-white" :
                                  "bg-[#fdb813] text-[#00078b]"
                              }`}>
                              {facility.status}
                            </span>
                          </td>
                          <td className="p-4 pr-6 text-xs text-[#00078b] font-semibold">
                            {facility.currentReservation || <span className="text-[#00078b]/40 italic font-normal">None (Ready for Booking)</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Booking Modal */}
              {showNewBookingModal && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                  <div className="bg-white w-full max-w-md p-6 rounded-2xl border border-[#00078b]/20 shadow-2xl">
                    <h3 className="text-base font-bold text-[#00078b] mb-4">Request Facility Booking</h3>
                    <form onSubmit={handleCreateBooking} className="space-y-4">
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-[#00078b] mb-1">Select Room</label>
                        <select
                          required
                          value={selectedFacilityId}
                          onChange={(e) => setSelectedFacilityId(e.target.value)}
                          className="w-full bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] px-3.5 py-2.5 rounded-xl text-sm focus:border-[#00078b] outline-none font-medium"
                        >
                          <option value="">-- Choose Classroom/Lab --</option>
                          {facilities.map(f => (
                            <option key={f.id} value={f.id} disabled={f.status !== "Available"}>
                              {f.name} ({f.status})
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-[#00078b] mb-1">Reservation / Event Details</label>
                        <input
                          type="text"
                          required
                          value={bookingDetails}
                          onChange={(e) => setBookingDetails(e.target.value)}
                          placeholder="e.g. Operating Systems Lecture (10:00 - 12:00)"
                          className="w-full bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] px-3.5 py-2.5 rounded-xl text-sm focus:border-[#00078b] outline-none font-medium"
                        />
                      </div>
                      <div className="flex justify-end space-x-3 pt-4 border-t border-[#00078b]/10">
                        <button
                          type="button"
                          onClick={() => {
                            setShowNewBookingModal(false);
                            setSelectedFacilityId("");
                            setBookingDetails("");
                          }}
                          className="text-xs text-[#00078b]/60 hover:text-[#00078b] font-bold px-3 py-2"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="bg-[#00078b] hover:bg-[#000566] text-white font-bold px-4 py-2 rounded-xl text-xs shadow-md"
                        >
                          Confirm Booking
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}

            </div>
          )}

    </AppLayout>
  );
}
