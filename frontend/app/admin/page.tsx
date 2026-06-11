'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { Upload, Database, Archive, Shield, Filter, BarChart3, Database as DatabaseIcon, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { CutoffStatusResponse } from '@/lib/types';

const cards = [
  { href: '/admin/cutoffs', icon: Upload, title: 'Upload Cutoffs', desc: 'Import CEE/JEE cutoff data from CSV' },
  { href: '/admin/college-info', icon: Database, title: 'Upload College Info', desc: 'Import college metadata (fee, placement, etc.)' },
  { href: '/admin/backups', icon: Archive, title: 'Backups', desc: 'View and restore data backups' },
  { href: '/admin/analytics', icon: BarChart3, title: 'Analytics', desc: 'Usage insights, trends, and prediction stats' },
  { href: '/admin/logs', icon: Filter, title: 'Event Log', desc: 'View system events, admin actions, and alerts' },
];

export default function AdminDashboard() {
  const { user } = useAuth();
  const [cutoffStatus, setCutoffStatus] = useState<CutoffStatusResponse | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingStatus(true);
      try {
        const data = await api.getCutoffStatus();
        if (!cancelled) setCutoffStatus(data);
      } catch {
        // silently fail
      } finally {
        if (!cancelled) setLoadingStatus(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <Shield className="w-8 h-8 text-emerald-500" />
          <div>
            <h1 className="text-2xl font-bold text-white">Admin Panel</h1>
            <p className="text-neutral-400 text-sm">Welcome, {user?.name || 'Admin'}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
          {cards.map(({ href, icon: Icon, title, desc }) => (
            <Link
              key={href}
              href={href}
              className="group bg-neutral-800/50 border border-neutral-700 rounded-xl p-6 hover:bg-neutral-800 hover:border-neutral-600 transition-all"
            >
              <div className="w-10 h-10 rounded-lg bg-neutral-700 flex items-center justify-center mb-4 group-hover:bg-neutral-600 transition-colors">
                <Icon className="w-5 h-5 text-emerald-400" />
              </div>
              <h2 className="text-lg font-semibold text-white mb-1">{title}</h2>
              <p className="text-sm text-neutral-400">{desc}</p>
            </Link>
          ))}
        </div>

        <div className="mt-8">
          <h2 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider mb-4 flex items-center gap-2">
            <DatabaseIcon size={16} className="text-emerald-400" />
            Cutoff Data Status
          </h2>

          {loadingStatus ? (
            <div className="flex items-center gap-2 text-neutral-500 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading...
            </div>
          ) : cutoffStatus ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {(['cee', 'jee'] as const).map((exam) => {
                const data = cutoffStatus[exam];
                return (
                  <div key={exam} className="bg-neutral-800/50 border border-neutral-700 rounded-xl p-5">
                    <h3 className="text-base font-semibold text-white mb-2 uppercase">{exam}</h3>
                    <div className="space-y-1 text-sm text-neutral-400">
                      <p>Years: <span className="text-white font-medium">{data.years.join(', ') || 'None'}</span></p>
                      <p>Records: <span className="text-white font-medium">{data.records.toLocaleString()}</span></p>
                      <p>Colleges: <span className="text-white font-medium">{data.colleges}</span></p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-neutral-500">Could not load cutoff status.</p>
          )}
        </div>
      </div>
    </div>
  );
}
