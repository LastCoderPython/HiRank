'use client';

import React, { useEffect } from 'react';

interface ClearChatsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function ClearChatsModal({ isOpen, onClose, onConfirm }: ClearChatsModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 transition-opacity" role="dialog" aria-modal="true" aria-label="Clear all chats">
      <div className="w-full max-w-sm bg-neutral-900 rounded-xl border border-neutral-800 shadow-2xl p-6 flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-200">
        <h2 className="text-lg font-semibold text-white">Clear all chats?</h2>
        <p className="text-sm text-neutral-400">
          This action cannot be undone. All your chat history will be permanently deleted.
        </p>
        <div className="flex justify-end gap-3 mt-4">
          <button 
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-neutral-300 hover:bg-neutral-800 transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={onConfirm}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white transition-colors"
          >
            Clear All
          </button>
        </div>
      </div>
    </div>
  );
}
