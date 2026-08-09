import React, { useEffect, useState } from 'react';
import { Settings, Cpu, User, Clock, ChevronDown, Check } from 'lucide-react';
import { apiClient } from '../../api/client';
import SettingsModal from './SettingsModal';

export default function Sidebar({ selectedModel, setSelectedModel }) {
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
    <div className="w-64 h-full bg-bg-surface border-r border-border-color flex flex-col justify-between p-4">
      
      {/* Top Section */}
      <div>
        {/* Branding */}
        <div className="flex items-center gap-3 mb-8 px-2">
          <div className="w-10 h-10 rounded-lg bg-accent-primary flex items-center justify-center font-bold text-white text-xl shadow-lg shadow-accent-primary/20">
            P
          </div>
          <div>
            <h1 className="font-bold text-lg text-text-primary tracking-tight">Ad-PIE</h1>
            <p className="text-[10px] text-text-secondary uppercase tracking-wider font-semibold">Intelligence Engine</p>
          </div>
        </div>

        {/* Model Selection */}
        <div className="mb-6 relative">
          <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 px-2 flex items-center gap-2">
            <Cpu size={14} /> AI Model
          </div>
          
          <button 
            onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
            className="w-full flex items-center justify-between p-3 rounded-lg border border-border-color bg-bg-base hover:border-accent-primary hover:bg-bg-surface-elevated transition-colors"
          >
            <div className="flex items-center gap-2 text-sm font-medium">
              <span>{models.find(m => m.id === selectedModel)?.icon}</span>
              {models.find(m => m.id === selectedModel)?.name}
            </div>
            <ChevronDown size={16} className="text-text-secondary" />
          </button>

          {isModelDropdownOpen && (
            <div className="absolute top-full left-0 mt-1 w-full bg-bg-base border border-border-color rounded-lg shadow-xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2">
              {models.map(model => (
                <button
                  key={model.id}
                  onClick={() => handleModelSelect(model.id)}
                  className="w-full flex items-center justify-between p-3 text-sm hover:bg-bg-surface-elevated transition-colors text-left"
                >
                  <div className="flex items-center gap-2">
                    <span>{model.icon}</span>
                    <span className={selectedModel === model.id ? 'font-medium text-accent-primary' : 'text-text-primary'}>
                      {model.name}
                    </span>
                  </div>
                  {selectedModel === model.id && <Check size={16} className="text-accent-primary" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Section */}
      <div className="space-y-4">
        {/* Workspace Status */}
        {activeFactory && (
          <div className="p-3 rounded-lg bg-bg-base border border-border-color text-xs">
            <div className="flex items-center justify-between mb-2 pb-2 border-b border-border-color">
              <span className="text-text-secondary">Workspace</span>
              <span className="font-medium text-accent-primary truncate max-w-[100px]">{activeFactory.factory_name}</span>
            </div>
            <div className="flex flex-col gap-1 text-text-secondary">
              <div className="flex items-center gap-1">
                <Clock size={12} />
                <span>Last Refreshed:</span>
              </div>
              <span className="font-mono">{new Date(activeFactory.last_refreshed_at).toLocaleString()}</span>
            </div>
          </div>
        )}

        {/* Profile */}
        <div 
          onClick={() => setIsSettingsOpen(true)}
          className="flex items-center gap-3 p-2 rounded-lg hover:bg-bg-base transition-colors cursor-pointer group border border-transparent hover:border-border-color"
        >
          <div className="w-8 h-8 rounded-full bg-accent-secondary flex items-center justify-center text-white font-medium shrink-0">
            {sessionInfo?.claims?.display_name?.charAt(0) || <User size={16} />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-text-primary truncate">
              {sessionInfo?.claims?.display_name || 'Loading Profile...'}
            </div>
            <div className="text-xs text-text-secondary truncate">
              {sessionInfo?.user_id}
            </div>
          </div>
          <Settings size={16} className="text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
        </div>
      </div>

      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
}
