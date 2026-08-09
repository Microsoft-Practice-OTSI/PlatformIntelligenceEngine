import React, { useState, useEffect } from 'react';
import { X, Save, Key, Check } from 'lucide-react';
import { apiClient } from '../../api/client';

export default function SettingsModal({ isOpen, onClose }) {
  const [keys, setKeys] = useState({
    google: '',
    azureEndpoint: '',
    azureKey: '',
    nvidia: ''
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchKeys();
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

  if (!isOpen) return null;

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
