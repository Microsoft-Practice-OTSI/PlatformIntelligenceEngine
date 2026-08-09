import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User } from 'lucide-react';
import { apiClient } from '../../api/client';

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
  
  const chatEndRef = useRef(null);

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

    try {
      // Get factory name from localStorage (set during factory selection)
      const factoryName = localStorage.getItem('selected_factory') || 'default';
      const sessionToken = localStorage.getItem('x_session_token');
      
      console.log('Sending chat request with:', {
        factory: factoryName,
        model: selectedModel,
        sessionToken: sessionToken ? '✓ present' : '✗ missing',
        query: userMessage.content.substring(0, 50) + '...'
      });
      
      const response = await apiClient.post('/ai/ask', {
        query: userMessage.content,
        factory_name: factoryName,
        model: selectedModel
      });
      
      console.log('Chat response received:', response.data);

      const aiMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.data.response_markdown || response.data.answer || 'Completed.'
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error('Chat API Error:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        headers: error.response?.headers,
        request: error.request?.url,
        stack: error.stack
      });
      
      const errorDetail = error.response?.data?.detail 
        || error.response?.data?.message 
        || error.message 
        || 'Unknown error';
      
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `**Error:** ${errorDetail}\n\nDebug: Check browser console (F12) for full details.`
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
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
              <div className="font-semibold text-text-primary mb-1">{m.role === 'user' ? 'You' : 'PIE Assistant'}</div>
              <p className="text-[15px] whitespace-pre-wrap leading-relaxed text-text-primary">
                {m.content}
              </p>
            </div>
          </div>
        ))}
        {loading && (
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
                sendMessage(e);
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
