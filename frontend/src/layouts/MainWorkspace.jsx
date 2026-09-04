import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';

import ChatContainer from '../components/Chat/ChatContainer';
import SetupWizard from '../components/Onboarding/SetupWizard';
import Sidebar from '../components/Sidebar/Sidebar';
import TopBar from '../components/TopBar';
import { apiClient } from '../api/client';

export default function MainWorkspace() {
  const [workspaceReady, setWorkspaceReady] = useState(() => {
    return Boolean(localStorage.getItem('x_session_token') && localStorage.getItem('selected_factory'));
  });
  const [sessionInfo, setSessionInfo] = useState(null);
  const [selectedModel, setSelectedModel] = useState(() => {
    // Load model selection from localStorage, default to 'nvidia-nim'
    return localStorage.getItem('selected_model') || 'nvidia-nim';
  });

  useEffect(() => {
    const fetchSession = async () => {
      if (localStorage.getItem('x_session_token')) {
        try {
          const { data } = await apiClient.get('/auth/session');
          setSessionInfo(data);
        } catch (e) {
          localStorage.removeItem('x_session_token');
          setWorkspaceReady(false);
        }
      }
    };
    if (workspaceReady) {
      fetchSession();
    }
  }, [workspaceReady]);

  // Persist model selection to localStorage whenever it changes
  const handleModelChange = (newModel) => {
    localStorage.setItem('selected_model', newModel);
    setSelectedModel(newModel);
  };

  const handleSwitchAccount = async () => {
    try {
      await apiClient.post('/auth/logout');
    } catch (e) {
      console.warn('Logout request failed:', e);
    } finally {
      localStorage.removeItem('x_session_token');
      localStorage.removeItem('selected_factory');
      setSessionInfo(null);
      setWorkspaceReady(false);
    }
  };

  const handleSwitchFactory = () => {
    setWorkspaceReady(false);
  };
  
  if (!workspaceReady) {
    return <SetupWizard onComplete={() => setWorkspaceReady(true)} />;
  }

  return (
    <div className="flex flex-col h-screen w-full overflow-hidden glass-canvas text-text-primary relative">

      {/* Light blue glassy ambient highlights */}
      <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] rounded-full bg-sky-200/25 blur-[100px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[20%] w-[550px] h-[550px] rounded-full bg-blue-100/30 blur-[120px] pointer-events-none" />

      {/* Frozen top branding bar (visible across all views) */}
      <TopBar 
        sessionInfo={sessionInfo} 
        onSwitchAccount={handleSwitchAccount} 
        onSwitchFactory={handleSwitchFactory} 
      />

      <div className="flex flex-1 min-h-0 w-full overflow-hidden relative z-1">
        {/* Left Pane 1: Sidebar Settings */}
        <Sidebar 
          selectedModel={selectedModel} 
          setSelectedModel={handleModelChange}
          onSwitchAccount={handleSwitchAccount}
          onSwitchFactory={handleSwitchFactory}
        />

        {/* Left Pane 2: Chatbot / Command Center */}
        <div className="w-[35%] h-full border-r border-slate-200/80 flex flex-col bg-white/40 backdrop-blur-md">
          <div className="flex-1 overflow-hidden relative">
            <ChatContainer selectedModel={selectedModel} />
          </div>
        </div>

        {/* Right Pane: Dynamic Data Canvas */}
        <div className="flex-1 h-full flex flex-col relative overflow-hidden bg-transparent">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

