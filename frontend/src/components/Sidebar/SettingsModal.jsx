import React, { useState, useEffect } from 'react';
import { X, Save, Key, Check, LogOut, AlertTriangle, Loader2 } from 'lucide-react';
import { apiClient } from '../../api/client';

export default function SettingsModal({ isOpen, onClose, authenticated }) {
  const [keys, setKeys] = useState({
    google: '',
    azureEndpoint: '',
    azureKey: '',
    nvidia: ''
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchKeys();
    } else {
      setConfirmLogout(false);
      setSuccess(false);
    }
  }, [isOpen]);

  const fetchKeys = async () => {
    try {
      const { data } = await apiClient.get('/settings/keys');
      setKeys(data);
    } catch (e) {
      console.error('Failed to fetch keys');
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      await apiClient.post('/settings/keys', keys);
      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onClose();
      }, 1500);
    } catch (e) {
      console.error('Failed to save keys');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await apiClient.post('/auth/logout');
    } catch (e) {
      // Even if the API fails, clear the local session and return to login
      console.error('Logout API failed:', e);
    } finally {
      localStorage.removeItem('x_session_token');
      localStorage.removeItem('selected_factory');
      window.location.href = '/';
    }
  };

  if (!isOpen) return null;

  if (confirmLogout) {
    return (
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in">
        <div className="bg-bg-surface border border-border-color rounded-xl w-full max-w-md shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
          {/* Header */}
          <div className="p-4 border-b border-border-color flex items-center justify-between bg-bg-surface-elevated">
            <div className="flex items-center gap-2">
              <AlertTriangle size={18} className="text-red-500" />
              <h2 className="font-semibold text-lg text-text-primary">Confirm Logout</h2>
            </div>
            <button onClick={() => setConfirmLogout(false)} className="p-1 rounded hover:bg-bg-base text-text-secondary hover:text-text-primary transition-colors">
              <X size={20} />
            </button>
          </div>

          {/* Body */}
          <div className="p-6">
            <p className="text-sm text-text-secondary">
              Are you sure you want to log out? Your PIE session will be revoked and you'll return to the login screen.
            </p>
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-border-color bg-bg-base flex justify-end gap-3">
            <button
              onClick={() => setConfirmLogout(false)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50"
            >
              {loggingOut ? <Loader2 className="animate-spin" size={16} /> : <LogOut size={16} />}
              {loggingOut ? 'Logging out...' : 'Log Out'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in">
      <div className="bg-bg-surface border border-border-color rounded-xl w-full max-w-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-4 border-b border-border-color flex items-center justify-between bg-bg-surface-elevated">
          <div className="flex items-center gap-2">
            <Key size={18} className="text-accent-primary" />
            <h2 className="font-semibold text-lg text-text-primary">AI Provider Settings</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-bg-base text-text-secondary hover:text-text-primary transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Google Gemini API Key</label>
            <input 
              type="password" 
              value={keys.google}
              onChange={(e) => setKeys({...keys, google: e.target.value})}
              placeholder="AIzaSy..." 
              className="w-full bg-bg-base border border-border-color rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Azure OpenAI Endpoint</label>
            <input 
              type="text" 
              value={keys.azureEndpoint}
              onChange={(e) => setKeys({...keys, azureEndpoint: e.target.value})}
              placeholder="https://your-resource.openai.azure.com/" 
              className="w-full bg-bg-base border border-border-color rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-primary mb-3"
            />
            <label className="block text-sm font-medium text-text-primary mb-1">Azure OpenAI Key</label>
            <input 
              type="password" 
              value={keys.azureKey}
              onChange={(e) => setKeys({...keys, azureKey: e.target.value})}
              placeholder="Enter Azure Key" 
              className="w-full bg-bg-base border border-border-color rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">NVIDIA NIM API Key</label>
            <input 
              type="password" 
              value={keys.nvidia}
              onChange={(e) => setKeys({...keys, nvidia: e.target.value})}
              placeholder="nvapi-..." 
              className="w-full bg-bg-base border border-border-color rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
        </div>

        {/* Session / Logout */}
        {authenticated && (
          <div className="px-6 pb-6">
            <div className="pt-5 border-t border-border-color">
              <div className="flex items-center gap-2 mb-2">
                <LogOut size={14} className="text-red-500" />
                <span className="block text-sm font-medium text-text-primary">Session</span>
              </div>
              <button
                onClick={() => setConfirmLogout(true)}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-red-500 border border-red-500/50 hover:bg-red-500/10 transition-colors"
              >
                <LogOut size={16} />
                Log Out
              </button>
              <p className="mt-2 text-xs text-text-secondary">
                Revoke your session and return to the login screen.
              </p>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-4 border-t border-border-color bg-bg-base flex justify-end gap-3">
          <button 
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-text-secondary hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={handleSave}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-accent-primary text-white hover:bg-accent-primary-hover transition-colors disabled:opacity-50"
          >
            {success ? <Check size={16} /> : <Save size={16} />}
            {success ? 'Saved!' : 'Save Keys'}
          </button>
        </div>

      </div>
    </div>
  );
}
