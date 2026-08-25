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
  CRITICAL: { bg: 'bg-red-500/15', border: 'border-red-500/40', text: 'text-red-400', icon: ShieldX },
  HIGH: { bg: 'bg-orange-500/15', border: 'border-orange-500/40', text: 'text-orange-400', icon: ShieldAlert },
  MEDIUM: { bg: 'bg-yellow-500/15', border: 'border-yellow-500/40', text: 'text-yellow-400', icon: Shield },
  LOW: { bg: 'bg-green-500/15', border: 'border-green-500/40', text: 'text-green-400', icon: ShieldCheck },
};

const SEVERITY_DOT = {
  HIGH: 'bg-red-400',
  MEDIUM: 'bg-yellow-400',
  LOW: 'bg-green-400',
  INFO: 'bg-blue-400',
};

function FindingRow({ finding }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-border-color rounded-lg bg-bg-surface overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 text-left hover:bg-bg-surface-elevated transition-colors"
      >
        <span className={`w-2 h-2 rounded-full shrink-0 ${SEVERITY_DOT[finding.severity] || 'bg-gray-400'}`} />
        <span className="font-medium text-text-primary text-sm flex-1">{finding.asset}</span>
        <span className="px-2 py-0.5 text-[10px] rounded bg-bg-base border border-border-color text-text-secondary">
          {finding.asset_type}
        </span>
        <span className="px-2 py-0.5 text-[10px] rounded bg-bg-base border border-border-color text-text-secondary">
          {finding.confidence}
        </span>
        {expanded ? <ChevronUp size={14} className="text-text-secondary" /> : <ChevronDown size={14} className="text-text-secondary" />}
      </button>
      {expanded && (
        <div className="p-3 pt-0 border-t border-border-color space-y-2 text-xs">
          <p className="text-text-secondary">{finding.reason}</p>
          {finding.evidence?.length > 0 && (
            <div>
              <span className="font-semibold text-text-secondary">Evidence:</span>
              <div className="mt-1 space-y-1">
                {finding.evidence.map((ev, i) => (
                  <code key={i} className="block px-2 py-1 bg-bg-base rounded border border-border-color text-accent-primary font-mono text-[11px] break-all">
                    {ev}
                  </code>
                ))}
              </div>
            </div>
          )}
          <div className="flex gap-3 text-text-secondary">
            <span>Relationship: <strong>{finding.relationship}</strong></span>
            <span>Impact: <strong>{finding.impact_type}</strong></span>
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
    <div className="flex flex-col h-full bg-bg-base overflow-y-auto">
      {/* Header */}
      <div className="p-6 border-b border-border-color bg-bg-surface">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {onBack && (
              <button
                onClick={onBack}
                className="p-1.5 rounded-lg border border-border-color text-text-secondary hover:bg-bg-surface-elevated hover:text-text-primary transition-colors"
                title="Back"
              >
                <ArrowLeft size={16} />
              </button>
            )}
            <h2 className="text-xl font-semibold text-text-primary flex items-center gap-2">
              <GitBranch size={20} className="text-accent-primary" />
              Change Impact Analysis
            </h2>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3 mt-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">Target:</span>
            <span className="px-2 py-1 bg-bg-base border border-border-color rounded text-sm font-medium text-accent-primary">
              {assetName}
            </span>
            {objectType && (
              <span className="px-2 py-1 bg-bg-base border border-border-color rounded text-xs text-text-secondary">
                {objectType}
              </span>
            )}
          </div>
          <select
            value={changeType}
            onChange={(e) => setChangeType(e.target.value)}
            className="px-3 py-1.5 bg-bg-base border border-border-color rounded-lg text-sm text-text-primary focus:outline-none focus:border-accent-primary"
          >
            {CHANGE_TYPES.map((ct) => (
              <option key={ct.value} value={ct.value}>{ct.label}</option>
            ))}
          </select>
          <button
            onClick={runAnalysis}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-1.5 bg-accent-primary text-white rounded-lg text-sm font-medium hover:bg-accent-primary/90 transition-colors disabled:opacity-50"
          >
            {loading ? <RefreshCw className="animate-spin" size={14} /> : <GitBranch size={14} />}
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
            <div className={`flex items-center gap-4 p-5 rounded-xl border ${riskStyle?.bg} ${riskStyle?.border}`}>
              <RiskIcon size={32} className={riskStyle?.text} />
              <div className="flex-1">
                <div className={`text-2xl font-bold ${riskStyle?.text}`}>
                  {result.risk?.level} RISK
                </div>
                <div className="text-sm text-text-secondary mt-1">
                  Score: {result.risk?.score}/100
                </div>
              </div>
              <div className="text-right text-sm text-text-secondary">
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
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">Why?</h3>
                <div className="space-y-1">
                  {result.risk.reasons.map((reason, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-text-primary">
                      <span className="text-accent-primary mt-0.5">•</span>
                      {reason}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Impact Chain */}
            {result.impact_chain?.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">Impact Chain</h3>
                <div className="flex flex-wrap items-center gap-1 text-xs font-mono">
                  {result.impact_chain.map((item, i) => (
                    <React.Fragment key={i}>
                      <span className="px-2 py-1 bg-bg-surface border border-border-color rounded text-text-primary">
                        {item}
                      </span>
                      {i < result.impact_chain.length - 1 && (
                        <span className="text-text-secondary">→</span>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </section>
            )}

            {/* Affected Pipelines */}
            {result.affected_pipelines?.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">Affected Pipelines</h3>
                <div className="flex flex-wrap gap-2">
                  {result.affected_pipelines.map((p, i) => (
                    <span key={i} className="px-2 py-1 bg-bg-surface border border-border-color rounded text-sm text-text-primary">
                      {p}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* External Systems */}
            {result.external_systems?.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">External Systems</h3>
                <div className="flex flex-wrap gap-2">
                  {result.external_systems.map((s, i) => (
                    <span key={i} className="flex items-center gap-1 px-2 py-1 bg-accent-secondary/10 border border-accent-secondary/30 rounded text-sm text-accent-secondary">
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
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">
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
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">
                  Indirect Impacts ({result.indirect_impacts.length})
                </h3>
                <div className="space-y-2">
                  {result.indirect_impacts.slice(0, 10).map((f, i) => (
                    <FindingRow key={i} finding={f} />
                  ))}
                  {result.indirect_impacts.length > 10 && (
                    <p className="text-xs text-text-secondary text-center py-2">
                      + {result.indirect_impacts.length - 10} more indirect impacts
                    </p>
                  )}
                </div>
              </section>
            )}

            {/* Consequences */}
            {result.potential_consequences?.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">Potential Consequences</h3>
                <div className="space-y-1">
                  {result.potential_consequences.map((c, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-text-primary">
                      <AlertTriangle size={14} className="text-yellow-400 mt-0.5 shrink-0" />
                      {c}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Recommendation */}
            {result.recommendation && (
              <section className="rounded-xl border border-accent-primary/30 bg-accent-primary/5 p-5">
                <h3 className="text-sm font-semibold text-accent-primary uppercase tracking-wider mb-2">Recommendation</h3>
                <div className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
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
