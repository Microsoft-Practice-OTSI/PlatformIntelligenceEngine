import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';

import ChatContainer from '../components/Chat/ChatContainer';
import SetupWizard from '../components/Onboarding/SetupWizard';
import Sidebar from '../components/Sidebar/Sidebar';

export default function MainWorkspace() {
  const [workspaceReady, setWorkspaceReady] = useState(false);
  const [selectedModel, setSelectedModel] = useState(() => {
    // Load model selection from localStorage, default to 'nvidia-nim'
    return localStorage.getItem('selected_model') || 'nvidia-nim';
  });

  // Persist model selection to localStorage whenever it changes
  const handleModelChange = (newModel) => {
    localStorage.setItem('selected_model', newModel);
    setSelectedModel(newModel);
  };
  
  if (!workspaceReady) {
    return <SetupWizard onComplete={() => setWorkspaceReady(true)} />;
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-bg-base text-text-primary">
      
      {/* Left Pane 1: Sidebar Settings */}
      <Sidebar selectedModel={selectedModel} setSelectedModel={handleModelChange} />

      {/* Left Pane 2: Chatbot / Command Center */}
      <div className="w-[35%] h-full border-r border-border-color flex flex-col bg-bg-base">
        <div className="flex-1 overflow-hidden relative">
          <ChatContainer selectedModel={selectedModel} />
        </div>
      </div>

      {/* Right Pane: Dynamic Data Canvas */}
      <div className="flex-1 h-full flex flex-col relative overflow-hidden bg-bg-base">
        <Outlet />
      </div>
    </div>
  );
}

