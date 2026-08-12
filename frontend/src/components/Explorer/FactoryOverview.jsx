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
  { key: 'pipeline_count', label: 'Pipelines', description: 'Total No. of Pipelines', icon: Workflow, color: 'text-accent-primary', bg: 'bg-accent-primary/10' },
  { key: 'activity_count', label: 'Activities', description: 'Total number of activities across all pipelines', icon: Activity, color: 'text-status-info', bg: 'bg-status-info/10' },
  { key: 'dataset_count', label: 'Datasets', description: 'Total number of datasets defined in the factory', icon: Database, color: 'text-status-success', bg: 'bg-status-success/10' },
  { key: 'linked_service_count', label: 'Linked Services', description: 'Total number of connection definitions to external data stores', icon: Link2, color: 'text-accent-secondary', bg: 'bg-accent-secondary/10' },
  { key: 'trigger_count', label: 'Triggers', description: 'Total number of schedule and event triggers', icon: Timer, color: 'text-status-warning', bg: 'bg-status-warning/10' },
  { key: 'global_parameters_count', label: 'Global Params', description: 'Factory-wide parameters referenced by pipelines', icon: SlidersHorizontal, color: 'text-accent-primary', bg: 'bg-accent-primary/10' },
  { key: 'data_flow_count', label: 'Data Flows', description: 'Total number of mapping data flows', icon: GitBranch, color: 'text-status-info', bg: 'bg-status-info/10' },
  { key: 'orphan_count', label: 'Orphan Pipelines', description: 'Pipelines that are never triggered by any schedule or parent pipeline', icon: Trash2, color: 'text-status-error', bg: 'bg-status-error/10' },
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
    <div className="flex flex-col h-full bg-bg-base overflow-y-auto">
      <div className="p-6 border-b border-border-color bg-bg-surface">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-accent-primary/15 border border-accent-primary/30 flex items-center justify-center shrink-0">
              <Factory size={20} className="text-accent-primary" />
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-text-primary">
                Factory Name: <span className="text-accent-primary">{factory.factory_name}</span>
              </h2>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-secondary mt-1">
                <span className="flex items-center gap-1">
                  <FolderGit2 size={12} /> {factory.resource_group}
                </span>
                <span className="flex items-center gap-1">
                  <MapPin size={12} /> {factory.location}
                </span>
                <span className="flex items-center gap-1">
                  <RefreshCw size={12} /> Refreshed: {formatTimestamp(factory.last_refreshed_at)}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border-color text-sm font-medium text-text-primary hover:bg-bg-surface-elevated transition-colors disabled:opacity-50 shrink-0"
          >
            <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6 max-w-6xl mx-auto w-full">
        {activeConfig ? (
          <section>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                <button onClick={closeList} className="p-1 rounded hover:bg-bg-surface-elevated transition-colors" title="Back to overview">
                  <ArrowLeft size={18} className="text-text-secondary" />
                </button>
                {activeConfig.title} ({listData.length})
              </h3>
              <button
                onClick={closeList}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border-color text-xs font-medium text-text-secondary hover:bg-bg-surface-elevated hover:text-text-primary transition-colors"
              >
                Back to Overview
              </button>
            </div>

            {listLoading ? (
              <div className="flex items-center gap-2 text-text-secondary text-sm py-8 justify-center">
                <RefreshCw className="animate-spin" size={14} />
                Loading {activeConfig.title.toLowerCase()}...
              </div>
            ) : listError ? (
              <div className="p-6 bg-bg-surface border border-border-color rounded-lg text-status-warning text-sm">
                {listError}
              </div>
            ) : listData.length === 0 ? (
              <div className="p-6 bg-bg-surface border border-border-color rounded-lg text-text-secondary text-sm">
                {activeConfig.empty}
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border border-border-color bg-bg-surface">
                <table className="w-full text-left border-collapse text-sm text-text-primary">
                  <thead>
                    <tr className="bg-bg-surface-elevated border-b border-border-color">
                      {activeConfig.columns.map((col) => (
                        <th key={col.key} className="p-3 font-medium text-text-secondary">{col.label}</th>
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
                            detailHref ? 'cursor-pointer hover:bg-bg-surface-elevated' : ''
                          }`}
                        >
                          {activeConfig.columns.map((col) => (
                            <td
                              key={col.key}
                              className={`p-3 ${col.key === 'name' && detailHref ? 'font-medium text-accent-primary' : ''}`}
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
                    className={`relative group rounded-lg border border-border-color bg-bg-surface p-4 flex flex-col gap-3 transition-colors ${
                      config && !orphanPending
                        ? 'cursor-pointer hover:border-accent-primary/60'
                        : 'cursor-default'
                    } ${orphanPending ? 'opacity-70' : ''}`}
                  >
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-xs px-3 py-1.5 rounded-md bg-bg-elevated border border-border-color text-xs text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                      {card.description}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                        {card.label}
                      </span>
                      <span className={`w-8 h-8 rounded-md ${card.bg} flex items-center justify-center`}>
                        <card.icon size={16} className={card.color} />
                      </span>
                    </div>
                    <div className="flex items-end justify-between">
                      {orphanPending ? (
                        <span className="flex items-center gap-2 text-sm text-text-secondary">
                          <RefreshCw className="animate-spin" size={18} />
                          Loading...
                        </span>
                      ) : (
                        <span className="text-3xl font-bold text-text-primary">{value}</span>
                      )}
                      {config && !orphanPending && (
                        <span className="text-xs text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity">
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
                <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                  <Sparkles size={18} className="text-accent-secondary" /> Factory Insights
                </h3>
                <button
                  onClick={generateInsights}
                  disabled={insightsLoading}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border-color text-xs font-medium text-text-secondary hover:bg-bg-surface-elevated hover:text-text-primary transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={13} className={insightsLoading ? 'animate-spin' : ''} />
                  Regenerate
                </button>
              </div>

              {insightsLoading && !insights ? (
                <div className="p-6 bg-bg-surface border border-border-color rounded-lg flex items-center gap-2 text-text-secondary text-sm">
                  <RefreshCw className="animate-spin" size={14} />
                  Generating factory insights...
                </div>
              ) : (
                <>
                  <div className="grid gap-2 mb-4">
                    {insightItems.map((item, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 p-3 rounded-lg bg-bg-surface border border-border-color text-sm"
                      >
                        <item.icon size={16} className={`mt-0.5 shrink-0 ${item.tone}`} />
                        <span className="text-text-primary">{item.text}</span>
                      </div>
                    ))}
                  </div>

                  <div className="rounded-lg border border-border-color bg-bg-surface p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2 text-xs font-semibold text-text-secondary uppercase tracking-wider">
                        <Bot size={14} className="text-status-success" /> AI Narrative
                      </div>
                      {insights?.provider && (
                        <span className="text-[10px] text-text-secondary bg-bg-base border border-border-color rounded px-2 py-0.5">
                          {formatProviderLabel(insights.provider)}
                        </span>
                      )}
                    </div>
                    {insightsLoading ? (
                      <div className="flex items-center gap-2 text-text-secondary text-sm">
                        <RefreshCw className="animate-spin" size={14} />
                        Generating insights...
                      </div>
                    ) : aiError ? (
                      <p className="text-status-warning text-sm">
                        {aiError} — deterministic insights above remain valid.
                      </p>
                    ) : (
                      <p className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
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
