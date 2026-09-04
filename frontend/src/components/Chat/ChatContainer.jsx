import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User } from 'lucide-react';
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

export default function ChatContainer({ selectedModel }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: 'Welcome to your PIE Conversational Workspace. I have synced your Data Factory metadata. How can I help you today?',
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamStarted, setStreamStarted] = useState(false);

  const chatEndRef = useRef(null);
  const sessionIdRef = useRef(null);
  if (!sessionIdRef.current) {
    sessionIdRef.current = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { id: Date.now(), role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setStreamStarted(false);

    const aiMessage = { id: Date.now() + 1, role: 'assistant', content: '' };
    setMessages((prev) => [...prev, aiMessage]);

    const factoryName = localStorage.getItem('selected_factory') || 'default';
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
          factory_name: factoryName,
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
    <div className="flex flex-col h-full bg-transparent">
      <div className="flex-1 overflow-y-auto px-4 py-6 flex flex-col gap-5">
        {messages.map((m) => (
          <div key={m.id} className="flex gap-3 max-w-3xl mx-auto w-full group animate-in fade-in duration-200">
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 shadow-xs mt-0.5 ${m.role === 'user' ? 'bg-accent-primary' : 'bg-emerald-600'}`}>
              {m.role === 'user' ? <User size={16} className="text-white" /> : <Bot size={16} className="text-white" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-slate-800 mb-1.5 flex items-center gap-2">
                <span>{m.role === 'user' ? 'You' : 'PIE Assistant'}</span>
              </div>
              {m.role === 'user' ? (
                <div className="p-4 rounded-2xl bg-blue-50/90 backdrop-blur-sm border border-blue-200/90 text-sm font-medium text-slate-900 leading-relaxed shadow-xs">
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>
              ) : (
                <div className="p-5 rounded-2xl bg-white/90 backdrop-blur-md border border-slate-200/80 text-sm text-slate-900 shadow-card leading-relaxed">
                  <MarkdownMessage content={m.content} />
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && !streamStarted && (
          <div className="flex gap-3 max-w-3xl mx-auto w-full animate-in fade-in duration-200">
            <div className="w-7 h-7 rounded-lg bg-emerald-600 flex items-center justify-center shrink-0 shadow-xs mt-0.5">
              <Bot size={16} className="text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-slate-800 mb-1.5">PIE Assistant</div>
              <div className="p-3.5 rounded-2xl bg-white/90 backdrop-blur-md border border-slate-200 shadow-card flex items-center gap-1.5 h-10 w-20">
                 <div className="w-2 h-2 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                 <div className="w-2 h-2 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                 <div className="w-2 h-2 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="p-4 border-t border-slate-200/80 bg-white/80 backdrop-blur-md">
        <form onSubmit={sendMessage} className="relative max-w-3xl mx-auto flex items-end bg-white/95 border border-slate-300 rounded-2xl shadow-sm focus-within:ring-2 focus-within:ring-accent-primary/20 focus-within:border-accent-primary transition-all overflow-hidden">
          <textarea
            className="w-full bg-transparent text-slate-900 font-medium p-3.5 pr-12 resize-none max-h-32 min-h-[46px] focus:outline-none scrollbar-hide text-sm placeholder:text-slate-500"
            placeholder="Ask anything about ADF pipelines, datasets, dependencies..."
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form.requestSubmit();
              }
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="absolute right-2 bottom-2 p-2.5 rounded-xl bg-accent-primary text-white hover:bg-accent-hover shadow-xs transition-colors disabled:opacity-40 disabled:bg-slate-200 disabled:text-slate-400"
          >
            <Send size={15} />
          </button>
        </form>
        <div className="text-center text-xs font-medium text-slate-600 mt-2">
          PIE Assistant indexes ADF lineage and metadata in real-time. Verify critical configs.
        </div>
      </div>
    </div>
  );
}
