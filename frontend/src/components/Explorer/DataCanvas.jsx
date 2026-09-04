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
      <div className="p-6 border-b border-border-color bg-white shadow-xs">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(-1)}
              className="p-1.5 rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-xs"
              title="Back"
            >
              <ArrowLeft size={16} />
            </button>
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-xs"
            >
              <ArrowLeft size={14} />
              Back to Pipelines
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-accent-primary shadow-xs">
            <Activity size={20} />
          </div>
          <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">{pipeline.name}</h2>
          <button
            onClick={() => navigate(`/impact-analysis/${encodeURIComponent(pipeline.name)}?type=Pipeline`)}
            className="flex items-center gap-1.5 px-3 py-1.5 ml-2 rounded-xl border border-blue-300 bg-blue-50 text-accent-primary text-xs font-bold hover:bg-blue-100 transition-colors shadow-xs"
          >
            <GitBranch size={13} />
            Impact Analysis
          </button>
        </div>
        <p className="text-slate-700 font-semibold text-xs mt-1.5 font-mono">
          Pipeline ID: {pipeline.id}
        </p>
      </div>

      {/* Content */}
      <div className="p-6 space-y-6 max-w-5xl mx-auto w-full">
        
        {/* Activities Section */}
        <section>
          <h3 className="text-base font-extrabold mb-3 text-slate-900">Activities ({pipeline.activities?.length || 0})</h3>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card">
            <table className="w-full text-left border-collapse text-sm text-slate-900">
              <thead>
                <tr className="bg-slate-100/80 border-b border-slate-200">
                  <th className="px-4 py-3 font-bold text-xs text-slate-700 uppercase tracking-wider">Name</th>
                  <th className="px-4 py-3 font-bold text-xs text-slate-700 uppercase tracking-wider">Type</th>
                  <th className="px-4 py-3 font-bold text-xs text-slate-700 uppercase tracking-wider">Depends On</th>
                </tr>
              </thead>
              <tbody>
                {pipeline.activities?.map((act, i) => (
                  <tr key={i} className="border-b border-slate-200 last:border-0 hover:bg-slate-50/90 transition-colors">
                    <td className="px-4 py-3 font-bold text-slate-900">{act.name}</td>
                    <td className="px-4 py-3">
                      <span className="px-2.5 py-1 bg-slate-100 rounded-md text-xs font-semibold border border-slate-300 text-slate-800 font-mono">
                        {act.type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700 font-medium text-xs">
                      {act.dependsOn?.map(d => d.activity).join(', ') || '—'}
                    </td>
                  </tr>
                ))}
                {(!pipeline.activities || pipeline.activities.length === 0) && (
                  <tr>
                    <td colSpan="3" className="p-6 text-center text-slate-600 font-medium">No activities found</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Global Parameters Placeholder */}
        <section>
          <h3 className="text-base font-extrabold mb-3 flex items-center gap-2 text-slate-900">
            <Database size={18} className="text-accent-primary" /> Global Parameters & Variables
          </h3>
          <div className="p-5 bg-white border border-slate-200 rounded-2xl text-slate-800 font-medium text-sm shadow-card">
            <p>Parameters data is indexed. This pipeline references {Object.keys(pipeline.parameters || {}).length} parameter(s).</p>
          </div>
        </section>

      </div>
    </div>
  );
}
