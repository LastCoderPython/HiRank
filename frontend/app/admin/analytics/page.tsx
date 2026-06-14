'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { AnalyticsOverview, DailyAnalytics, PredictionAnalytics } from '@/lib/types';
import { Loader2, MessageSquare, Users, TrendingUp, BarChart3, Activity, type LucideIcon } from 'lucide-react';

function StatCard({ icon: Icon, label, value, color }: { icon: LucideIcon; label: string; value: string | number; color: string }) {
  return (
    <div className="bg-neutral-800/50 border border-neutral-700 rounded-xl p-5">
      <div className="flex items-center gap-3 mb-2">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
        <span className="text-sm text-neutral-400">{label}</span>
      </div>
      <p className="text-2xl font-bold text-white">{typeof value === 'number' ? value.toLocaleString() : value}</p>
    </div>
  );
}

function SimpleBar({ data, max }: { data: { date: string; chats: number }[]; max: number }) {
  return (
    <div className="flex items-end gap-[3px] h-32">
      {data.map((d, i) => {
        const height = max > 0 ? (d.chats / max) * 100 : 0;
        return (
          <div key={i} className="flex-1 flex flex-col items-center group relative">
            <div
              className="w-full bg-blue-500/60 hover:bg-blue-400 rounded-t transition-colors min-h-[2px]"
              style={{ height: `${Math.max(height, 1)}%` }}
              title={`${d.date}: ${d.chats} chats`}
            />
          </div>
        );
      })}
    </div>
  );
}

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [daily, setDaily] = useState<DailyAnalytics | null>(null);
  const [predictions, setPredictions] = useState<PredictionAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [ov, da, pa] = await Promise.all([
          api.getAnalyticsOverview(),
          api.getDailyAnalytics(30),
          api.getPredictionAnalytics(),
        ]);
        if (!cancelled) {
          setOverview(ov);
          setDaily(da);
          setPredictions(pa);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load analytics');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="animate-spin text-neutral-500" size={32} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-8">
        <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">{error}</div>
      </div>
    );
  }

  const maxDaily = daily ? Math.max(...daily.daily.map(d => d.chats), 1) : 1;

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <BarChart3 className="w-7 h-7 text-emerald-500" />
          <div>
            <h1 className="text-2xl font-bold text-white">Analytics</h1>
            <p className="text-neutral-400 text-sm">Usage insights and trends</p>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
          <StatCard icon={MessageSquare} label="Total Chats" value={overview?.total_chats ?? 0} color="bg-blue-500/20 text-blue-400" />
          <StatCard icon={Activity} label="Chats Today" value={overview?.chats_today ?? 0} color="bg-green-500/20 text-green-400" />
          <StatCard icon={MessageSquare} label="Messages" value={overview?.total_messages ?? 0} color="bg-purple-500/20 text-purple-400" />
          <StatCard icon={Users} label="Users" value={overview?.total_users ?? 0} color="bg-orange-500/20 text-orange-400" />
          <StatCard icon={TrendingUp} label="Predictions" value={overview?.total_predictions ?? 0} color="bg-emerald-500/20 text-emerald-400" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-neutral-800/50 border border-neutral-700 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Chat Volume (Last 30 Days)</h2>
            {daily && daily.daily.length > 0 ? (
              <SimpleBar data={daily.daily} max={maxDaily} />
            ) : (
              <p className="text-sm text-neutral-500">No data yet.</p>
            )}
          </div>

          <div className="bg-neutral-800/50 border border-neutral-700 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Prediction Band Distribution</h2>
            {predictions && predictions.total_prediction_events > 0 ? (
              <div className="space-y-3">
                {['safe', 'target', 'ambitious'].map((band) => {
                  const count = predictions.band_distribution[band] || 0;
                  const total = Object.values(predictions.band_distribution).reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? (count / total) * 100 : 0;
                  const colors: Record<string, string> = {
                    safe: 'bg-emerald-500',
                    target: 'bg-yellow-500',
                    ambitious: 'bg-orange-500',
                  };
                  return (
                    <div key={band}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-neutral-300 capitalize">{band}</span>
                        <span className="text-neutral-400">{count} ({pct.toFixed(0)}%)</span>
                      </div>
                      <div className="h-2 bg-neutral-700 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${colors[band]}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
                <p className="text-xs text-neutral-500 mt-3">
                  Based on {predictions.total_prediction_events} prediction events
                </p>
              </div>
            ) : (
              <p className="text-sm text-neutral-500">No prediction data yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
