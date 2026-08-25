import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { RefreshCw, Activity, Database, AlertCircle, ArrowLeft, GitBranch } from 'lucide-react';

export default function DataCanvas() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [pipeline, setPipeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPipeline = async () => {
      try {
        setLoading(true);
        const factoryName = localStorage.getItem('selected_factory') || undefined;
        const detailRes = await apiClient.get(`/pipelines/${id}`, {
          params: factoryName ? { factory_name: factoryName } : undefined,
        });
        setPipeline(detailRes.data);
      } catch (err) {
        setError(err.response?.data?.detail || err.message);
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchPipeline();
    } else {
      setLoading(false);
      setError("No pipeline selected. Navigate to /pipeline/{name} to view pipeline details.");
    }
  }, [id]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-bg-base">
        <div className="flex items-center gap-2 text-text-secondary">
          <RefreshCw className="animate-spin" size={20} />
          <span>Loading canvas data...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-bg-base p-8">
        <AlertCircle size={48} className="text-status-warning mb-4" />
        <p className="text-text-secondary">{error}</p>
      </div>
    );
  }

  if (!pipeline) {
    return null;
  }

  return (
    <div className="flex flex-col h-full bg-bg-base overflow-y-auto">
      {/* Header */}
      <div className="p-6 border-b border-border-color bg-bg-surface">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(-1)}
              className="p-1.5 rounded-lg border border-border-color text-text-secondary hover:bg-bg-surface-elevated hover:text-text-primary transition-colors"
              title="Back"
            >
              <ArrowLeft size={16} />
            </button>
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border-color text-xs font-medium text-text-secondary hover:bg-bg-surface-elevated hover:text-text-primary transition-colors"
            >
              <ArrowLeft size={14} />
              Back to Pipelines
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Activity className="text-accent-primary" size={24} />
          <h2 className="text-2xl font-semibold text-text-primary">{pipeline.name}</h2>
          <button
            onClick={() => navigate(`/impact-analysis/${encodeURIComponent(pipeline.name)}?type=Pipeline`)}
            className="flex items-center gap-1.5 px-3 py-1.5 ml-2 rounded-lg border border-accent-primary/40 bg-accent-primary/10 text-accent-primary text-xs font-medium hover:bg-accent-primary/20 transition-colors"
          >
            <GitBranch size={13} />
            Impact Analysis
          </button>
        </div>
        <p className="text-text-secondary text-sm">
          Pipeline ID: {pipeline.id}
        </p>
      </div>

      {/* Content */}
      <div className="p-6 space-y-6 max-w-5xl mx-auto w-full">
        
        {/* Activities Section */}
        <section>
          <h3 className="text-lg font-semibold mb-4 border-b border-border-color pb-2 text-text-primary">Activities ({pipeline.activities?.length || 0})</h3>
          <div className="overflow-hidden rounded-lg border border-border-color bg-bg-surface">
            <table className="w-full text-left border-collapse text-sm text-text-primary">
              <thead>
                <tr className="bg-bg-surface-elevated border-b border-border-color">
                  <th className="p-3 font-medium text-text-secondary">Name</th>
                  <th className="p-3 font-medium text-text-secondary">Type</th>
                  <th className="p-3 font-medium text-text-secondary">Depends On</th>
                </tr>
              </thead>
              <tbody>
                {pipeline.activities?.map((act, i) => (
                  <tr key={i} className="border-b border-border-color last:border-0 hover:bg-bg-surface-elevated transition-colors">
                    <td className="p-3 font-medium">{act.name}</td>
                    <td className="p-3">
                      <span className="px-2 py-1 bg-bg-base rounded text-xs border border-border-color text-text-secondary">
                        {act.type}
                      </span>
                    </td>
                    <td className="p-3 text-text-secondary">
                      {act.dependsOn?.map(d => d.activity).join(', ') || '-'}
                    </td>
                  </tr>
                ))}
                {(!pipeline.activities || pipeline.activities.length === 0) && (
                  <tr>
                    <td colSpan="3" className="p-4 text-center text-text-secondary">No activities found</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Global Parameters Placeholder */}
        <section>
          <h3 className="text-lg font-semibold mb-4 border-b border-border-color pb-2 flex items-center gap-2 text-text-primary">
            <Database size={18} className="text-text-secondary" /> Global Parameters & Variables
          </h3>
          <div className="p-6 bg-bg-surface border border-border-color rounded-lg text-text-secondary text-sm">
            <p>Parameters data goes here. This pipeline has {Object.keys(pipeline.parameters || {}).length} parameters.</p>
          </div>
        </section>

      </div>
    </div>
  );
}
