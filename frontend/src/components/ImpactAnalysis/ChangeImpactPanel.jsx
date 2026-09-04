import React, { useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  GitBranch,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  ArrowLeft,
} from 'lucide-react';
import { apiClient } from '../../api/client';

const CHANGE_TYPES = [
  { value: 'DELETE', label: 'Delete' },
  { value: 'REMOVE', label: 'Remove' },
  { value: 'DISABLE', label: 'Disable' },
  { value: 'MODIFY', label: 'Modify' },
  { value: 'REPLACE', label: 'Replace' },
  { value: 'RENAME', label: 'Rename' },
  { value: 'DECOMMISSION', label: 'Decommission' },
];

const RISK_STYLES = {
  CRITICAL: { bg: 'bg-red-50 border border-red-200', border: 'border-red-200', text: 'text-red-700', icon: ShieldX },
  HIGH: { bg: 'bg-orange-50 border border-orange-200', border: 'border-orange-200', text: 'text-orange-700', icon: ShieldAlert },
  MEDIUM: { bg: 'bg-amber-50 border border-amber-200', border: 'border-amber-200', text: 'text-amber-700', icon: Shield },
  LOW: { bg: 'bg-emerald-50 border border-emerald-200', border: 'border-emerald-200', text: 'text-emerald-700', icon: ShieldCheck },
};

const SEVERITY_DOT = {
  HIGH: 'bg-red-500',
  MEDIUM: 'bg-amber-500',
  LOW: 'bg-emerald-500',
  INFO: 'bg-sky-500',
};

function FindingRow({ finding }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-border-color rounded-xl bg-white overflow-hidden shadow-xs hover:border-slate-300 transition-colors">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3.5 text-left hover:bg-slate-50 transition-colors"
      >
        <span className={`w-2 h-2 rounded-full shrink-0 ${SEVERITY_DOT[finding.severity] || 'bg-slate-400'}`} />
        <span className="font-semibold text-text-primary text-sm flex-1">{finding.asset}</span>
        <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-slate-100 border border-slate-200 text-slate-700">
          {finding.asset_type}
        </span>
        <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-blue-50 border border-blue-200 text-blue-700">
          {finding.confidence}
        </span>
        {expanded ? <ChevronUp size={15} className="text-text-secondary" /> : <ChevronDown size={15} className="text-text-secondary" />}
      </button>
      {expanded && (
        <div className="p-4 pt-0 border-t border-border-color space-y-2.5 text-xs bg-slate-50/50">
          <p className="text-slate-700 font-medium leading-relaxed">{finding.reason}</p>
          {finding.evidence?.length > 0 && (
            <div>
              <span className="font-semibold text-slate-800">Evidence:</span>
              <div className="mt-1 space-y-1">
                {finding.evidence.map((ev, i) => (
                  <code key={i} className="block px-2.5 py-1.5 bg-white rounded-lg border border-slate-200 text-accent-primary font-mono text-[11px] break-all shadow-xs">
                    {ev}
                  </code>
                ))}
              </div>
            </div>
          )}
          <div className="flex gap-4 text-slate-600 pt-1">
            <span>Relationship: <strong className="text-slate-900">{finding.relationship}</strong></span>
            <span>Impact: <strong className="text-slate-900">{finding.impact_type}</strong></span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ChangeImpactPanel({ assetName, objectType, onBack }) {
  const [changeType, setChangeType] = useState('DELETE');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const runAnalysis = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { data } = await apiClient.post('/graph/change-impact', {
        target_asset: assetName,
        change_type: changeType,
        object_type: objectType || undefined,
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to run impact analysis.');
    } finally {
      setLoading(false);
    }
  };

  const riskStyle = result ? RISK_STYLES[result.risk?.level] || RISK_STYLES.LOW : null;
  const RiskIcon = riskStyle?.icon || Shield;

  return (
    <div className="flex flex-col h-full bg-slate-50 overflow-y-auto">
      {/* Header */}
      <div className="p-6 border-b border-border-color bg-white shadow-xs">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {onBack && (
              <button
                onClick={onBack}
                className="p-1.5 rounded-lg border border-border-color bg-white text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors shadow-xs"
                title="Back"
              >
                <ArrowLeft size={16} />
              </button>
            )}
            <h2 className="text-xl font-bold text-text-primary flex items-center gap-2 tracking-tight">
              <GitBranch size={20} className="text-accent-primary" />
              Change Impact Analysis
            </h2>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3 mt-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-text-secondary">Target:</span>
            <span className="px-2.5 py-1 bg-blue-50 border border-blue-200/80 rounded-lg text-xs font-semibold text-accent-primary">
              {assetName}
            </span>
            {objectType && (
              <span className="px-2 py-1 bg-slate-100 border border-slate-200 rounded-lg text-xs text-slate-600 font-medium">
                {objectType}
              </span>
            )}
          </div>
          <select
            value={changeType}
            onChange={(e) => setChangeType(e.target.value)}
            className="px-3 py-1.5 bg-white border border-border-color rounded-xl text-xs font-semibold text-slate-800 shadow-xs focus:outline-none focus:border-accent-primary focus:ring-2 focus:ring-accent-primary/20"
          >
            {CHANGE_TYPES.map((ct) => (
              <option key={ct.value} value={ct.value}>{ct.label}</option>
            ))}
          </select>
          <button
            onClick={runAnalysis}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-1.5 bg-accent-primary text-white rounded-xl text-xs font-semibold hover:bg-accent-hover shadow-xs transition-colors disabled:opacity-50"
          >
            {loading ? <RefreshCw className="animate-spin" size={13} /> : <GitBranch size={13} />}
            {loading ? 'Analyzing...' : 'Analyze Impact'}
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="p-6 space-y-6 max-w-5xl mx-auto w-full">
        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertTriangle size={16} />
            {error}
          </div>
        )}

        {!result && !loading && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-text-secondary">
            <GitBranch size={48} className="mb-4 opacity-30" />
            <p className="text-sm">Select a change type and click Analyze Impact to see results.</p>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-16 text-text-secondary">
            <RefreshCw className="animate-spin mr-2" size={20} />
            Running change impact analysis...
          </div>
        )}

        {result && (
          <>
            {/* Disambiguation Notice */}
            {result.disambiguation && (
              <div className="flex items-start gap-3 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-400 text-sm">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <div className="whitespace-pre-wrap">{result.disambiguation}</div>
              </div>
            )}

            {/* Risk Banner */}
            <div className={`flex items-center gap-4 p-5 rounded-2xl border ${riskStyle?.bg} ${riskStyle?.border} shadow-xs`}>
              <RiskIcon size={32} className={riskStyle?.text} />
              <div className="flex-1">
                <div className={`text-2xl font-black ${riskStyle?.text} tracking-tight`}>
                  {result.risk?.level} RISK
                </div>
                <div className="text-sm font-semibold text-slate-700 mt-0.5">
                  Risk Score: {result.risk?.score}/100
                </div>
              </div>
              <div className="text-right text-xs font-semibold text-slate-700 space-y-0.5">
                <div>{result.direct_impacts?.length || 0} direct impacts</div>
                <div>{result.indirect_impacts?.length || 0} indirect impacts</div>
                {result.external_systems?.length > 0 && (
                  <div>{result.external_systems.length} external system(s)</div>
                )}
              </div>
            </div>

            {/* Risk Reasons */}
            {result.risk?.reasons?.length > 0 && (
              <section>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Why?</h3>
                <div className="space-y-1.5">
                  {result.risk.reasons.map((reason, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-slate-900 font-medium">
                      <span className="text-accent-primary mt-0.5 font-bold">•</span>
                      {reason}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Impact Chain */}
            {result.impact_chain?.length > 0 && (
              <section>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Impact Chain</h3>
                <div className="flex flex-wrap items-center gap-1.5 text-xs font-mono">
                  {result.impact_chain.map((item, i) => (
                    <React.Fragment key={i}>
                      <span className="px-2.5 py-1 bg-white border border-slate-300 rounded-lg text-slate-900 font-bold shadow-xs">
                        {item}
                      </span>
                      {i < result.impact_chain.length - 1 && (
                        <span className="text-slate-500 font-bold">→</span>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </section>
            )}

            {/* Affected Pipelines */}
            {result.affected_pipelines?.length > 0 && (
              <section>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Affected Pipelines</h3>
                <div className="flex flex-wrap gap-2">
                  {result.affected_pipelines.map((p, i) => (
                    <span key={i} className="px-3 py-1 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 font-semibold shadow-xs">
                      {p}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* External Systems */}
            {result.external_systems?.length > 0 && (
              <section>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">External Systems</h3>
                <div className="flex flex-wrap gap-2">
                  {result.external_systems.map((s, i) => (
                    <span key={i} className="flex items-center gap-1.5 px-3 py-1 bg-purple-50 border border-purple-200 rounded-lg text-sm text-purple-800 font-semibold shadow-xs">
                      <ExternalLink size={12} />
                      {s}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* Direct Impacts */}
            {result.direct_impacts?.length > 0 && (
              <section>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Direct Impacts ({result.direct_impacts.length})
                </h3>
                <div className="space-y-2">
                  {result.direct_impacts.map((f, i) => (
                    <FindingRow key={i} finding={f} />
                  ))}
                </div>
              </section>
            )}

            {/* Indirect Impacts */}
            {result.indirect_impacts?.length > 0 && (
              <section>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Indirect Impacts ({result.indirect_impacts.length})
                </h3>
                <div className="space-y-2">
                  {result.indirect_impacts.slice(0, 10).map((f, i) => (
                    <FindingRow key={i} finding={f} />
                  ))}
                  {result.indirect_impacts.length > 10 && (
                    <p className="text-xs text-slate-700 font-semibold text-center py-2">
                      + {result.indirect_impacts.length - 10} more indirect impacts
                    </p>
                  )}
                </div>
              </section>
            )}

            {/* Consequences */}
            {result.potential_consequences?.length > 0 && (
              <section>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Potential Consequences</h3>
                <div className="space-y-1.5">
                  {result.potential_consequences.map((c, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-slate-900 font-medium">
                      <AlertTriangle size={15} className="text-amber-600 mt-0.5 shrink-0" />
                      {c}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Recommendation */}
            {result.recommendation && (
              <section className="rounded-2xl border border-blue-200 bg-blue-50/60 p-5 shadow-xs">
                <h3 className="text-xs font-bold text-accent-primary uppercase tracking-wider mb-2">Recommendation</h3>
                <div className="text-sm text-slate-900 font-medium whitespace-pre-wrap leading-relaxed">
                  {result.recommendation}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
