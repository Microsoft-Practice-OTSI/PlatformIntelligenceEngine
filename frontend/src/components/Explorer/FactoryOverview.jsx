import React, { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  Workflow,
  Activity,
  Database,
  Link2,
  Timer,
  SlidersHorizontal,
  GitBranch,
  Trash2,
  Sparkles,
  MapPin,
  FolderGit2,
  Bot,
  AlertTriangle,
  CheckCircle2,
  Factory,
  ArrowLeft,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';

const STAT_CARDS = [
  { key: 'pipeline_count', label: 'Pipelines', description: 'Total No. of Pipelines', icon: Workflow, color: 'text-blue-600', bg: 'bg-blue-50 border border-blue-200/60' },
  { key: 'activity_count', label: 'Activities', description: 'Total number of activities across all pipelines', icon: Activity, color: 'text-sky-600', bg: 'bg-sky-50 border border-sky-200/60' },
  { key: 'dataset_count', label: 'Datasets', description: 'Total number of datasets defined in the factory', icon: Database, color: 'text-emerald-600', bg: 'bg-emerald-50 border border-emerald-200/60' },
  { key: 'linked_service_count', label: 'Linked Services', description: 'Total number of connection definitions to external data stores', icon: Link2, color: 'text-purple-600', bg: 'bg-purple-50 border border-purple-200/60' },
  { key: 'trigger_count', label: 'Triggers', description: 'Total number of schedule and event triggers', icon: Timer, color: 'text-amber-600', bg: 'bg-amber-50 border border-amber-200/60' },
  { key: 'global_parameters_count', label: 'Global Params', description: 'Factory-wide parameters referenced by pipelines', icon: SlidersHorizontal, color: 'text-indigo-600', bg: 'bg-indigo-50 border border-indigo-200/60' },
  { key: 'data_flow_count', label: 'Data Flows', description: 'Total number of mapping data flows', icon: GitBranch, color: 'text-teal-600', bg: 'bg-teal-50 border border-teal-200/60' },
  { key: 'orphan_count', label: 'Orphan Pipelines', description: 'Pipelines that are never triggered by any schedule or parent pipeline', icon: Trash2, color: 'text-rose-600', bg: 'bg-rose-50 border border-rose-200/60' },
];

const LIST_CONFIGS = {
  pipeline_count: {
    title: 'Pipelines',
    empty: 'No pipelines found',
    endpoint: (name) => `/factories/${encodeURIComponent(name)}/pipelines`,
    detailLink: (row) => `/pipeline/${encodeURIComponent(row.name)}`,
    columns: [
      { key: 'name', label: 'Name' },
      { key: 'folder', label: 'Folder', render: (v) => v || '—' },
      { key: 'description', label: 'Description', render: (v) => v || '—' },
      { key: 'activity_count', label: 'Activities' },
    ],
  },
  dataset_count: {
    title: 'Datasets',
    empty: 'No datasets found',
    endpoint: (name) => `/datasets?factory_name=${encodeURIComponent(name)}`,
    columns: [
      { key: 'name', label: 'Name' },
      { key: 'type', label: 'Type' },
      { key: 'linked_service', label: 'Linked Service' },
      { key: 'is_onprem', label: 'On-Prem', render: (v) => (v ? 'Yes' : 'No') },
    ],
  },
  linked_service_count: {
    title: 'Linked Services',
    empty: 'No linked services found',
    endpoint: (name) => `/linked-services?factory_name=${encodeURIComponent(name)}`,
    columns: [
      { key: 'name', label: 'Name' },
      { key: 'type', label: 'Type' },
      { key: 'connect_via_ir', label: 'Integration Runtime', render: (v) => v || '—' },
    ],
  },
  trigger_count: {
    title: 'Triggers',
    empty: 'No triggers found',
    endpoint: (name) => `/triggers?factory_name=${encodeURIComponent(name)}`,
    columns: [
      { key: 'name', label: 'Name' },
      { key: 'type', label: 'Type' },
      { key: 'runtime_state', label: 'State', render: (v) => v || '—' },
      { key: 'recurrence', label: 'Recurrence', render: (v) => (typeof v === 'string' ? v : JSON.stringify(v)) },
    ],
  },
  global_parameters_count: {
    title: 'Global Parameters',
    empty: 'No global parameters defined',
    endpoint: (name) => `/factories/${encodeURIComponent(name)}/global-parameters`,
    columns: [
      { key: 'name', label: 'Name' },
      { key: 'type', label: 'Type' },
      { key: 'value', label: 'Value', render: (v) => String(v ?? '') },
      { key: 'pipeline_ref', label: 'Reference', render: (v) => v || '—' },
    ],
  },
  orphan_count: {
    title: 'Orphan Pipelines',
    empty: 'No orphan pipelines',
    rows: (insights) => (insights?.orphan_pipelines || []).map((name) => ({ name })),
    columns: [{ key: 'name', label: 'Pipeline Name' }],
  },
};

function formatTimestamp(ts) {
  if (!ts) return 'Never';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return 'Never';
  }
}

function formatProviderLabel(provider) {
  if (!provider) return null;
  if (provider === 'deterministic' || provider === 'mock' || provider.includes('fallback')) {
    return 'Deterministic';
  }
  return provider;
}

function renderCell(column, value) {
  return column.render ? column.render(value) : String(value ?? '');
}

export default function FactoryOverview() {
  const navigate = useNavigate();
  const [factory, setFactory] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [activeList, setActiveList] = useState(null);
  const [listData, setListData] = useState([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState(null);

  const loadFactory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get('/factories');
      const list = data.factories || [];
      if (!list.length) {
        setError('No factory synced yet. Complete onboarding (login → select subscription → select factory) to view the overview dashboard.');
        setLoading(false);
        return;
      }

      const stored = localStorage.getItem('selected_factory');
      const active = list.find((f) => f.factory_name === stored)?.factory_name || list[0].factory_name;
      localStorage.setItem('selected_factory', active);

      const { data: summary } = await apiClient.get(`/factories/${encodeURIComponent(active)}/summary`);
      setFactory(summary);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load factory overview.');
    } finally {
      setLoading(false);
    }
  }, []);

  const generateInsights = useCallback(async () => {
    if (!factory) return;
    setInsightsLoading(true);
    setAiError(null);
    try {
      const model = localStorage.getItem('selected_model') || 'nvidia-nim';
      const { data } = await apiClient.post('/ai/insights', {
        factory_name: factory.factory_name,
        model,
      });
      setInsights(data);
    } catch (err) {
      setAiError(err.response?.data?.detail || err.message || 'Failed to generate AI insights.');
    } finally {
      setInsightsLoading(false);
    }
  }, [factory]);

  const openList = useCallback(async (card) => {
    const config = LIST_CONFIGS[card.key];
    if (!config) return;
    sessionStorage.setItem('factory_active_list', card.key);
    setActiveList(card.key);
    setListLoading(true);
    setListError(null);
    try {
      if (config.rows) {
        setListData(config.rows(insights));
      } else {
        const { data } = await apiClient.get(config.endpoint(factory.factory_name));
        setListData(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      setListError(err.response?.data?.detail || err.message || 'Failed to load list.');
      setListData([]);
    } finally {
      setListLoading(false);
    }
  }, [factory, insights]);

  const closeList = () => {
    sessionStorage.removeItem('factory_active_list');
    setActiveList(null);
    setListData([]);
    setListError(null);
  };

  useEffect(() => {
    loadFactory();
  }, [loadFactory]);

  useEffect(() => {
    if (factory && !insights) generateInsights();
  }, [factory, insights, generateInsights]);

  useEffect(() => {
    if (!factory) return;
    const pending = sessionStorage.getItem('factory_active_list');
    if (pending && LIST_CONFIGS[pending]) {
      sessionStorage.removeItem('factory_active_list');
      openList({ key: pending });
    }
  }, [factory, openList]);

  const handleRefresh = async () => {
    if (!factory) return;
    setRefreshing(true);
    setError(null);
    setActiveList(null);
    try {
      await apiClient.post(`/factories/${encodeURIComponent(factory.factory_name)}/refresh`);
      await loadFactory();
      setInsights(null);
      generateInsights();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to refresh factory.');
    } finally {
      setRefreshing(false);
    }
  };

  const insightItems = [];
  if (insights?.duplicate_parameters?.length) {
    const sample = insights.duplicate_parameters[0].names.join(', ');
    insightItems.push({
      icon: AlertTriangle,
      tone: 'text-status-warning',
      text: `${insights.duplicate_parameters.length} duplicate global parameter value(s) detected: ${sample}${insights.duplicate_parameters.length > 1 ? ', …' : ''} share the same value.`,
    });
  }
  if (insights?.orphan_count > 0) {
    insightItems.push({
      icon: AlertTriangle,
      tone: 'text-status-warning',
      text: `${insights.orphan_count} orphan pipeline(s) are never triggered by any schedule or parent pipeline.`,
    });
  }
  if (insights?.zero_retry_count > 0) {
    insightItems.push({
      icon: AlertTriangle,
      tone: 'text-status-warning',
      text: `${insights.zero_retry_count} fragile activity(ies) have no retry policy configured.`,
    });
  }
  if (insights?.peak_concurrency_count > 1) {
    insightItems.push({
      icon: AlertTriangle,
      tone: 'text-status-error',
      text: `Peak schedule concurrency of ${insights.peak_concurrency_count} pipeline(s) at ${insights.peak_hour || 'unknown'} hour.`,
    });
  }
  if (insights && !insightItems.length) {
    insightItems.push({
      icon: CheckCircle2,
      tone: 'text-status-success',
      text: 'No obvious risks detected: no duplicate global parameter values, orphan pipelines, zero-retry activities, or concurrency collisions.',
    });
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-bg-base">
        <div className="flex items-center gap-2 text-text-secondary">
          <RefreshCw className="animate-spin" size={20} />
          <span>Loading factory overview...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-bg-base p-8">
        <AlertTriangle size={48} className="text-status-warning mb-4" />
        <p className="text-text-secondary text-center max-w-lg">{error}</p>
      </div>
    );
  }

  if (!factory) {
    return null;
  }

  const activeConfig = activeList ? LIST_CONFIGS[activeList] : null;

  return (
    <div className="flex flex-col h-full bg-transparent overflow-y-auto">
      <div className="p-6 border-b border-slate-200/80 bg-white/80 backdrop-blur-md shadow-xs">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200/80 flex items-center justify-center shrink-0 shadow-xs">
              <Factory size={20} className="text-accent-primary" />
            </div>
            <div>
              <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                Factory: <span className="text-accent-primary">{factory.factory_name}</span>
              </h2>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs mt-1.5">
                <span className="flex items-center gap-1.5 font-semibold text-slate-700">
                  <FolderGit2 size={13} className="text-slate-500" /> {factory.resource_group}
                </span>
                <span className="flex items-center gap-1.5 font-semibold text-slate-700">
                  <MapPin size={13} className="text-slate-500" /> {factory.location}
                </span>
                <span className="flex items-center gap-1.5 font-semibold text-slate-700">
                  <RefreshCw size={13} className="text-slate-500" /> Refreshed: {formatTimestamp(factory.last_refreshed_at)}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-300 text-xs font-bold text-slate-900 bg-white hover:bg-slate-50 transition-all shadow-xs disabled:opacity-50 shrink-0"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin text-accent-primary' : 'text-slate-600'} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6 max-w-6xl mx-auto w-full">
        {activeConfig ? (
          <section>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <button onClick={closeList} className="p-1 rounded-lg hover:bg-slate-100 transition-colors" title="Back to overview">
                  <ArrowLeft size={18} className="text-slate-700" />
                </button>
                {activeConfig.title} ({listData.length})
              </h3>
              <button
                onClick={closeList}
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-slate-300 text-xs font-bold text-slate-700 hover:bg-slate-100 hover:text-slate-900 transition-colors shadow-xs"
              >
                Back to Overview
              </button>
            </div>

            {listLoading ? (
              <div className="flex items-center gap-2 text-slate-700 font-medium text-sm py-8 justify-center">
                <RefreshCw className="animate-spin text-accent-primary" size={16} />
                Loading {activeConfig.title.toLowerCase()}...
              </div>
            ) : listError ? (
              <div className="p-6 bg-white border border-amber-200 rounded-2xl text-amber-800 text-sm font-medium">
                {listError}
              </div>
            ) : listData.length === 0 ? (
              <div className="p-6 bg-white border border-slate-200 rounded-2xl text-slate-700 text-sm font-medium">
                {activeConfig.empty}
              </div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card">
                <table className="w-full text-left border-collapse text-sm text-text-primary">
                  <thead>
                    <tr className="bg-slate-100/80 border-b border-slate-200">
                      {activeConfig.columns.map((col) => (
                        <th key={col.key} className="px-4 py-3 font-bold text-xs text-slate-700 uppercase tracking-wider">{col.label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {listData.map((row, i) => {
                      const detailHref = activeConfig.detailLink ? activeConfig.detailLink(row) : null;
                      return (
                        <tr
                          key={i}
                          onClick={detailHref ? () => navigate(detailHref) : undefined}
                          title={detailHref ? 'View pipeline detail' : undefined}
                          className={`border-b border-border-color last:border-0 transition-colors ${
                            detailHref ? 'cursor-pointer hover:bg-slate-50/90' : ''
                          }`}
                        >
                          {activeConfig.columns.map((col) => (
                            <td
                              key={col.key}
                              className={`px-4 py-3 text-slate-700 ${col.key === 'name' && detailHref ? 'font-semibold text-accent-primary' : ''}`}
                            >
                              {renderCell(col, row[col.key])}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {STAT_CARDS.map((card) => {
                const config = LIST_CONFIGS[card.key];
                const isOrphan = card.key === 'orphan_count';
                const orphanPending = isOrphan && insights == null;
                const value = isOrphan
                  ? insights?.orphan_count ?? 0
                  : factory[card.key] ?? 0;
                return (
                  <div
                    key={card.key}
                    onClick={config && !orphanPending ? () => openList(card) : undefined}
                    className={`relative group rounded-2xl border border-slate-200/80 bg-white/90 backdrop-blur-md p-5 flex flex-col gap-3 transition-all ${
                      config && !orphanPending
                        ? 'cursor-pointer hover:border-blue-400 hover:shadow-[0_12px_28px_-6px_rgba(37,99,235,0.12),0_4px_12px_-2px_rgba(15,23,42,0.04)] hover:-translate-y-0.5'
                        : 'cursor-default'
                    } ${orphanPending ? 'opacity-70' : ''} shadow-[0_4px_16px_rgba(15,23,42,0.03)]`}
                  >
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-xs px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-md">
                      {card.description}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                        {card.label}
                      </span>
                      <span className={`w-8 h-8 rounded-lg ${card.bg} flex items-center justify-center shrink-0`}>
                        <card.icon size={16} className={card.color} />
                      </span>
                    </div>
                    <div className="flex items-end justify-between">
                      {orphanPending ? (
                        <span className="flex items-center gap-2 text-sm text-slate-700 font-medium">
                          <RefreshCw className="animate-spin" size={18} />
                          Loading...
                        </span>
                      ) : (
                        <span className="text-3xl font-black text-slate-900 tracking-tight">{value}</span>
                      )}
                      {config && !orphanPending && (
                        <span className="text-xs font-bold text-accent-primary opacity-0 group-hover:opacity-100 transition-opacity">
                          View →
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <section>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-extrabold text-slate-900 flex items-center gap-2">
                  <Sparkles size={18} className="text-accent-secondary" /> Factory Insights
                </h3>
                <button
                  onClick={generateInsights}
                  disabled={insightsLoading}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-300 text-xs font-bold text-slate-700 bg-white hover:bg-slate-50 hover:text-slate-900 transition-all shadow-xs disabled:opacity-50"
                >
                  <RefreshCw size={13} className={insightsLoading ? 'animate-spin text-accent-primary' : ''} />
                  Regenerate
                </button>
              </div>

              {insightsLoading && !insights ? (
                <div className="p-6 bg-white border border-slate-200 rounded-2xl flex items-center gap-2 text-slate-700 font-medium text-sm shadow-xs">
                  <RefreshCw className="animate-spin text-accent-primary" size={15} />
                  Generating factory insights...
                </div>
              ) : (
                <>
                  <div className="grid gap-2.5 mb-4">
                    {insightItems.map((item, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 p-3.5 rounded-xl bg-white border border-slate-200 text-sm shadow-xs"
                      >
                        <item.icon size={16} className={`mt-0.5 shrink-0 ${item.tone}`} />
                        <span className="text-slate-900 font-medium leading-relaxed">{item.text}</span>
                      </div>
                    ))}
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2 text-xs font-bold text-slate-700 uppercase tracking-wider">
                        <Bot size={15} className="text-emerald-600" /> AI Narrative
                      </div>
                      {insights?.provider && (
                        <span className="text-xs font-bold text-slate-700 bg-slate-100 border border-slate-300 rounded-md px-2 py-0.5">
                          {formatProviderLabel(insights.provider)}
                        </span>
                      )}
                    </div>
                    {insightsLoading ? (
                      <div className="flex items-center gap-2 text-slate-700 font-medium text-sm py-2">
                        <RefreshCw className="animate-spin text-accent-primary" size={15} />
                        Generating narrative summary...
                      </div>
                    ) : aiError ? (
                      <p className="text-amber-800 font-medium text-sm">
                        {aiError} — deterministic insights above remain valid.
                      </p>
                    ) : (
                      <p className="text-sm text-slate-900 font-medium whitespace-pre-wrap leading-relaxed">
                        {insights?.narrative}
                      </p>
                    )}
                  </div>
                </>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
