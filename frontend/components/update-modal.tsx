'use client';

import React from 'react';
import { X, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface UpdateModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  body: string;
}

export function UpdateModal({ isOpen, onClose, title, body }: UpdateModalProps) {
  if (!isOpen) return null;

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }}
      onClick={onClose}
    >
      {/* Modal Panel */}
      <div
        className="relative w-full max-w-lg rounded-2xl border border-neutral-700/60 bg-neutral-900 shadow-2xl overflow-hidden"
        style={{
          animation: 'modalFadeIn 0.25s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top accent gradient strip */}
        <div className="h-1 w-full bg-gradient-to-r from-blue-600 via-violet-500 to-blue-400" />

        {/* Header */}
        <div className="flex items-start gap-3 px-6 pt-5 pb-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/15 border border-blue-500/25">
            <Sparkles size={18} className="text-blue-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-blue-400 mb-0.5">
              What&apos;s New
            </p>
            <h2 className="text-base font-semibold text-neutral-100 leading-snug">
              {title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 p-1.5 rounded-lg text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Divider */}
        <div className="mx-6 border-t border-neutral-800" />

        {/* Body — render Markdown */}
        <div className="px-6 py-5 text-sm text-neutral-300 leading-relaxed prose prose-invert prose-sm max-w-none
          prose-p:text-neutral-300
          prose-li:text-neutral-300
          prose-strong:text-neutral-100 prose-strong:font-semibold
          prose-ul:space-y-2 prose-ul:my-2
        ">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {body}
          </ReactMarkdown>
        </div>

        {/* Footer */}
        <div className="px-6 pb-5 pt-1">
          <button
            onClick={onClose}
            className="w-full rounded-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white text-sm font-medium py-2.5 transition-colors"
          >
            Got it
          </button>
        </div>
      </div>

      {/* Keyframe animation */}
      <style>{`
        @keyframes modalFadeIn {
          from { opacity: 0; transform: scale(0.96) translateY(8px); }
          to   { opacity: 1; transform: scale(1)    translateY(0px); }
        }
      `}</style>
    </div>
  );
}
