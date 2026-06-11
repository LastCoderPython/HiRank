'use client';

import { useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { ComparisonResponse } from '@/lib/types';
import { CompareTable } from '@/components/compare-table';
import { Loader2, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export default function ComparePage() {
  const [collegesInput, setCollegesInput] = useState('');
  const [branchInput, setBranchInput] = useState('');
  const [result, setResult] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = useCallback(async () => {
    const trimmed = collegesInput.trim().toUpperCase();
    if (!trimmed) {
      setError('Enter at least 2 college codes (e.g. AEC,JEC)');
      return;
    }
    const codes = trimmed.split(/[, ]+/).filter(Boolean);
    if (codes.length < 2) {
      setError('Enter at least 2 college codes');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.compareColleges(codes.join(','), branchInput.trim() || undefined);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Comparison failed');
    } finally {
      setLoading(false);
    }
  }, [collegesInput, branchInput]);

  return (
    <div className="min-h-screen bg-neutral-900 text-white">
      <div className="max-w-5xl mx-auto p-6">
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-neutral-400 hover:text-white mb-6 transition-colors">
          <ArrowLeft size={16} /> Back
        </Link>

        <h1 className="text-2xl font-bold mb-2">College Compare</h1>
        <p className="text-sm text-neutral-400 mb-6">Compare fees, placements, hostels, and seats side by side.</p>

        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <input
            type="text"
            value={collegesInput}
            onChange={e => setCollegesInput(e.target.value)}
            placeholder="College codes: AEC, JEC, NITS"
            className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg py-2.5 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
            onKeyDown={e => { if (e.key === 'Enter') handleCompare(); }}
          />
          <input
            type="text"
            value={branchInput}
            onChange={e => setBranchInput(e.target.value)}
            placeholder="Branch (optional): CSE"
            className="w-full sm:w-40 bg-neutral-800 border border-neutral-700 rounded-lg py-2.5 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
            onKeyDown={e => { if (e.key === 'Enter') handleCompare(); }}
          />
          <button
            onClick={handleCompare}
            disabled={loading}
            className="px-6 py-2.5 rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            Compare
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400 mb-4">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-6">
            <div className="flex items-center gap-2 mb-4">
              <h2 className="text-lg font-semibold text-white">
                {result.colleges.join(' vs ')}
              </h2>
              {result.branch && (
                <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/30">
                  {result.branch}
                </span>
              )}
            </div>
            <CompareTable
              colleges={result.colleges}
              branch={result.branch}
              metrics={result.metrics}
              hasData={result.has_data}
            />
          </div>
        )}

        <div className="mt-8 p-4 rounded-lg bg-neutral-800/30 border border-neutral-700/30">
          <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">Tips</h3>
          <ul className="text-xs text-neutral-400 space-y-1">
            <li>Use college codes: AEC, JEC, NITS, GU, DU, BVEC, BBEC, DHEC, etc.</li>
            <li>Separate multiple codes with commas or spaces.</li>
            <li>Add a branch filter to compare specific programs.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
