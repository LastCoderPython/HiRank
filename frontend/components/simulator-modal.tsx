'use client';

import React, { useState } from 'react';
import { X, Loader2, TrendingUp, ArrowUpRight, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { SimulatedOption, SimulationResponse } from '@/lib/types';
import { cn } from '@/lib/utils';

const BADGE_COLORS: Record<string, string> = {
  safe: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  target: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  ambitious: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
};

function OptionList({ options, label }: { options: SimulatedOption[]; label: string }) {
  if (options.length === 0) return null;
  return (
    <div>
      <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">{label}</h4>
      <div className="space-y-1.5">
        {options.map((o, i) => (
          <div key={i} className={cn(
            "flex items-center justify-between px-3 py-2 rounded-lg border text-sm",
            o.is_unlocked ? "bg-blue-500/10 border-blue-500/30" : "bg-neutral-800/50 border-neutral-700/50"
          )}>
            <div className="flex items-center gap-2 min-w-0">
              {o.is_unlocked && <ArrowUpRight size={14} className="text-blue-400 shrink-0" />}
              <span className="text-white truncate font-medium">{o.college_name}</span>
              <span className="text-neutral-400 truncate">{o.branch}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0 ml-3">
              <span className="text-xs text-neutral-400">#{o.closing_rank}</span>
              <span className={cn(
                "text-[11px] font-medium px-1.5 py-0.5 rounded-full border",
                BADGE_COLORS[o.band] || "text-neutral-400"
              )}>
                {o.match_percentage.toFixed(0)}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface SimulatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSendToChat: (message: string) => void;
}

export function SimulatorModal({ isOpen, onClose, onSendToChat }: SimulatorModalProps) {
  const [currentRank, setCurrentRank] = useState('');
  const [targetRank, setTargetRank] = useState('');
  const [category, setCategory] = useState('General');
  const [exam, setExam] = useState('CEE');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSimulate = async () => {
    const cur = parseInt(currentRank);
    const tgt = parseInt(targetRank);
    if (!cur || !tgt || cur < 1 || tgt < 1) {
      setError('Enter valid current and target ranks');
      return;
    }
    if (tgt >= cur) {
      setError('Target rank should be lower (better) than current rank');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.simulateRank({
        current_rank: cur,
        target_rank: tgt,
        category,
        exam,
      });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200" role="dialog" aria-modal="true" aria-label="Rank Simulator">
      <div
        className="w-full max-w-2xl bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 max-h-[85vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-4 border-b border-neutral-800 shrink-0">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Rank Simulator</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-md text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors" aria-label="Close">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="overflow-y-auto p-6 space-y-5">
          <p className="text-sm text-neutral-400">
            See which colleges you could unlock if you improve your rank.
          </p>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-neutral-400 mb-1.5">Current Rank</label>
              <input
                type="number"
                min="1"
                value={currentRank}
                onChange={e => setCurrentRank(e.target.value)}
                placeholder="4200"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg py-2.5 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-400 mb-1.5">Target Rank</label>
              <input
                type="number"
                min="1"
                value={targetRank}
                onChange={e => setTargetRank(e.target.value)}
                placeholder="3000"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg py-2.5 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-neutral-400 mb-1.5">Category</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg py-2.5 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="General">General</option>
                <option value="OBC">OBC</option>
                <option value="SC">SC</option>
                <option value="ST">ST</option>
                <option value="EWS">EWS</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-400 mb-1.5">Exam</label>
              <select
                value={exam}
                onChange={e => setExam(e.target.value)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg py-2.5 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="CEE">Assam CEE</option>
                <option value="JEE">JEE Mains</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleSimulate}
            disabled={loading || !currentRank || !targetRank}
            className="w-full py-2.5 rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            Simulate
          </button>

          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-5 border-t border-neutral-800 pt-5">
              <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-500/10 border border-blue-500/30">
                <TrendingUp className="w-5 h-5 text-blue-400 shrink-0" />
                <p className="text-sm text-blue-200">{result.summary}</p>
              </div>

              {result.newly_unlocked.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <ArrowUpRight size={14} /> Newly Unlocked
                  </h4>
                  <OptionList options={result.newly_unlocked} label="" />
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-neutral-300">At Rank {result.current_rank}</h3>
                  <OptionList options={result.current_options.filter(o => o.band === 'safe')} label="Safe" />
                  <OptionList options={result.current_options.filter(o => o.band === 'target')} label="Target" />
                  <OptionList options={result.current_options.filter(o => o.band === 'ambitious')} label="Ambitious" />
                </div>
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-neutral-300">At Rank {result.target_rank}</h3>
                  <OptionList options={result.target_options.filter(o => o.band === 'safe')} label="Safe" />
                  <OptionList options={result.target_options.filter(o => o.band === 'target')} label="Target" />
                  <OptionList options={result.target_options.filter(o => o.band === 'ambitious')} label="Ambitious" />
                </div>
              </div>

              <button
                onClick={() => {
                  onSendToChat(`What if I improve from rank ${currentRank} to ${targetRank} in ${exam === 'CEE' ? 'Assam CEE' : 'JEE Mains'} ${category} category?`);
                  onClose();
                }}
                className="w-full py-2 rounded-lg bg-neutral-800 border border-neutral-700 text-sm text-neutral-200 hover:bg-neutral-700 transition-colors flex items-center justify-center gap-2"
              >
                Ask about this in chat <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
