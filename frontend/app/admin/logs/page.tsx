'use client';

import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { LogEntry } from '@/lib/types';
import { Loader2, AlertCircle, ChevronLeft, ChevronRight, Filter } from 'lucide-react';

const SEVERITY_COLORS: Record<string, string> = {
  info: 'text-blue-400 bg-blue-500/10',
  warning: 'text-yellow-400 bg-yellow-500/10',
  error: 'text-orange-400 bg-orange-500/10',
  critical: 'text-red-400 bg-red-500/10',
};

const SEVERITY_DOT: Record<string, string> = {
  info: 'bg-blue-400',
  warning: 'bg-yellow-400',
  error: 'bg-orange-400',
  critical: 'bg-red-400',
};

export default function LogsPage() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [severity, setSeverity] = useState('');
  const [eventType, setEventType] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const limit = 50;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getLogs({
        severity: severity || undefined,
        event_type: eventType || undefined,
        limit,
        offset,
      });
      setEntries(result.entries);
      setTotal(result.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load logs');
    } finally {
      setLoading(false);
    }
  }, [severity, eventType, offset]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.getLogs({
          severity: severity || undefined,
          event_type: eventType || undefined,
          limit,
          offset,
        });
        if (!cancelled) {
          setEntries(result.entries);
          setTotal(result.total);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load logs');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [severity, eventType, offset]);

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  const formatDate = (d: string) => {
    const date = new Date(d);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    return date.toLocaleString();
  };

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg bg-neutral-700 flex items-center justify-center">
            <Filter className="w-4 h-4 text-emerald-400" />
          </div>
          <h1 className="text-xl font-bold text-white">Event Log</h1>
          <span className="text-sm text-neutral-500 ml-auto">{total} total events</span>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-6 flex-wrap">
          <select
            value={severity}
            onChange={e => { setSeverity(e.target.value); setOffset(0); }}
            className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
          >
            <option value="">All Severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="critical">Critical</option>
          </select>
          <select
            value={eventType}
            onChange={e => { setEventType(e.target.value); setOffset(0); }}
            className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
          >
            <option value="">All Event Types</option>
            <option value="system_event">System Event</option>
            <option value="admin_action">Admin Action</option>
            <option value="usage_threshold">Usage Threshold</option>
            <option value="digest">Digest</option>
            <option value="error">Error</option>
          </select>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 rounded-xl px-4 py-3 mb-4">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
            <button onClick={fetchLogs} className="ml-auto text-xs underline hover:text-red-300">Retry</button>
          </div>
        )}

        {/* Empty */}
        {!loading && !error && entries.length === 0 && (
          <p className="text-neutral-500 text-sm py-16 text-center">No log entries found.</p>
        )}

        {/* Log Entries */}
        {!loading && entries.length > 0 && (
          <div className="space-y-2">
            {entries.map(entry => (
              <div key={entry.id} className="bg-neutral-800/50 border border-neutral-700 rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                  className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-neutral-800/80 transition-colors"
                >
                  <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${SEVERITY_DOT[entry.severity] || 'bg-neutral-500'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SEVERITY_COLORS[entry.severity] || 'text-neutral-400 bg-neutral-700'}`}>
                        {entry.severity}
                      </span>
                      <span className="text-xs text-neutral-500">{entry.event_type}</span>
                      <span className="text-xs text-neutral-600">{entry.source}</span>
                    </div>
                    <p className="text-sm text-neutral-200">{entry.summary}</p>
                    <p className="text-xs text-neutral-500 mt-0.5">{formatDate(entry.created_at)}</p>
                  </div>
                  <span className="text-neutral-600 text-xs mt-1">{entry.actor_role}</span>
                </button>
                {expandedId === entry.id && entry.details && (
                  <div className="px-4 pb-3 pt-0">
                    <pre className="text-xs text-neutral-400 bg-neutral-900 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono">
                      {JSON.stringify(entry.details, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4 mt-6">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 rounded-lg transition-colors text-neutral-300"
            >
              <ChevronLeft className="w-4 h-4" /> Previous
            </button>
            <span className="text-sm text-neutral-500">Page {currentPage} of {totalPages}</span>
            <button
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 rounded-lg transition-colors text-neutral-300"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
