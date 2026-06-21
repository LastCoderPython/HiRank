'use client';

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Bell, Plus, Trash2, Loader2, AlertCircle, ToggleLeft, ToggleRight, X } from 'lucide-react';
import { api } from '@/lib/api';
import { SystemAlert } from '@/lib/types';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [creating, setCreating] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getAlerts();
      setAlerts(result.alerts);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const result = await api.getAlerts();
        if (!cancelled) setAlerts(result.alerts);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load alerts');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleCreate = async () => {
    if (!newContent.trim()) return;
    setCreating(true);
    try {
      await api.createAlert(newContent.trim());
      toast.success('Alert created successfully');
      setNewContent('');
      setShowModal(false);
      fetchAlerts();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to create alert');
    } finally {
      setCreating(false);
    }
  };

  const handleActivate = async (alertId: string) => {
    setTogglingId(alertId);
    try {
      await api.activateAlert(alertId);
      toast.success('Alert activated — LLM injection is now live');
      fetchAlerts();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to activate alert');
    } finally {
      setTogglingId(null);
    }
  };

  const handleDeactivateAll = async () => {
    setTogglingId('all');
    try {
      await api.deactivateAllAlerts();
      toast.success('All alerts deactivated');
      fetchAlerts();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to deactivate alerts');
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (alertId: string) => {
    setDeletingId(alertId);
    try {
      await api.deleteAlert(alertId);
      toast.success('Alert deleted');
      fetchAlerts();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to delete alert');
    } finally {
      setDeletingId(null);
    }
  };

  const activeAlert = alerts.find(a => a.is_active);

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-3xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-neutral-700 flex items-center justify-center">
            <Bell className="w-4 h-4 text-amber-400" />
          </div>
          <h1 className="text-xl font-bold text-white">System Alerts</h1>
          <button
            onClick={() => setShowModal(true)}
            className="ml-auto flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold rounded-xl transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Alert
          </button>
        </div>
        <p className="text-sm text-neutral-500 mb-6 ml-11">
          The active alert is silently injected into the AI's context on every chat request. Only one alert can be active at a time.
        </p>

        {/* Active alert banner */}
        {activeAlert && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-3 mb-6 flex items-start gap-3">
            <div className="w-2 h-2 rounded-full bg-amber-400 mt-1.5 shrink-0 animate-pulse" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-amber-400 font-medium mb-1">ACTIVE — currently injected into all AI responses</p>
              <p className="text-sm text-neutral-200 break-words">{activeAlert.content}</p>
            </div>
            <button
              onClick={handleDeactivateAll}
              disabled={togglingId === 'all'}
              className="text-amber-400 hover:text-amber-300 disabled:opacity-40 shrink-0"
              title="Deactivate all alerts"
            >
              {togglingId === 'all' ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
            </button>
          </div>
        )}

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
            <button onClick={fetchAlerts} className="ml-auto text-xs underline hover:text-red-300">Retry</button>
          </div>
        )}

        {/* Empty */}
        {!loading && !error && alerts.length === 0 && (
          <div className="text-center py-16">
            <Bell className="w-8 h-8 text-neutral-600 mx-auto mb-3" />
            <p className="text-neutral-500 text-sm">No alerts yet. Create one to inject context into the AI.</p>
          </div>
        )}

        {/* Alert List */}
        {!loading && alerts.length > 0 && (
          <div className="space-y-3">
            {alerts.map(alert => (
              <div
                key={alert.id}
                className={`bg-neutral-800/50 border rounded-xl px-4 py-4 flex items-start gap-3 transition-all ${
                  alert.is_active ? 'border-amber-500/40' : 'border-neutral-700'
                }`}
              >
                <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${alert.is_active ? 'bg-amber-400 animate-pulse' : 'bg-neutral-600'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-neutral-200 break-words">{alert.content}</p>
                  <p className="text-xs text-neutral-500 mt-1">
                    {new Date(alert.created_at).toLocaleString()}
                    {alert.is_active && <span className="ml-2 text-amber-400 font-medium">● Active</span>}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {/* Toggle active */}
                  <button
                    onClick={() => alert.is_active ? handleDeactivateAll() : handleActivate(alert.id)}
                    disabled={togglingId === alert.id || togglingId === 'all'}
                    title={alert.is_active ? 'Deactivate' : 'Activate'}
                    className="text-neutral-400 hover:text-amber-400 disabled:opacity-40 transition-colors"
                  >
                    {togglingId === alert.id ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : alert.is_active ? (
                      <ToggleRight className="w-5 h-5 text-amber-400" />
                    ) : (
                      <ToggleLeft className="w-5 h-5" />
                    )}
                  </button>
                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(alert.id)}
                    disabled={deletingId === alert.id}
                    title="Delete alert"
                    className="text-neutral-500 hover:text-red-400 disabled:opacity-40 transition-colors"
                  >
                    {deletingId === alert.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Alert Modal */}
      {showModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={e => { if (e.target === e.currentTarget) setShowModal(false); }}
        >
          <div className="bg-neutral-900 border border-neutral-700 rounded-2xl w-full max-w-lg shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800">
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold text-white">New System Alert</h2>
              </div>
              <button onClick={() => setShowModal(false)} className="text-neutral-500 hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="px-6 py-4">
              <label className="block text-xs text-neutral-400 mb-2">Alert content</label>
              <textarea
                autoFocus
                value={newContent}
                onChange={e => setNewContent(e.target.value)}
                placeholder="e.g. CEE Phase 3 counseling begins on July 15th, 2026. Registration closes July 14th at 11:59 PM."
                rows={4}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-xl px-4 py-3 text-sm text-neutral-200 placeholder-neutral-600 resize-none focus:outline-none focus:border-amber-500/50"
              />
              <p className="text-xs text-neutral-600 mt-2">
                Keep it concise. The alert is injected as a sentence or two into the AI's brain, not displayed to users.
              </p>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-neutral-800">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 text-sm text-neutral-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newContent.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 text-black text-sm font-semibold rounded-xl transition-colors"
              >
                {creating && <Loader2 className="w-4 h-4 animate-spin" />}
                Create Alert
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
