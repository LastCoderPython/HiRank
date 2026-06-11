'use client';

import React from 'react';
import { ComparisonMetric } from '@/lib/types';

interface CompareTableProps {
  colleges: string[];
  branch?: string;
  metrics: ComparisonMetric[];
  hasData: boolean;
}

export function CompareTable({ colleges, branch, metrics, hasData }: CompareTableProps) {
  if (!hasData) {
    return (
      <div className="p-4 rounded-lg bg-neutral-800/50 border border-neutral-700/50 text-sm text-neutral-400">
        No comparison data available for the selected colleges.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-neutral-700/50">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-neutral-800/80">
            <th className="text-left px-4 py-3 text-neutral-400 font-medium text-xs uppercase tracking-wider">
              {branch ? `${branch} — ` : ''}Metric
            </th>
            {colleges.map((code) => (
              <th key={code} className="text-left px-4 py-3 text-white font-semibold">
                {code}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric, i) => (
            <tr key={i} className="border-t border-neutral-800/50 hover:bg-neutral-800/30 transition-colors">
              <td className="px-4 py-3 text-neutral-300 font-medium whitespace-nowrap">
                {metric.label}
                {metric.source && (
                  <span className="ml-2 text-[10px] text-neutral-500">({metric.source})</span>
                )}
              </td>
              {colleges.map((code) => {
                const val = metric.values[code] || 'N/A';
                const isNA = val === 'N/A';
                return (
                  <td key={code} className={`px-4 py-3 ${isNA ? 'text-neutral-600 italic' : 'text-white'}`}>
                    {isNA ? 'N/A' : val}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
