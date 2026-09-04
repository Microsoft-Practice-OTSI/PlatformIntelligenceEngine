import React, { useState, useEffect } from 'react';
import { Server, Database, FolderOpen, Loader2, CheckCircle2, LogOut, User, ArrowLeft } from 'lucide-react';
import { apiClient } from '../../api/client';

export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(0);
  const [subscriptions, setSubscriptions] = useState([]);
  const [factories, setFactories] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  
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
        try {
          const { data } = await apiClient.get('/auth/session');
          setCurrentUser(data);
        } catch (e) {}
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
          const { data } = await apiClient.get('/auth/session');
          setCurrentUser(data);
          // Always proceed to subscription selection to allow factory re-selection
          setStep(1);
          fetchSubscriptions();
        } catch(e) {
          localStorage.removeItem('x_session_token');
          setCurrentUser(null);
          setStep(0);
        }
      } else {
        setCurrentUser(null);
        setStep(0);
      }
    };
    checkAuth();
  }, []);

  const handleSwitchAccount = async () => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.post('/auth/logout');
    } catch (e) {
      console.warn('Logout request failed:', e);
    } finally {
      localStorage.removeItem('x_session_token');
      localStorage.removeItem('selected_factory');
      setCurrentUser(null);
      setSelectedSub(null);
      setSelectedFactory(null);
      setSubscriptions([]);
      setFactories([]);
      setStep(0);
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.post('/auth/login');
      setAuthUrl(data.login_url);

      const width = 600;
      const height = 700;
      const dualScreenLeft = window.screenLeft !== undefined ? window.screenLeft : window.screenX;
      const dualScreenTop = window.screenTop !== undefined ? window.screenTop : window.screenY;
      const screenW = window.innerWidth || document.documentElement.clientWidth || screen.width;
      const screenH = window.innerHeight || document.documentElement.clientHeight || screen.height;
      const left = Math.max(0, Math.floor(dualScreenLeft + (screenW - width) / 2));
      const top = Math.max(0, Math.floor(dualScreenTop + (screenH - height) / 2));

      window.open(
        data.login_url,
        '_blank',
        `width=${width},height=${height},top=${top},left=${left},scrollbars=yes,status=yes`
      );

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
    <div className="relative min-h-screen w-full flex items-center justify-center overflow-hidden glass-canvas p-6">
      {/* Ambient glowing glassy light-blue orbs */}
      <div className="absolute top-[-10%] left-[-8%] w-[560px] h-[560px] rounded-full bg-gradient-to-tr from-sky-300/30 to-blue-400/20 blur-[110px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-8%] w-[600px] h-[600px] rounded-full bg-gradient-to-bl from-blue-300/30 to-indigo-300/20 blur-[120px] pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[650px] h-[650px] rounded-full bg-sky-200/25 blur-[130px] pointer-events-none" />
      
      {/* Subtle glassy grid overlay */}
      <div className="absolute inset-0 bg-[radial-gradient(#0284c7_1px,transparent_1px)] [background-size:28px_28px] opacity-[0.06] pointer-events-none" />

      {/* Main Glassy Card Container */}
      <div className={`w-full ${step === 0 ? 'max-w-[450px]' : 'max-w-xl'} glass-card-premium rounded-[28px] p-8 md:p-10 relative overflow-hidden transition-all duration-300 z-10`}>
        
        {/* Progress Bar (Only visible during workspace setup steps) */}
        {step > 0 && (
          <div className="absolute top-0 left-0 w-full h-1.5 bg-slate-100">
            <div className="h-full bg-gradient-to-r from-accent-primary to-accent-secondary transition-all duration-500" style={{ width: `${(step / 4) * 100}%` }} />
          </div>
        )}

        {/* Step 0: Clean Centered Login UI (matching screenshot) */}
        {step === 0 ? (
          <div className="text-center animate-in fade-in zoom-in-95 duration-300">
            {currentUser ? (
              /* If already authenticated, show the exact success layout from screenshot */
              <>
                <div className="w-[64px] h-[64px] mx-auto mb-4 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-center font-bold text-2xl text-emerald-600 shadow-[0_4px_14px_rgba(5,150,105,0.12)]">
                  ✓
                </div>
                <h1 className="text-xl font-bold text-slate-900 mb-2 tracking-tight">
                  Authenticated Successfully
                </h1>
                <p className="text-base font-bold text-slate-900 mb-0.5">
                  {currentUser?.claims?.display_name || 'Active User'}
                </p>
                <p className="text-xs font-medium text-slate-600 mb-3 break-all">
                  {currentUser?.user_id}
                </p>
                <div className="mb-4">
                  <span className="inline-block px-3.5 py-1 bg-sky-50 border border-sky-200 text-accent-primary text-xs font-semibold rounded-full shadow-2xs">
                    Session Connected
                  </span>
                </div>
                <p className="text-xs text-slate-600 font-medium leading-relaxed mb-6">
                  Connected to Microsoft Azure. Select your workspace to start exploring.
                </p>

                <div className="space-y-2.5">
                  <button
                    onClick={() => { setStep(1); fetchSubscriptions(); }}
                    className="w-full py-3 px-5 bg-accent-primary hover:bg-accent-hover text-white font-bold text-sm rounded-xl shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <span>Continue to Subscriptions</span>
                    <span>→</span>
                  </button>
                  <button
                    onClick={handleSwitchAccount}
                    className="w-full py-2.5 px-4 bg-white/90 hover:bg-white border border-slate-300 text-slate-700 font-semibold text-xs rounded-xl shadow-2xs transition-colors cursor-pointer"
                  >
                    Switch to Another Account
                  </button>
                </div>
              </>
            ) : (
              /* Unauthenticated clean login card */
              <>
                <div className="w-[64px] h-[64px] mx-auto mb-5 rounded-2xl bg-gradient-to-b from-sky-50 to-blue-100/70 border border-blue-200/80 flex items-center justify-center shadow-[0_4px_14px_rgba(14,116,144,0.1)]">
                  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4C9.11 4 6.6 5.64 5.35 8.04C2.34 8.36 0 10.91 0 14C0 17.31 2.69 20 6 20H19C21.76 20 24 17.76 24 15C24 12.36 21.95 10.22 19.35 10.04Z" fill="#2563eb"/>
                  </svg>
                </div>

                <h1 className="text-xl font-bold text-slate-900 mb-1.5 tracking-tight">
                  Sign in to Ad-PIE
                </h1>
                
                <p className="text-xs font-medium text-slate-600 mb-3.5">
                  Azure Data — Platform Intelligence Engine
                </p>

                <div className="mb-6">
                  <span className="inline-block px-3.5 py-1 bg-sky-50/90 backdrop-blur-sm border border-sky-200 text-accent-primary text-xs font-semibold rounded-full shadow-2xs">
                    Enterprise Identity • Microsoft Entra
                  </span>
                </div>

                {error && (
                  <div className="p-3.5 mb-5 bg-red-50/90 border border-red-200 rounded-xl text-red-600 text-xs font-medium text-left">
                    {error}
                  </div>
                )}

                <button 
                  onClick={handleLogin}
                  disabled={loading}
                  className="w-full py-3.5 px-5 bg-white/95 hover:bg-white border border-slate-200 hover:border-blue-300 text-slate-900 font-bold rounded-2xl shadow-xs hover:shadow-[0_8px_25px_rgba(37,99,235,0.12)] transition-all flex items-center justify-center gap-3 cursor-pointer disabled:opacity-60 mb-4"
                >
                  {loading ? (
                    <Loader2 className="animate-spin text-accent-primary" size={18} />
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 21 21">
                      <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
                      <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
                      <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
                      <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
                    </svg>
                  )}
                  <span className="text-sm">{loading ? 'Waiting for authentication...' : 'Login with Microsoft'}</span>
                </button>

                <p className="text-xs text-slate-500 font-medium leading-relaxed">
                  Authenticate with your Microsoft account to discover subscriptions, factories, and pipeline lineage.
                </p>

                {authUrl && (
                  <a href={authUrl} target="_blank" rel="noreferrer" className="inline-block text-xs font-semibold text-accent-primary hover:underline mt-4">
                    Popup blocked? Click here to open login window
                  </a>
                )}
              </>
            )}
          </div>
        ) : (
          /* Steps 1, 2, 3, 4 Header */
          <div className="mb-6 text-center">
            <h2 className="text-xl font-bold text-slate-900 mb-1">Configure Your Workspace</h2>
            <p className="text-slate-600 text-xs font-medium">Select the environment you want to explore with PIE.</p>
          </div>
        )}

        {error && step > 0 && (
          <div className="p-3.5 mb-5 bg-red-50 border border-red-200 rounded-xl text-red-600 text-xs font-medium">
            {error}
          </div>
        )}

        {/* Step 1: Subscriptions */}
        {step === 1 && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Connected Account & Switch Account Option */}
            <div className="flex items-center justify-between p-3.5 rounded-2xl bg-sky-50/70 backdrop-blur-sm border border-sky-200/70 shadow-2xs mb-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-accent-primary to-accent-secondary text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                  {currentUser?.claims?.display_name?.charAt(0) || currentUser?.user_id?.charAt(0) || <User size={14} />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold text-slate-900 truncate">
                    {currentUser?.claims?.display_name || currentUser?.user_id || 'Connected Account'}
                  </div>
                  <div className="text-[11px] text-slate-500 font-medium truncate">
                    {currentUser?.user_id}
                  </div>
                </div>
              </div>

              <button
                onClick={handleSwitchAccount}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 bg-white/95 hover:bg-red-50 hover:border-red-300 hover:text-red-700 text-xs font-bold text-slate-700 transition-colors shadow-xs shrink-0 cursor-pointer"
                title="Sign out and log into another Microsoft account"
              >
                <LogOut size={13} />
                <span>Switch Account</span>
              </button>
            </div>

            <h3 className="text-base font-bold flex items-center gap-2 mb-4 text-slate-900">
              <Server className="text-accent-primary" size={18} />
              1. Select Azure Subscription
            </h3>
            {loading ? (
              <div className="flex items-center justify-center p-8"><Loader2 className="animate-spin text-accent-primary" /></div>
            ) : (
              <div className="grid gap-2.5">
                {subscriptions.map(sub => (
                  <button 
                    key={sub.subscription_id}
                    onClick={() => handleSubSelect(sub)}
                    className="p-4 rounded-2xl glass-tile flex items-center justify-between text-left group cursor-pointer"
                  >
                    <div>
                      <div className="font-bold text-sm text-slate-900">{sub.subscription_name}</div>
                    </div>
                    <div className="w-5 h-5 rounded-full border border-slate-300 group-hover:border-accent-primary flex items-center justify-center">
                       <div className="w-2.5 h-2.5 rounded-full bg-accent-primary opacity-0 group-hover:opacity-100 transition-opacity" />
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
             <div className="flex items-center justify-between mb-4">
               <button 
                 onClick={() => setStep(1)} 
                 className="flex items-center gap-1.5 text-xs font-bold text-slate-700 hover:text-accent-primary transition-colors cursor-pointer"
               >
                 <ArrowLeft size={14} />
                 <span>Back to Subscriptions</span>
               </button>

               <button
                 onClick={handleSwitchAccount}
                 disabled={loading}
                 className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 bg-white/95 hover:bg-red-50 hover:border-red-300 hover:text-red-700 text-xs font-bold text-slate-700 transition-colors shadow-xs shrink-0 cursor-pointer"
                 title="Sign out and log into another Microsoft account"
               >
                 <LogOut size={13} />
                 <span>Switch Account</span>
               </button>
             </div>

            <h3 className="text-base font-bold flex items-center gap-2 mb-3 text-slate-900">
              <Database className="text-accent-primary" size={18} />
              2. Select Data Factory
            </h3>
            <div className="grid grid-cols-[auto_auto_1fr] items-center gap-x-2 mb-4 px-3.5 py-2.5 rounded-2xl bg-sky-50/70 backdrop-blur-sm border border-sky-200/70">
              <div className="flex items-center gap-1.5">
                <Server size={13} className="text-emerald-600 shrink-0" />
                <span className="text-xs font-semibold text-slate-700">Subscription</span>
              </div>
              <span className="text-slate-400">:</span>
              <span className="text-xs font-bold text-emerald-800">{selectedSub?.subscription_name}</span>
            </div>
            {loading ? (
              <div className="flex items-center justify-center p-8"><Loader2 className="animate-spin text-accent-primary" /></div>
            ) : (
              <div className="grid gap-2.5">
                {factories.map(f => (
                  <button 
                    key={f.factory_name}
                    onClick={() => handleFactorySelect(f)}
                    className="p-4 rounded-2xl glass-tile flex items-center justify-between text-left group cursor-pointer"
                  >
                    <div className="grid grid-cols-[auto_auto_1fr] items-center gap-x-2.5 gap-y-1.5">
                      <div className="flex items-center gap-1.5">
                        <Database size={13} className="text-accent-primary shrink-0" />
                        <span className="text-xs font-semibold text-slate-700">Data Factory</span>
                      </div>
                      <span className="text-slate-400">:</span>
                      <span className="text-xs font-bold text-accent-primary">{f.factory_name}</span>

                      <div className="flex items-center gap-1.5">
                        <FolderOpen size={13} className="text-sky-600 shrink-0" />
                        <span className="text-xs font-semibold text-slate-700">Resource Group</span>
                      </div>
                      <span className="text-slate-400">:</span>
                      <span className="text-xs font-bold text-slate-900">{f.resource_group}</span>
                    </div>
                    <div className="w-5 h-5 rounded-full border border-slate-300 group-hover:border-accent-primary flex items-center justify-center">
                       <div className="w-2.5 h-2.5 rounded-full bg-accent-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </button>
                ))}
                {factories.length === 0 && <div className="text-slate-700 text-sm font-medium">No factories found.</div>}
              </div>
            )}
          </div>
        )}



        {/* Step 3: Syncing */}
        {step === 3 && (
          <div className="py-12 flex flex-col items-center justify-center animate-in fade-in duration-500">
             <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full border-4 border-slate-100 border-t-accent-primary animate-spin" />
                <Database className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-accent-primary" size={20} />
             </div>
             <h3 className="text-xl font-extrabold text-slate-900 mb-2">Syncing {selectedFactory?.factory_name}</h3>
             <p className="text-slate-700 text-center max-w-sm text-sm font-medium leading-relaxed">
               Extracting pipelines, mapping datasets, and building the in-memory knowledge graph...
             </p>
          </div>
        )}

        {/* Step 4: Complete */}
        {step === 4 && (
          <div className="py-12 flex flex-col items-center justify-center animate-in zoom-in duration-500">
             <div className="w-16 h-16 rounded-2xl bg-emerald-50 border border-emerald-300 flex items-center justify-center mb-6 text-emerald-600 shadow-sm">
                <CheckCircle2 size={32} />
             </div>
             <h3 className="text-xl font-extrabold text-slate-900 mb-2">Ready to Explore</h3>
             <p className="text-slate-700 text-center max-w-sm mb-8 text-sm font-medium">
               Your workspace is synced and ready.
             </p>
             <button onClick={onComplete} className="px-6 py-3 bg-accent-primary hover:bg-accent-hover text-white rounded-xl font-semibold transition-all w-full shadow-sm">
               Enter Workspace
             </button>
          </div>
        )}

      </div>
    </div>
  );
}
