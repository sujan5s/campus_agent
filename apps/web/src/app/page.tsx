"use client";

import React, { useState, useEffect, useRef } from "react";
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
  CalendarX,
  ClipboardCheck,
  ArrowLeftRight,
  Inbox,
} from "lucide-react";

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

  // Scheduler State
  const [tasks, setTasks] = useState<Task[]>([
    { id: "1", name: "Daily Timetable Synchronization", trigger: "Every day at 06:00", status: "completed", lastRun: "Today, 06:00" },
    { id: "2", name: "Facility HVAC Optimization Run", trigger: "Hourly, at :00", status: "running", lastRun: "Today, 17:00" },
    { id: "3", name: "Campus Cleanliness Node Scan", trigger: "Every Monday at 08:00", status: "idle", lastRun: "June 1, 08:00" },
    { id: "4", name: "Automated Energy Saving Mode", trigger: "Every day at 22:00", status: "idle", lastRun: "Yesterday, 22:00" },
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
        const response = await fetch("http://localhost:8000/api/agent/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
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
    <div className="flex h-screen bg-[#080b11] text-slate-100 font-sans overflow-hidden">
      
      {/* SIDEBAR */}
      <aside className="w-64 glass-panel border-r border-slate-800 flex flex-col justify-between shrink-0">
        <div>
          <div className="p-6 flex items-center space-x-3 border-b border-slate-800">
            <div className="bg-primary-500/10 p-2 rounded-xl border border-primary-500/20 text-primary-400">
              <Sparkles className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight tracking-wider bg-gradient-to-r from-primary-400 to-indigo-400 bg-clip-text text-transparent">
                CAMPUS OPS
              </h1>
              <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
                Agent Controller
              </span>
            </div>
          </div>

          <nav className="p-4 space-y-2">
            <button
              onClick={() => setActiveTab("overview")}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                activeTab === "overview"
                  ? "bg-primary-500/20 text-primary-300 shadow-glass-inset border border-primary-500/30"
                  : "text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              }`}
            >
              <LayoutDashboard className="h-5 w-5" />
              <span className="text-sm font-medium">Overview</span>
            </button>
            <button
              onClick={() => setActiveTab("chat")}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                activeTab === "chat"
                  ? "bg-primary-500/20 text-primary-300 shadow-glass-inset border border-primary-500/30"
                  : "text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              }`}
            >
              <MessageSquare className="h-5 w-5" />
              <span className="text-sm font-medium">Agent Chat</span>
            </button>
            <button
              onClick={() => setActiveTab("scheduler")}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                activeTab === "scheduler"
                  ? "bg-primary-500/20 text-primary-300 shadow-glass-inset border border-primary-500/30"
                  : "text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              }`}
            >
              <CalendarDays className="h-5 w-5" />
              <span className="text-sm font-medium">Task Scheduler</span>
            </button>
            <button
              onClick={() => setActiveTab("facilities")}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                activeTab === "facilities"
                  ? "bg-primary-500/20 text-primary-300 shadow-glass-inset border border-primary-500/30"
                  : "text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              }`}
            >
              <Building2 className="h-5 w-5" />
              <span className="text-sm font-medium">Facilities</span>
            </button>

            <div className="pt-3 mt-3 border-t border-slate-800/60">
              <a
                href="/timetable"
                className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              >
                <CalendarDays className="h-5 w-5" />
                <span className="text-sm font-medium">Timetable</span>
              </a>
              <a
                href="/leaves"
                className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              >
                <CalendarX className="h-5 w-5" />
                <span className="text-sm font-medium">Leaves</span>
              </a>
              <a
                href="/approvals"
                className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              >
                <ClipboardCheck className="h-5 w-5" />
                <span className="text-sm font-medium">Approvals</span>
              </a>
              <a
                href="/exchanges"
                className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              >
                <ArrowLeftRight className="h-5 w-5" />
                <span className="text-sm font-medium">Exchanges</span>
              </a>
              <a
                href="/inbox"
                className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              >
                <Inbox className="h-5 w-5" />
                <span className="text-sm font-medium">Inbox</span>
              </a>
              <a
                href="/setup"
                className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              >
                <Database className="h-5 w-5" />
                <span className="text-sm font-medium">Data Setup</span>
              </a>
              <a
                href="/login"
                className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              >
                <LogIn className="h-5 w-5" />
                <span className="text-sm font-medium">Sign In</span>
              </a>
            </div>
          </nav>
        </div>

        {/* System Status Foot */}
        <div className="p-4 border-t border-slate-800/60 bg-slate-900/20">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-slate-400">Services Endpoint</span>
            <div className="flex items-center space-x-1.5">
              <span className={`h-2.5 w-2.5 rounded-full ${backendConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`}></span>
              <span className="font-semibold">{backendConnected ? "Online" : "Demo Mode"}</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 leading-normal">
            {backendConnected ? "Connected to FastAPI on port 8000." : "Failed to reach backend. Interactive features run as simulation."}
          </p>
        </div>
      </aside>

      {/* MAIN CONTAINER */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#080b11] relative">
        {/* Glow Effects */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-primary-500/10 rounded-full blur-[120px] pointer-events-none"></div>
        <div className="absolute bottom-10 left-10 w-80 h-80 bg-indigo-500/5 rounded-full blur-[100px] pointer-events-none"></div>

        {/* HEADER */}
        <header className="h-20 glass-panel border-b border-slate-800/60 flex items-center justify-between px-8 z-10 shrink-0">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-slate-100 flex items-center space-x-2">
              <span>Smart Campus Ops</span>
              <span className="text-xs bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 px-2 py-0.5 rounded-full font-medium uppercase tracking-wide">
                v1.0.0
              </span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">Automating day-to-day administrative overhead</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800 text-xs">
              <Zap className="h-4 w-4 text-amber-500" />
              <span>Orchestrator: <strong>LangGraph Engine</strong></span>
            </div>
          </div>
        </header>

        {/* CONTENT */}
        <div className="flex-1 overflow-y-auto p-8 z-10">
          
          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-8 animate-fadeIn">
              
              {/* Stat Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Active Agents</p>
                      <h3 className="text-3xl font-extrabold mt-2 text-slate-100">3 Nodes</h3>
                    </div>
                    <span className="bg-primary-500/10 p-2.5 rounded-xl border border-primary-500/20 text-primary-400">
                      <Bot className="h-5 w-5" />
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-4 flex items-center space-x-1">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
                    <span>Router, Scheduler, Facilities</span>
                  </p>
                </div>

                <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Scheduled Automations</p>
                      <h3 className="text-3xl font-extrabold mt-2 text-slate-100">{tasks.length} Active</h3>
                    </div>
                    <span className="bg-emerald-500/10 p-2.5 rounded-xl border border-emerald-500/20 text-emerald-400">
                      <CalendarDays className="h-5 w-5" />
                    </span>
                  </div>
                  <p className="text-[11px] text-emerald-400 mt-4 font-medium">
                    1 running currently
                  </p>
                </div>

                <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Reservations tracked</p>
                      <h3 className="text-3xl font-extrabold mt-2 text-slate-100">
                        {facilities.filter(f => f.status === "Reserved" || f.status === "Occupied").length} / {facilities.length}
                      </h3>
                    </div>
                    <span className="bg-amber-500/10 p-2.5 rounded-xl border border-amber-500/20 text-amber-400">
                      <Building2 className="h-5 w-5" />
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-4">
                    Rooms allocated for today
                  </p>
                </div>

                <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">System Integrity</p>
                      <h3 className="text-3xl font-extrabold mt-2 text-slate-100">99.8%</h3>
                    </div>
                    <span className="bg-indigo-500/10 p-2.5 rounded-xl border border-indigo-500/20 text-indigo-400">
                      <CheckCircle2 className="h-5 w-5" />
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-4">
                    All cron processes active
                  </p>
                </div>
              </div>

              {/* Dynamic workflow log and instructions */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* Graph visualization simulation */}
                <div className="lg:col-span-2 glass-card p-6 rounded-2xl flex flex-col h-[350px]">
                  <h4 className="font-bold text-sm uppercase tracking-wider text-slate-400 mb-6 flex items-center justify-between">
                    <span>LangGraph Active Flow Pipeline</span>
                    <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700">Visualization</span>
                  </h4>
                  
                  <div className="flex-1 flex items-center justify-around relative px-4">
                    {/* Visual graph connect lines */}
                    <div className="absolute left-[28%] right-[28%] top-1/2 h-0.5 bg-gradient-to-r from-primary-500 to-indigo-500 -translate-y-1/2 z-0"></div>
                    
                    <div className="z-10 flex flex-col items-center space-y-2">
                      <div className="w-16 h-16 rounded-full bg-slate-900 border-2 border-primary-500 flex items-center justify-center shadow-lg shadow-primary-500/20">
                        <Bot className="h-7 w-7 text-primary-400" />
                      </div>
                      <span className="text-xs font-bold">RouterNode</span>
                      <span className="text-[10px] text-slate-500">Evaluates Query</span>
                    </div>

                    <div className="flex flex-col space-y-6 z-10">
                      <div className="flex flex-col items-center space-y-1">
                        <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center">
                          <CalendarDays className="h-5 w-5 text-slate-400" />
                        </div>
                        <span className="text-[10px] font-medium">SchedulerNode</span>
                      </div>
                      <div className="flex flex-col items-center space-y-1">
                        <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center">
                          <Building2 className="h-5 w-5 text-slate-400" />
                        </div>
                        <span className="text-[10px] font-medium">FacilityNode</span>
                      </div>
                    </div>

                    <div className="z-10 flex flex-col items-center space-y-2">
                      <div className="w-16 h-16 rounded-full bg-slate-900 border-2 border-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                        <CheckCircle2 className="h-7 w-7 text-indigo-400" />
                      </div>
                      <span className="text-xs font-bold">State Response</span>
                      <span className="text-[10px] text-slate-500">Final Answer</span>
                    </div>
                  </div>
                  
                  <div className="mt-4 p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs text-slate-400 flex items-center space-x-2">
                    <AlertTriangle className="h-4 w-4 text-indigo-400 shrink-0" />
                    <span>The Multi-Agent architecture automatically routes instructions to specific node solvers depending on natural language intent.</span>
                  </div>
                </div>

                {/* Operations Summary */}
                <div className="glass-card p-6 rounded-2xl flex flex-col h-[350px]">
                  <h4 className="font-bold text-sm uppercase tracking-wider text-slate-400 mb-4">
                    Next Tasks Queue
                  </h4>
                  <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                    {tasks.map(task => (
                      <div key={task.id} className="p-3 bg-slate-950/40 border border-slate-800/60 rounded-xl flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-slate-200">{task.name}</p>
                          <p className="text-[10px] text-slate-500 mt-0.5">{task.trigger}</p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className={`h-2 w-2 rounded-full ${
                            task.status === "running" ? "bg-primary-500 animate-ping" :
                            task.status === "completed" ? "bg-emerald-500" : "bg-slate-600"
                          }`}></span>
                          <span className="text-[10px] font-semibold uppercase text-slate-400">{task.status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <button 
                    onClick={() => setActiveTab("scheduler")}
                    className="w-full mt-4 bg-primary-600 hover:bg-primary-500 text-white font-medium py-2 rounded-xl text-xs transition duration-200"
                  >
                    Manage Scheduler
                  </button>
                </div>

              </div>

            </div>
          )}

          {/* TAB 2: AGENT CHAT */}
          {activeTab === "chat" && (
            <div className="h-[calc(100vh-14rem)] flex gap-8 animate-fadeIn">
              
              {/* Chat Thread */}
              <div className="flex-1 glass-card rounded-2xl flex flex-col overflow-hidden relative">
                
                {/* Chat Header */}
                <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/10 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="h-10 w-10 bg-primary-500/10 rounded-xl border border-primary-500/30 flex items-center justify-center text-primary-400">
                      <Bot className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold">Campus Orchestrator Agent</h4>
                      <p className="text-[11px] text-slate-400">Active Node State Listener</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-1 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded text-[10px] font-semibold">
                    <span className="h-1.5 w-1.5 bg-emerald-400 rounded-full"></span>
                    <span>LangGraph Mode</span>
                  </div>
                </div>

                {/* Messages Box */}
                <div className="flex-1 p-6 overflow-y-auto space-y-4">
                  {messages.map((msg, index) => (
                    <div
                      key={index}
                      className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"} items-start gap-3`}
                    >
                      {msg.sender === "agent" && (
                        <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-primary-400 shrink-0 text-xs font-bold">
                          <Bot className="h-4 w-4" />
                        </div>
                      )}
                      <div className="max-w-[70%]">
                        <div
                          className={`p-4 rounded-2xl text-sm leading-relaxed border ${
                            msg.sender === "user"
                              ? "bg-primary-600/20 border-primary-500/30 text-slate-100 rounded-tr-none"
                              : "bg-slate-900/60 border-slate-800/80 text-slate-200 rounded-tl-none"
                          }`}
                        >
                          {msg.sender === "agent" && msg.agentName && (
                            <span className="text-[10px] block font-bold text-primary-400 uppercase tracking-wider mb-1">
                              {msg.agentName}
                            </span>
                          )}
                          <p>{msg.text}</p>
                        </div>
                        <span className="text-[10px] text-slate-500 mt-1 block px-2">
                          {msg.timestamp}
                        </span>
                      </div>
                    </div>
                  ))}

                  {isTyping && (
                    <div className="flex justify-start items-center gap-3">
                      <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-primary-400 shrink-0">
                        <Bot className="h-4 w-4 animate-spin" />
                      </div>
                      <div className="bg-slate-900/40 border border-slate-850 px-4 py-3 rounded-2xl text-xs text-slate-400 flex items-center space-x-2">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin text-slate-500" />
                        <span>LangGraph executing nodes...</span>
                      </div>
                    </div>
                  )}

                  <div ref={chatEndRef} />
                </div>

                {/* Input form */}
                <div className="p-4 border-t border-slate-800/80 bg-slate-900/20 flex items-center space-x-2">
                  <input
                    type="text"
                    value={inputVal}
                    onChange={(e) => setInputVal(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                    placeholder="Ask agent: 'Book Room 302 tomorrow' or 'List current scheduling issues'"
                    className="flex-1 glass-input px-4 py-3 rounded-xl text-sm"
                  />
                  <button
                    onClick={handleSendMessage}
                    className="bg-primary-600 hover:bg-primary-500 text-white p-3 rounded-xl transition duration-150 shadow-lg shadow-primary-600/10"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                </div>

              </div>

              {/* Steps/Trace Sidebar */}
              <div className="w-80 glass-card rounded-2xl p-6 flex flex-col h-full">
                <h4 className="font-bold text-sm uppercase tracking-wider text-slate-400 mb-4 flex items-center space-x-2">
                  <Zap className="h-4 w-4 text-primary-400" />
                  <span>Agent Run Log</span>
                </h4>
                
                <div className="flex-1 bg-slate-950/40 rounded-xl border border-slate-850 p-4 overflow-y-auto space-y-4">
                  {activeWorkflowSteps.length === 0 ? (
                    <div className="text-center py-12 text-slate-500 text-xs">
                      <Clock className="h-8 w-8 mx-auto mb-2 text-slate-600" />
                      No active workflow runtime trace. Ask the agent a question to view real-time state routing.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-[11px] font-semibold text-primary-400 uppercase tracking-widest">Active State Nodes</p>
                      {activeWorkflowSteps.map((step, idx) => (
                        <div key={idx} className="flex items-start space-x-2 text-xs border-l-2 border-primary-500 pl-3 py-1">
                          <div>
                            <p className="font-semibold text-slate-300">{step.split(":")[0]}</p>
                            {step.split(":")[1] && (
                              <p className="text-[10px] text-slate-500 mt-0.5">{step.split(":")[1]}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="mt-4 text-[11px] text-slate-500 leading-normal">
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
                  <h3 className="text-lg font-bold text-slate-200">Scheduled Operational Scripts</h3>
                  <p className="text-xs text-slate-400 mt-0.5">Autonomous routines executed by the Scheduler Agent node</p>
                </div>
                <button
                  onClick={() => setShowNewTaskModal(true)}
                  className="bg-primary-600 hover:bg-primary-500 text-white font-medium px-4 py-2 rounded-xl text-xs flex items-center space-x-2 transition duration-150"
                >
                  <Plus className="h-4 w-4" />
                  <span>Schedule Task</span>
                </button>
              </div>

              {/* Grid of Tasks */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {tasks.map(task => (
                  <div key={task.id} className="glass-card p-6 rounded-2xl flex flex-col justify-between border border-slate-800">
                    <div>
                      <div className="flex justify-between items-start">
                        <h4 className="font-bold text-slate-100 text-sm">{task.name}</h4>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          task.status === "completed" ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400" :
                          task.status === "running" ? "bg-primary-500/10 border border-primary-500/20 text-primary-400 animate-pulse" :
                          "bg-slate-800 border border-slate-700 text-slate-400"
                        }`}>
                          {task.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-2 flex items-center space-x-1.5">
                        <Clock className="h-3.5 w-3.5 text-slate-500" />
                        <span>Trigger: <strong>{task.trigger}</strong></span>
                      </p>
                    </div>

                    <div className="mt-6 pt-4 border-t border-slate-800/60 flex justify-between items-center text-xs text-slate-500">
                      <span>Last executed: {task.lastRun}</span>
                      <button
                        onClick={() => triggerTaskRun(task.id)}
                        disabled={task.status === "running"}
                        className="bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white px-3 py-1.5 rounded-lg border border-slate-700 font-semibold flex items-center space-x-1 transition disabled:opacity-40"
                      >
                        <Play className="h-3 w-3" />
                        <span>Execute Now</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Create Task Modal */}
              {showNewTaskModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                  <div className="glass-panel w-full max-w-md p-6 rounded-2xl border border-slate-800">
                    <h3 className="text-base font-bold mb-4">Schedule New Campus Automation</h3>
                    <form onSubmit={handleAddNewTask} className="space-y-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-1">Automation Task Name</label>
                        <input
                          type="text"
                          required
                          value={newTaskName}
                          onChange={(e) => setNewTaskName(e.target.value)}
                          placeholder="e.g. Server Backup, Faculty Timetable Audit"
                          className="w-full glass-input px-3 py-2 rounded-xl text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-1">Trigger (Cron / Interval)</label>
                        <input
                          type="text"
                          required
                          value={newTaskTrigger}
                          onChange={(e) => setNewTaskTrigger(e.target.value)}
                          placeholder="e.g. Every day at 04:00, Every 2 hours"
                          className="w-full glass-input px-3 py-2 rounded-xl text-sm"
                        />
                      </div>
                      <div className="flex justify-end space-x-3 pt-4 border-t border-slate-850">
                        <button
                          type="button"
                          onClick={() => setShowNewTaskModal(false)}
                          className="text-xs text-slate-400 hover:text-slate-200 px-3 py-2"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="bg-primary-600 hover:bg-primary-500 text-white font-medium px-4 py-2 rounded-xl text-xs"
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
                  <h3 className="text-lg font-bold text-slate-200">Campus Facilities Control</h3>
                  <p className="text-xs text-slate-400 mt-0.5">Real-time room occupancy and automated allocation tracking</p>
                </div>
                <button
                  onClick={() => setShowNewBookingModal(true)}
                  className="bg-primary-600 hover:bg-primary-500 text-white font-medium px-4 py-2 rounded-xl text-xs flex items-center space-x-2 transition duration-150"
                >
                  <Plus className="h-4 w-4" />
                  <span>Request Booking</span>
                </button>
              </div>

              {/* Facility Table */}
              <div className="glass-card rounded-2xl overflow-hidden border border-slate-800">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-900/40 border-b border-slate-800 text-slate-400 text-xs font-bold uppercase tracking-wider">
                        <th className="p-4 pl-6">Room / Lab</th>
                        <th className="p-4">Type</th>
                        <th className="p-4">Capacity</th>
                        <th className="p-4">Status</th>
                        <th className="p-4 pr-6">Current Reservation / User</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-sm">
                      {facilities.map(facility => (
                        <tr key={facility.id} className="hover:bg-slate-900/10 transition">
                          <td className="p-4 pl-6 font-semibold text-slate-200">{facility.name}</td>
                          <td className="p-4 text-slate-400">{facility.type}</td>
                          <td className="p-4 text-slate-400">{facility.capacity} seats</td>
                          <td className="p-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              facility.status === "Available" ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400" :
                              facility.status === "Occupied" ? "bg-indigo-500/10 border border-indigo-500/20 text-indigo-400" :
                              "bg-amber-500/10 border border-amber-500/20 text-amber-400"
                            }`}>
                              {facility.status}
                            </span>
                          </td>
                          <td className="p-4 pr-6 text-xs text-slate-300">
                            {facility.currentReservation || <span className="text-slate-500 italic">None (Ready for Booking)</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Booking Modal */}
              {showNewBookingModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                  <div className="glass-panel w-full max-w-md p-6 rounded-2xl border border-slate-800">
                    <h3 className="text-base font-bold mb-4">Request Facility Booking</h3>
                    <form onSubmit={handleCreateBooking} className="space-y-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-1">Select Room</label>
                        <select
                          required
                          value={selectedFacilityId}
                          onChange={(e) => setSelectedFacilityId(e.target.value)}
                          className="w-full glass-input px-3 py-2 rounded-xl text-sm bg-slate-900"
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
                        <label className="block text-xs font-semibold text-slate-400 mb-1">Reservation / Event Details</label>
                        <input
                          type="text"
                          required
                          value={bookingDetails}
                          onChange={(e) => setBookingDetails(e.target.value)}
                          placeholder="e.g. Operating Systems Lecture (10:00 - 12:00)"
                          className="w-full glass-input px-3 py-2 rounded-xl text-sm"
                        />
                      </div>
                      <div className="flex justify-end space-x-3 pt-4 border-t border-slate-850">
                        <button
                          type="button"
                          onClick={() => {
                            setShowNewBookingModal(false);
                            setSelectedFacilityId("");
                            setBookingDetails("");
                          }}
                          className="text-xs text-slate-400 hover:text-slate-200 px-3 py-2"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="bg-primary-600 hover:bg-primary-500 text-white font-medium px-4 py-2 rounded-xl text-xs"
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

        </div>
      </main>

    </div>
  );
}
