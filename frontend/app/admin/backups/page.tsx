'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { BackupEntry } from '@/lib/types';
import { toast } from 'sonner';
import { Archive, RotateCcw, Loader2, AlertCircle } from 'lucide-react';

export default function BackupsPage() {
  const [backups, setBackups] = useState<BackupEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchBackups = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listBackups();
      setBackups(data.backups);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load backups');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.listBackups();
        if (!cancelled) setBackups(data.backups);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load backups');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleRestore = async (id: string) => {
    if (!window.confirm('Are you sure you want to restore this backup? Current data will be replaced.')) return;
    setRestoring(id);
    try {
      const res = await api.restoreBackup(id);
      if (res.success) {
        toast.success(`Backup restored: ${res.rows} rows loaded`);
        fetchBackups();
      } else {
        toast.error('Restore failed');
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Restore failed');
    } finally {
      setRestoring(null);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg bg-neutral-700 flex items-center justify-center">
            <Archive className="w-4 h-4 text-emerald-400" />
          </div>
          <h1 className="text-xl font-bold text-white">Backups</h1>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 rounded-xl px-4 py-3 mb-4">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
            <button onClick={fetchBackups} className="ml-auto text-xs underline hover:text-red-300">Retry</button>
          </div>
        )}

        {!loading && !error && backups.length === 0 && (
          <p className="text-neutral-500 text-sm py-16 text-center">No backups found.</p>
        )}

        {!loading && backups.length > 0 && (
          <div className="bg-neutral-800/50 border border-neutral-700 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-neutral-800 text-neutral-300 text-left">
                  <th className="px-4 py-3 font-medium">Filename</th>
                  <th className="px-4 py-3 font-medium whitespace-nowrap">Created</th>
                  <th className="px-4 py-3 font-medium text-right">Size</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {backups.map((b) => (
                  <tr key={b.id} className="border-t border-neutral-700 text-neutral-200">
                    <td className="px-4 py-3">{b.filename}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-neutral-400">{formatDate(b.created_at)}</td>
                    <td className="px-4 py-3 text-right text-neutral-400 whitespace-nowrap">{formatSize(b.size_bytes)}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        disabled={restoring === b.id}
                        onClick={() => handleRestore(b.id)}
                        className="flex items-center gap-1.5 ml-auto px-3 py-1.5 text-xs bg-neutral-700 hover:bg-neutral-600 disabled:opacity-50 text-neutral-200 rounded-lg transition-colors"
                      >
                        {restoring === b.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                        Restore
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
