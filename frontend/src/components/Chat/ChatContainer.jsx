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
    <div className="flex flex-col h-full bg-bg-base">
      <div className="flex-1 overflow-y-auto px-4 py-8 flex flex-col gap-6">
        {messages.map((m) => (
          <div key={m.id} className="flex gap-4 max-w-3xl mx-auto w-full group">
            <div className={`w-8 h-8 rounded-sm flex items-center justify-center shrink-0 ${m.role === 'user' ? 'bg-accent-secondary' : 'bg-status-success'}`}>
              {m.role === 'user' ? <User size={20} className="text-white" /> : <Bot size={20} className="text-white" />}
            </div>
            <div className="flex-1 min-w-0">
              {m.role === 'user' && <div className="font-semibold text-text-primary mb-1">You</div>}
              {m.role === 'assistant' && m.content && <div className="font-semibold text-text-primary mb-1">PIE Assistant</div>}
              {m.role === 'user' ? (
                <p className="text-[15px] whitespace-pre-wrap leading-relaxed text-text-primary">
                  {m.content}
                </p>
              ) : (
                <MarkdownMessage content={m.content} />
              )}
            </div>
          </div>
        ))}
        {loading && !streamStarted && (
          <div className="flex gap-4 max-w-3xl mx-auto w-full">
            <div className="w-8 h-8 rounded-sm bg-status-success flex items-center justify-center shrink-0">
              <Bot size={20} className="text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-text-primary mb-1">PIE Assistant</div>
              <div className="flex items-center gap-1 h-6">
                 <div className="w-2 h-2 rounded-full bg-text-secondary animate-bounce" style={{ animationDelay: '0ms' }} />
                 <div className="w-2 h-2 rounded-full bg-text-secondary animate-bounce" style={{ animationDelay: '150ms' }} />
                 <div className="w-2 h-2 rounded-full bg-text-secondary animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="p-4 border-t border-border-color bg-bg-base">
        <form onSubmit={sendMessage} className="relative max-w-3xl mx-auto flex items-end bg-bg-surface border border-border-color rounded-xl shadow-sm focus-within:ring-1 focus-within:ring-accent-primary focus-within:border-accent-primary overflow-hidden">
          <textarea
            className="w-full bg-transparent text-text-primary p-3 pr-12 resize-none max-h-32 min-h-[44px] focus:outline-none scrollbar-hide"
            placeholder="Send a message to PIE..."
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
            className="absolute right-2 bottom-2 p-1.5 rounded-lg bg-accent-primary text-white hover:bg-accent-primary-hover transition-colors disabled:opacity-50 disabled:bg-bg-surface-elevated disabled:text-text-secondary"
          >
            <Send size={18} />
          </button>
        </form>
        <div className="text-center text-xs text-text-secondary mt-2">
          PIE can make mistakes. Consider verifying critical configurations.
        </div>
      </div>
    </div>
  );
}
