import React, { useState, useEffect } from 'react';
import { Server, Database, FolderOpen, Loader2, CheckCircle2 } from 'lucide-react';
import { apiClient } from '../../api/client';

export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(0);
  const [subscriptions, setSubscriptions] = useState([]);
  const [factories, setFactories] = useState([]);
  
  const [selectedSub, setSelectedSub] = useState(null);
  const [selectedFactory, setSelectedFactory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [authUrl, setAuthUrl] = useState(null);

  // Listen for postMessage from auth popup (fast-path)
  useEffect(() => {
    const handleMessage = async (event) => {
      if (event.data?.type === 'PIE_AUTH_SUCCESS' && event.data.sessionToken) {
        localStorage.setItem('x_session_token', event.data.sessionToken);
        // Always proceed to subscription selection after login
        setStep(1);
        fetchSubscriptions();
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  useEffect(() => {
    // Check if already authenticated
    const checkAuth = async () => {
      if (localStorage.getItem('x_session_token')) {
        try {
          await apiClient.get('/auth/session');
          // Always proceed to subscription selection to allow factory re-selection
          setStep(1);
          fetchSubscriptions();
        } catch(e) {
          localStorage.removeItem('x_session_token');
          setStep(0);
        }
      } else {
        setStep(0);
      }
    };
    checkAuth();
  }, []);

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.post('/auth/login');
      setAuthUrl(data.login_url);
      window.open(data.login_url, '_blank', 'width=600,height=700');

      const pollUrl = data.poll_url.replace('http://localhost:8000/api/v1', '');
      
      const pollTimer = setInterval(async () => {
        try {
          const pollRes = await apiClient.get(pollUrl);
          if (pollRes.data.status === 'complete') {
            clearInterval(pollTimer);
            localStorage.setItem('x_session_token', pollRes.data.session_token);
            // Always proceed to subscription selection
            setLoading(false);
            setStep(1);
            fetchSubscriptions();
          } else if (pollRes.data.status === 'error') {
            clearInterval(pollTimer);
            setLoading(false);
            setError(`Auth failed: ${pollRes.data.error || pollRes.data.message}`);
          }
        } catch (e) {
          if (e.response && e.response.status === 404) {
            clearInterval(pollTimer);
            setLoading(false);
          }
        }
      }, 2000);
    } catch (error) {
      setLoading(false);
      setError('Failed to initiate login. Is the backend running?');
    }
  };

  const fetchSubscriptions = async () => {
    setLoading(true);
    try {
      const { data } = await apiClient.get('/subscriptions');
      setSubscriptions(data.subscriptions || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchFactories = async (subId) => {
    setLoading(true);
    try {
      const { data } = await apiClient.post('/subscriptions/factories', [subId]);
      setFactories(data.factories || []);
    } catch (e) {
      setError('Failed to fetch factories from PIE backend.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubSelect = (sub) => {
    setSelectedSub(sub);
    setStep(2);
    fetchFactories(sub.subscription_id);
  };

  const handleFactorySelect = async (factory) => {
    setSelectedFactory(factory);
    setStep(3);
    
    // Sync the factory
    try {
      setLoading(true);
      await apiClient.post(`/discovery/sync`, {
        subscription_ids: [selectedSub.subscription_id],
        factory_names: [factory.factory_name],
        factory_resource_groups: {
          [factory.factory_name]: factory.resource_group
        },
        force_refresh: true
      });
      // Save selected factory to localStorage for ChatContainer to use
      localStorage.setItem('selected_factory', factory.factory_name);
      setTimeout(() => {
        setLoading(false);
        setStep(4);
      }, 1500); // UI delay for polish
    } catch (e) {
      setError('Failed to sync factory metadata.');
      setLoading(false);
      setStep(2);
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center bg-bg-base p-8">
      <div className="max-w-2xl w-full bg-bg-surface border border-border-color rounded-xl shadow-2xl p-8 relative overflow-hidden">
        
        {/* Progress Bar */}
        <div className="absolute top-0 left-0 w-full h-1 bg-bg-surface-elevated">
          <div className="h-full bg-accent-primary transition-all duration-500" style={{ width: `${(step / 4) * 100}%` }} />
        </div>

        <div className="mb-8 text-center">
          <h2 className="text-2xl font-semibold text-text-primary mb-2">Configure Your Workspace</h2>
          <p className="text-text-secondary">Select the environment you want to explore with PIE.</p>
        </div>

        {error && (
          <div className="p-4 mb-6 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm">
            {error}
          </div>
        )}

        {/* Step 0: Authentication */}
        {step === 0 && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500 flex flex-col items-center py-6">
            <div className="w-16 h-16 rounded-full bg-accent-primary/20 text-accent-primary flex items-center justify-center mb-4">
              <Server size={32} />
            </div>
            <h3 className="text-xl font-medium mb-2">Connect Azure Environment</h3>
            <p className="text-text-secondary text-center mb-8 max-w-sm">
              Please authenticate with your Microsoft account so PIE can discover your data engineering assets.
            </p>
            
            <button 
              onClick={handleLogin}
              disabled={loading}
              className="px-6 py-3 bg-accent-primary hover:bg-accent-primary-hover text-white rounded-lg font-medium transition-colors w-full flex justify-center items-center gap-2"
            >
              {loading ? <Loader2 className="animate-spin" size={18} /> : null}
              {loading ? 'Waiting for authentication...' : 'Login with Microsoft'}
            </button>

            {authUrl && (
              <a href={authUrl} target="_blank" rel="noreferrer" className="text-sm text-accent-primary hover:underline mt-4">
                Click here if the login window didn't open
              </a>
            )}
          </div>
        )}

        {/* Step 1: Subscriptions */}
        {step === 1 && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <h3 className="text-lg font-medium flex items-center gap-2 mb-4">
              <Server className="text-accent-primary" size={20} />
              1. Select Azure Subscription
            </h3>
            {loading ? (
              <div className="flex items-center justify-center p-8"><Loader2 className="animate-spin text-accent-primary" /></div>
            ) : (
              <div className="grid gap-3">
                {subscriptions.map(sub => (
                  <button 
                    key={sub.subscription_id}
                    onClick={() => handleSubSelect(sub)}
                    className="p-4 rounded-lg border border-border-color bg-bg-base hover:border-accent-primary hover:bg-bg-surface-elevated transition-all flex items-center justify-between text-left group"
                  >
                    <div>
                      <div className="font-medium">{sub.subscription_name}</div>
                    </div>
                    <div className="w-6 h-6 rounded-full border border-border-color group-hover:border-accent-primary flex items-center justify-center">
                       <div className="w-3 h-3 rounded-full bg-accent-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Factories */}
        {step === 2 && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
             <div className="flex items-center gap-2 mb-6 cursor-pointer text-text-secondary hover:text-text-primary" onClick={() => setStep(1)}>
                ← Back to Subscriptions
             </div>
            <h3 className="text-lg font-medium flex items-center gap-2 mb-3">
              <Database className="text-accent-primary" size={20} />
              2. Select Data Factory
            </h3>
            <div className="grid grid-cols-[auto_auto_1fr] items-center gap-x-2 mb-4 px-3 py-2 rounded-lg bg-bg-base border border-border-color">
              <div className="flex items-center gap-2">
                <Server size={14} className="text-status-success shrink-0" />
                <span className="text-sm text-text-secondary">Subscription</span>
              </div>
              <span className="text-text-secondary">:</span>
              <span className="text-sm font-medium text-status-success">{selectedSub?.subscription_name}</span>
            </div>
            {loading ? (
              <div className="flex items-center justify-center p-8"><Loader2 className="animate-spin text-accent-primary" /></div>
            ) : (
              <div className="grid gap-3">
                {factories.map(f => (
                  <button 
                    key={f.factory_name}
                    onClick={() => handleFactorySelect(f)}
                    className="p-4 rounded-lg border border-border-color bg-bg-base hover:border-accent-primary hover:bg-bg-surface-elevated transition-all flex items-center justify-between text-left group"
                  >
                    <div className="grid grid-cols-[auto_auto_1fr] items-center gap-x-2 gap-y-1.5">
                      <div className="flex items-center gap-2">
                        <Database size={14} className="text-accent-primary shrink-0" />
                        <span className="text-sm text-text-secondary">Data Factory</span>
                      </div>
                      <span className="text-text-secondary">:</span>
                      <span className="text-sm font-medium text-accent-primary">{f.factory_name}</span>

                      <div className="flex items-center gap-2">
                        <FolderOpen size={14} className="text-status-info shrink-0" />
                        <span className="text-sm text-text-secondary">Resource Group</span>
                      </div>
                      <span className="text-text-secondary">:</span>
                      <span className="text-sm font-medium text-status-info">{f.resource_group}</span>
                    </div>
                    <div className="w-6 h-6 rounded-full border border-border-color group-hover:border-accent-primary flex items-center justify-center">
                       <div className="w-3 h-3 rounded-full bg-accent-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </button>
                ))}
                {factories.length === 0 && <div className="text-text-secondary text-sm">No factories found.</div>}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Syncing */}
        {step === 3 && (
          <div className="py-12 flex flex-col items-center justify-center animate-in fade-in duration-500">
             <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full border-4 border-bg-surface-elevated border-t-accent-primary animate-spin" />
                <Database className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-text-secondary" size={20} />
             </div>
             <h3 className="text-xl font-medium mb-2">Syncing {selectedFactory?.factory_name}</h3>
             <p className="text-text-secondary text-center max-w-sm">
               Extracting pipelines, mapping datasets, and building the in-memory knowledge graph...
             </p>
          </div>
        )}

        {/* Step 4: Complete */}
        {step === 4 && (
          <div className="py-12 flex flex-col items-center justify-center animate-in zoom-in duration-500">
             <div className="w-16 h-16 rounded-full bg-status-success/20 flex items-center justify-center mb-6 text-status-success">
                <CheckCircle2 size={32} />
             </div>
             <h3 className="text-xl font-medium mb-2">Ready to Explore</h3>
             <p className="text-text-secondary text-center max-w-sm mb-8">
               Your workspace is synced and ready.
             </p>
             <button onClick={onComplete} className="px-6 py-3 bg-accent-primary hover:bg-accent-primary-hover text-white rounded-lg font-medium transition-colors w-full">
               Enter Workspace
             </button>
          </div>
        )}

      </div>
    </div>
  );
}
