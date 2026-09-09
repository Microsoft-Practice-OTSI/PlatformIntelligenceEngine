import React, { useEffect, useState } from 'react';
import { Settings, Cpu, User, Clock, ChevronDown, Check, LogOut, Layers } from 'lucide-react';
import { apiClient } from '../../api/client';
import SettingsModal from './SettingsModal';

export default function Sidebar({ selectedModel, setSelectedModel, onSwitchAccount, onSwitchFactory }) {
  const [sessionInfo, setSessionInfo] = useState(null);
  const [factories, setFactories] = useState([]);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const models = [
    { id: 'azure-openai', name: 'Azure OpenAI', icon: '☁️' },
    { id: 'google-gemini', name: 'Google Gemini', icon: '✨' },
    { id: 'nvidia-nim', name: 'NVIDIA NIM', icon: '🟩' }
  ];

  useEffect(() => {
    const fetchSession = async () => {
      try {
        const { data } = await apiClient.get('/auth/session');
        setSessionInfo(data);
      } catch (e) {
        console.error('Failed to fetch session info');
      }
    };

    const fetchFactories = async () => {
      try {
        const { data } = await apiClient.get('/factories');
        setFactories(data.factories || []);
      } catch (e) {
        console.error('Failed to fetch synced factories');
      }
    };

    fetchSession();
    fetchFactories();
  }, []);

  const activeFactory = factories.length > 0 ? factories[0] : null;

  const handleModelSelect = (modelId) => {
    setSelectedModel(modelId);
    setIsModelDropdownOpen(false);
  };

  return (
    <div className="w-64 h-full bg-white/80 backdrop-blur-xl border-r border-slate-200/80 flex flex-col justify-between p-4">
      
      {/* Top Section */}
      <div>
        {/* Model Selection */}
        <div className="mb-6 relative">
          <div className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 px-1 flex items-center gap-1.5">
            <Cpu size={14} className="text-accent-primary" /> AI Model
          </div>
          
          <button 
            onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
            className="w-full flex items-center justify-between p-2.5 rounded-xl border border-slate-200 bg-white hover:border-accent-primary hover:bg-slate-50 transition-all shadow-xs"
          >
            <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
              <span>{models.find(m => m.id === selectedModel)?.icon}</span>
              <span>{models.find(m => m.id === selectedModel)?.name}</span>
            </div>
            <ChevronDown size={15} className="text-slate-600" />
          </button>

          {isModelDropdownOpen && (
            <div className="absolute top-full left-0 mt-1.5 w-full bg-white border border-slate-200 rounded-xl shadow-lg z-50 overflow-hidden py-1 animate-in fade-in slide-in-from-top-2">
              {models.map(model => (
                <button
                  key={model.id}
                  onClick={() => handleModelSelect(model.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 text-xs transition-colors text-left ${
                    selectedModel === model.id ? 'bg-blue-50 font-bold text-accent-primary' : 'hover:bg-slate-50 text-slate-900 font-medium'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span>{model.icon}</span>
                    <span>{model.name}</span>
                  </div>
                  {selectedModel === model.id && <Check size={14} className="text-accent-primary" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Section */}
      <div className="space-y-3">
        {/* Workspace Status */}
        {activeFactory && (
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs shadow-xs">
            <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-200">
              <span className="text-slate-700 font-semibold">Active Factory</span>
              <div className="flex items-center gap-1">
                <span className="font-bold text-accent-primary truncate max-w-[90px]" title={activeFactory.factory_name}>
                  {activeFactory.factory_name}
                </span>
                {onSwitchFactory && (
                  <button
                    onClick={onSwitchFactory}
                    className="p-1 rounded-md hover:bg-slate-200/70 text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
                    title="Switch Data Factory or Subscription"
                  >
                    <Layers size={13} />
                  </button>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-1 text-xs text-slate-700">
              <div className="flex items-center gap-1.5 font-medium text-slate-700">
                <Clock size={12} className="text-slate-500" />
                <span>Last Synced:</span>
              </div>
              <span className="font-mono text-slate-900 font-semibold">{new Date(activeFactory.last_refreshed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          </div>
        )}

        {/* Profile */}
        <div 
          className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs group"
          title="Account & AI Provider Settings"
        >
          <div 
            onClick={() => setIsSettingsOpen(true)}
            className="flex items-center gap-2.5 min-w-0 flex-1 cursor-pointer"
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-accent-primary to-accent-secondary flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-xs">
              {sessionInfo?.claims?.display_name?.charAt(0) || <User size={15} />}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-bold text-slate-900 truncate">
                {sessionInfo?.claims?.display_name || 'Loading Profile...'}
              </div>
              <div className="text-[11px] text-slate-600 font-medium truncate">
                {sessionInfo?.user_id}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-0.5 shrink-0 pl-1">
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
              title="AI Provider Settings"
            >
              <Settings size={15} />
            </button>
            {onSwitchAccount && (
              <button
                onClick={onSwitchAccount}
                className="p-1.5 rounded-lg hover:bg-red-50 text-slate-500 hover:text-red-600 transition-colors cursor-pointer"
                title="Switch Account / Log Out"
              >
                <LogOut size={15} />
              </button>
            )}
          </div>
        </div>
      </div>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        authenticated={sessionInfo?.authenticated}
      />
    </div>
  );
}
