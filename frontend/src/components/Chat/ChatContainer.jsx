import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Bot,
  User,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Check,
  RotateCcw,
  ThumbsUp,
  MessageSquare,
  Workflow,
  GitBranch,
  Activity,
  Trash2,
  SlidersHorizontal,
  AlertTriangle,
  Clock,
  Download,
  Plus,
  Share2,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import MarkdownMessage from './MarkdownMessage';

const parseSSEBlock = (raw) => {
  let eventType = 'message';
  let data = '';
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) eventType = line.slice(6).trim();
    else if (line.startsWith('data:')) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { type: eventType, payload: JSON.parse(data) };
  } catch {
    return null;
  }
};

const QUERY_TEMPLATES = [
  {
    id: 'everyday',
    name: 'Everyday Queries',
    rows: '2.4k ADF entities',
    description: 'General conversational queries regarding ADF pipeline schedules, run states, and configurations.',
    query: 'What are the main pipelines and activities in this data factory?',
    icon: MessageSquare,
    color: 'text-blue-600',
    bg: 'bg-blue-50 border-blue-200',
  },
  {
    id: 'lineage',
    name: 'Pipeline Lineage',
    rows: '4 pipelines',
    description: 'Upstream and downstream pipeline execution dependencies, parent orchestrators, and triggered pipelines.',
    query: 'Explain the end-to-end lineage and dependencies of PL_Customer_Daily_Ingestion.',
    icon: GitBranch,
    color: 'text-orange-600',
    bg: 'bg-orange-50 border-orange-200',
  },
  {
    id: 'impact',
    name: 'Impact Simulation',
    rows: '12 relations',
    description: 'What-If deletion simulations to compute cascade breakage before modifying datasets or linked services.',
    query: 'What is the blast radius and impact if LS_AzureSql_EnterpriseDWH is deleted?',
    icon: AlertTriangle,
    color: 'text-teal-600',
    bg: 'bg-teal-50 border-teal-200',
  },
  {
    id: 'activities',
    name: 'Activity Chains',
    rows: '7 activities',
    description: 'Lookup, Copy, DatabricksNotebook, and ExecutePipeline step-by-step control flows.',
    query: 'List all activities inside PL_Customer_Daily_Ingestion and their retry configurations.',
    icon: Activity,
    color: 'text-sky-600',
    bg: 'bg-sky-50 border-sky-200',
  },
  {
    id: 'fragile',
    name: 'Fragile Retries & SLA',
    rows: '1 fragile step',
    description: 'Detect pipelines with 0-retry activities or tight SLA constraints vulnerable to failures.',
    query: 'Which pipeline activities have 0 retries and represent single points of failure?',
    icon: Clock,
    color: 'text-rose-600',
    bg: 'bg-rose-50 border-rose-200',
  },
  {
    id: 'orphan',
    name: 'Orphan Detection',
    rows: '0 orphans',
    description: 'Identify unreferenced pipelines not scheduled by any trigger or parent orchestrator.',
    query: 'Are there any orphan pipelines in df-dataintegration-dev that can be safely archived?',
    icon: Trash2,
    color: 'text-purple-600',
    bg: 'bg-purple-50 border-purple-200',
  },
  {
    id: 'transform',
    name: 'Data Flows & Spark',
    rows: '1 cluster',
    description: 'Apache Spark Databricks tasks and Slowly Changing Dimensions (SCD Type-2) transforms.',
    query: 'How does PL_DimCustomer_SCD2_Transform process staging records into DimCustomer?',
    icon: Workflow,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50 border-emerald-200',
  },
  {
    id: 'params',
    name: 'Global Parameters',
    rows: '3 parameters',
    description: 'Factory-wide parameters, default expressions, and dataset bindings.',
    query: 'Show all global parameters referenced across this data factory.',
    icon: SlidersHorizontal,
    color: 'text-indigo-600',
    bg: 'bg-indigo-50 border-indigo-200',
  },
];

export default function ChatContainer({ selectedModel, isExpanded, onToggleExpand }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: 'Welcome to your **PIE Conversational Workspace**. I have synchronized your Data Factory metadata. How can I help you today?',
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamStarted, setStreamStarted] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(QUERY_TEMPLATES[0]);
  const [likeCount, setLikeCount] = useState(159);
  const [hasLiked, setHasLiked] = useState(false);
  const [copied, setCopied] = useState(false);

  const chatEndRef = useRef(null);
  const sessionIdRef = useRef(null);
  if (!sessionIdRef.current) {
    sessionIdRef.current = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const activeFactory = localStorage.getItem('selected_factory') || 'df-dataintegration-dev';

  const handleLike = () => {
    if (hasLiked) {
      setLikeCount((prev) => prev - 1);
      setHasLiked(false);
    } else {
      setLikeCount((prev) => prev + 1);
      setHasLiked(true);
    }
  };

  const handleCopyThread = () => {
    const text = messages.map((m) => `${m.role.toUpperCase()}:\n${m.content}\n`).join('\n---\n\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClearThread = () => {
    setMessages([
      {
        id: Date.now(),
        role: 'assistant',
        content: `Conversation reset. Metadata for **${activeFactory}** is synchronized and ready.`,
      },
    ]);
  };

  const selectTemplate = (template) => {
    setSelectedTemplate(template);
    setInput(template.query);
  };

  const sendMessage = async (e, directText) => {
    if (e && e.preventDefault) e.preventDefault();
    const queryToSend = (typeof directText === 'string' ? directText : input).trim();
    if (!queryToSend || loading) return;

    const userMessage = { id: Date.now(), role: 'user', content: queryToSend };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setStreamStarted(false);

    const aiMessage = { id: Date.now() + 1, role: 'assistant', content: '' };
    setMessages((prev) => [...prev, aiMessage]);

    const sessionToken = localStorage.getItem('x_session_token');
    const apiBase = apiClient.defaults.baseURL;

    let receivedText = '';

    try {
      const response = await fetch(`${apiBase}/ai/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(sessionToken ? { 'X-Session-Token': sessionToken } : {}),
        },
        body: JSON.stringify({
          query: userMessage.content,
          factory_name: activeFactory,
          model: selectedModel,
          session_id: sessionIdRef.current,
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || `Server responded with ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      const processBlock = (raw) => {
        const parsed = parseSSEBlock(raw);
        if (!parsed) return;
        const { type, payload } = parsed;
        if (type === 'token' && payload.token) {
          if (!streamStarted) setStreamStarted(true);
          receivedText += payload.token;
          setMessages((prev) =>
            prev.map((m) => (m.id === aiMessage.id ? { ...m, content: receivedText } : m))
          );
        } else if (type === 'error') {
          throw new Error(payload.message || 'Streaming error');
        } else if (type === 'metadata') {
          console.log('Chat metadata:', payload);
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let sepIdx;
        while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, sepIdx);
          buffer = buffer.slice(sepIdx + 2);
          processBlock(raw);
        }
      }
      if (buffer.trim()) processBlock(buffer);
    } catch (error) {
      console.error('Chat stream error:', {
        message: error.message,
        status: error.response?.status,
        data: error.response?.data,
      });

      const errorDetail = error.message || 'Unknown error';
      if (!receivedText) {
        setMessages((prev) =>
          prev.map((m) => (m.id === aiMessage.id ? { ...m, content: `**Error:** ${errorDetail}` } : m))
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMessage.id ? { ...m, content: m.content + '\n\n_Stream interrupted._' } : m
          )
        );
      }
    } finally {
      setStreamStarted(false);
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#f8fafc] text-slate-900 font-sans antialiased overflow-hidden select-text">
      {/* ------------------------------------------------------------- */}
      {/* 1. TOP BREADCRUMB NAVIGATION BAR                              */}
      {/* ------------------------------------------------------------- */}
      <div className="h-12 shrink-0 px-4 border-b border-slate-200/80 bg-white/95 backdrop-blur-md flex items-center justify-between z-10 shadow-2xs">
        <div className="flex items-center gap-3 min-w-0">
          {/* Chevrons */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => window.history.back()}
              className="w-6 h-6 rounded-lg border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:text-slate-900 hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
              title="Back"
            >
              <ChevronLeft size={13} />
            </button>
            <button
              onClick={() => window.history.forward()}
              className="w-6 h-6 rounded-lg border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:text-slate-900 hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
              title="Forward"
            >
              <ChevronRight size={13} />
            </button>
          </div>

          {/* Breadcrumbs Path */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500 truncate font-medium">
            <span className="hover:text-slate-800 transition-colors cursor-pointer">Workspace</span>
            <span className="text-slate-300">›</span>
            <span className="hover:text-slate-800 font-semibold text-slate-700 transition-colors truncate">
              {activeFactory}
            </span>
            <span className="text-slate-300">›</span>
            <span className="font-bold text-slate-900 truncate">Conversational Intelligence</span>
            <span className="text-[11px] text-slate-400 font-mono ml-1 hidden sm:inline">
              ({messages.length} messages)
            </span>
          </div>
        </div>

        {/* Top Right Actions */}
        <div className="flex items-center gap-1.5 shrink-0 pl-2">
          {/* Synced Checkmark badge */}
          <div
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 border border-emerald-200/80 text-emerald-800 text-[11px] font-semibold"
            title="Metadata graph is synchronized and grounded"
          >
            <Check size={12} className="text-emerald-600" />
            <span className="hidden md:inline">Grounded</span>
          </div>

          {/* Clear chat */}
          <button
            onClick={handleClearThread}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Clear conversation"
          >
            <RotateCcw size={14} />
          </button>

          {/* Copy thread */}
          <button
            onClick={handleCopyThread}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Copy entire conversation"
          >
            {copied ? <Check size={14} className="text-emerald-600" /> : <Share2 size={14} />}
          </button>

          {/* Expand / Minimize Toggle */}
          {onToggleExpand && (
            <button
              onClick={onToggleExpand}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer ml-0.5"
              title={isExpanded ? 'Dock into split view' : 'Maximize to full width'}
            >
              {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* 2. MAIN BODY: SECONDARY CATALOG + CONVERSATION HERO & CANVAS  */}
      {/* ------------------------------------------------------------- */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Secondary Column: DATASET/CAPABILITY CATALOG (Shown in expanded mode or wide view) */}
        {(isExpanded || window.innerWidth >= 1200) && (
          <aside className="w-60 shrink-0 border-r border-slate-200/80 bg-white/70 backdrop-blur-md flex flex-col justify-between p-3.5 overflow-y-auto">
            <div>
              <div className="flex items-center justify-between mb-3 px-1">
                <span className="text-[11px] font-extrabold text-slate-400 uppercase tracking-wider">
                  Dataset Catalog
                </span>
                <span className="text-[10px] font-mono text-slate-400">{QUERY_TEMPLATES.length} topics</span>
              </div>

              <div className="space-y-1">
                {QUERY_TEMPLATES.map((item) => {
                  const isSelected = selectedTemplate.id === item.id;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => selectTemplate(item)}
                      className={`w-full flex items-center justify-between p-2 rounded-xl text-left transition-all group ${
                        isSelected
                          ? 'bg-blue-50/90 border border-blue-300 text-blue-900 shadow-2xs font-semibold'
                          : 'hover:bg-slate-100/80 border border-transparent text-slate-700 font-medium'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className={`w-7 h-7 rounded-lg ${item.bg} flex items-center justify-center shrink-0 shadow-2xs`}
                        >
                          <Icon size={14} className={item.color} />
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs truncate">{item.name}</div>
                          <div className="text-[10px] text-slate-400 font-mono truncate">{item.rows}</div>
                        </div>
                      </div>
                      <Sparkles
                        size={12}
                        className={`shrink-0 transition-opacity ${
                          isSelected ? 'text-blue-600 opacity-100' : 'opacity-0 group-hover:opacity-40'
                        }`}
                      />
                    </button>
                  );
                })}
              </div>

              {/* Add Custom Query Button */}
              <button
                onClick={() => setInput('')}
                className="w-full mt-3 py-2 px-3 rounded-xl border border-dashed border-slate-300 hover:border-blue-400 hover:bg-blue-50/50 text-slate-600 hover:text-blue-700 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                <Plus size={13} />
                <span>Add your own query</span>
              </button>
            </div>

            {/* Bottom Catalog Notice */}
            <div className="mt-4 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 text-[10px] text-slate-500 leading-relaxed font-medium">
              Synchronized with factory <span className="font-semibold text-slate-700">{activeFactory}</span>. Click
              any catalog template to inspect pipelines.
            </div>
          </aside>
        )}

        {/* Center Canvas: Hero Card + Conversation Thread + Reaction Badges */}
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto p-4 sm:p-6 bg-[#f8fafc]">
          <div className="max-w-4xl mx-auto w-full flex flex-col gap-4">
            {/* --------------------------------------------------------- */}
            {/* HERO HEADER CARD (Matches "Everyday Conversations 2k")   */}
            {/* --------------------------------------------------------- */}
            <div className="p-5 rounded-3xl bg-white border border-slate-200/90 shadow-card flex flex-col gap-3">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-sm shrink-0">
                    <MessageSquare size={22} />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-xl font-black text-slate-900 tracking-tight truncate">
                      {selectedTemplate ? selectedTemplate.name : 'Conversational Intelligence'}
                    </h2>
                    <p className="text-xs text-slate-500 font-medium mt-0.5 truncate">
                      {selectedTemplate.rows} • Synced with <strong className="text-slate-800">{activeFactory}</strong>
                    </p>
                  </div>
                </div>

                {/* Primary Action Button ("Download & use" style in reference) */}
                <button
                  onClick={() => sendMessage(null, selectedTemplate.query)}
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 text-xs font-bold transition-all shadow-xs shrink-0 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Download size={13} />
                  <span>Execute Query</span>
                </button>
              </div>

              {/* Description Paragraph */}
              <p className="text-xs text-slate-600 leading-relaxed font-medium">
                {selectedTemplate.description} Conversational responses are deterministically verified against your
                ADF lineage graph and knowledge repository.
              </p>

              {/* Tags / Subtitle metadata */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500 font-medium pt-1 border-t border-slate-100">
                <span>
                  Provider: <strong className="text-slate-800 font-semibold">{selectedModel}</strong>
                </span>
                <span>•</span>
                <span>
                  Grounding: <strong className="text-emerald-700 font-semibold">100% Graph Verification</strong>
                </span>
                <span>•</span>
                <span>
                  Mode: <strong className="text-blue-700 font-semibold">Real-Time Streaming SSE</strong>
                </span>
              </div>
            </div>

            {/* --------------------------------------------------------- */}
            {/* CONVERSATION THREAD CONTAINER ("EXAMPLE TRAINING ROW")    */}
            {/* --------------------------------------------------------- */}
            <div className="relative rounded-3xl bg-white border border-slate-200/90 shadow-card p-5 sm:p-6 flex flex-col gap-4">
              {/* Card Sub-header */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <span className="text-[11px] font-extrabold text-slate-400 uppercase tracking-wider block">
                    Conversation Thread
                  </span>
                  <p className="text-xs text-slate-500 font-medium mt-0.5">
                    Live dialogue grounded in your Azure Data Factory architecture
                  </p>
                </div>

                {/* Right Reaction & Stats (Thumbs up & Comment counts from reference photo!) */}
                <div className="flex items-center gap-3 shrink-0">
                  {/* Thumbs up reaction */}
                  <button
                    onClick={handleLike}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-bold transition-all shadow-2xs cursor-pointer ${
                      hasLiked
                        ? 'bg-blue-50 border-blue-300 text-blue-700'
                        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                    title="Mark conversation as helpful"
                  >
                    <ThumbsUp size={14} className={hasLiked ? 'text-blue-600 fill-blue-600' : 'text-slate-500'} />
                    <span>{likeCount}</span>
                  </button>

                  {/* Comment / message count */}
                  <div
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white text-slate-600 text-xs font-bold shadow-2xs"
                    title="Total messages in thread"
                  >
                    <MessageSquare size={14} className="text-slate-500" />
                    <span>{messages.length}</span>
                  </div>
                </div>
              </div>

              {/* Messages Flow */}
              <div className="space-y-4 min-h-[220px] max-h-[460px] overflow-y-auto pr-1">
                {messages.map((m) => (
                  <div key={m.id} className="flex flex-col gap-1 w-full animate-in fade-in duration-200">
                    {/* Role Header */}
                    <div
                      className={`text-[10px] font-black uppercase tracking-wider ${
                        m.role === 'user' ? 'text-slate-400 text-right pr-1' : 'text-blue-600 flex items-center gap-1.5 pl-1'
                      }`}
                    >
                      {m.role === 'user' ? (
                        'User'
                      ) : (
                        <>
                          <Sparkles size={11} className="text-blue-600" />
                          <span>Assistant</span>
                        </>
                      )}
                    </div>

                    {/* Bubble Content */}
                    {m.role === 'user' ? (
                      <div className="max-w-xl ml-auto p-3.5 rounded-2xl rounded-tr-xs bg-slate-100 text-slate-900 border border-slate-200/80 text-sm font-medium leading-relaxed shadow-2xs">
                        <p className="whitespace-pre-wrap">{m.content}</p>
                      </div>
                    ) : (
                      <div className="max-w-3xl mr-auto p-4 sm:p-5 rounded-2xl rounded-tl-xs bg-blue-50/50 border border-blue-200/80 text-sm text-slate-900 shadow-2xs leading-relaxed">
                        <MarkdownMessage content={m.content} />
                      </div>
                    )}
                  </div>
                ))}

                {/* Loading Streaming Indicator */}
                {loading && !streamStarted && (
                  <div className="flex flex-col gap-1 w-full animate-in fade-in duration-200">
                    <div className="text-[10px] font-black uppercase tracking-wider text-blue-600 flex items-center gap-1.5 pl-1">
                      <Sparkles size={11} className="text-blue-600" />
                      <span>Assistant</span>
                    </div>
                    <div className="max-w-xs p-3.5 rounded-2xl rounded-tl-xs bg-blue-50/50 border border-blue-200/80 flex items-center gap-2 text-xs text-slate-600">
                      <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '300ms' }} />
                      <span className="font-semibold text-slate-700 ml-1">Analyzing lineage graph...</span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* ------------------------------------------------------- */}
              {/* GROUNDING CALLOUT BANNER (Matches reference blue banner)*/}
              {/* ------------------------------------------------------- */}
              <div className="p-3.5 rounded-2xl bg-blue-50/70 border border-blue-200/80 flex items-center gap-3 text-xs text-slate-700 shadow-2xs">
                <div className="w-6 h-6 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-2xs">
                  <Sparkles size={13} />
                </div>
                <div className="leading-snug">
                  <strong className="text-blue-950 font-bold">The assistant reply is the learning target.</strong>
                  <span className="text-slate-600 ml-1">
                    The user message provides context; deterministic knowledge graphs grade and ground the response.
                  </span>
                </div>
              </div>

              {/* ------------------------------------------------------- */}
              {/* INPUT FORM                                              */}
              {/* ------------------------------------------------------- */}
              <form
                onSubmit={sendMessage}
                className="relative flex items-center bg-slate-50 border border-slate-300 rounded-2xl focus-within:ring-2 focus-within:ring-blue-600/20 focus-within:border-blue-600 transition-all overflow-hidden shadow-2xs"
              >
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={loading}
                  placeholder="Ask anything about ADF pipelines, activities, datasets, triggers..."
                  className="w-full bg-transparent px-4 py-3.5 text-sm text-slate-900 placeholder:text-slate-500 focus:outline-none font-medium pr-12"
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="absolute right-2 p-2 rounded-xl bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 transition-colors disabled:opacity-40 disabled:bg-slate-300 disabled:text-slate-500 shadow-2xs cursor-pointer"
                  title="Send message (Enter)"
                >
                  <Send size={15} />
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
