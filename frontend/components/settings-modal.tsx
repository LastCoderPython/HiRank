import React from 'react';
import { X, User } from 'lucide-react';
import Image from 'next/image';
import { useUser } from '@clerk/nextjs';

function UserAccountDetails() {
  const { isLoaded, isSignedIn, user } = useUser();
  if (isLoaded && isSignedIn && user) {
    return (
      <>
        <div className="w-10 h-10 rounded-full overflow-hidden shrink-0 relative">
          <Image src={user.imageUrl} alt={user.fullName || "User avatar"} fill referrerPolicy="no-referrer" className="object-cover" />
        </div>
        <div>
          <p className="text-sm font-medium text-white">{user.fullName || "User"}</p>
          <p className="text-xs text-neutral-400">{user.primaryEmailAddress?.emailAddress}</p>
        </div>
      </>
    );
  }
  return <GuestAccountDetails />;
}

function GuestAccountDetails() {
  return (
    <>
      <div className="w-10 h-10 rounded-full overflow-hidden shrink-0 relative bg-neutral-800 flex items-center justify-center border border-neutral-700">
        <User size={20} className="text-neutral-400" />
      </div>
      <div>
        <p className="text-sm font-medium text-white">Guest Account</p>
        <p className="text-xs text-neutral-400">Sign in to save progress</p>
      </div>
    </>
  );
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  if (!isOpen) return null;

  const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 transition-opacity">
      <div className="w-full max-w-md bg-neutral-900 rounded-xl border border-neutral-800 shadow-2xl p-6 flex flex-col gap-6 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold text-white">Settings</h2>
          <button 
            onClick={onClose} 
            className="p-1 text-neutral-400 hover:text-white transition-colors rounded"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          {/* Account Details */}
          <div>
            <h3 className="text-sm font-medium text-neutral-400 mb-2">Account</h3>
            <div className="flex items-center gap-3 p-3 bg-neutral-800/50 rounded-lg border border-neutral-700/50">
              {hasClerk ? <UserAccountDetails /> : <GuestAccountDetails />}
            </div>
          </div>
        </div>

        <div className="flex justify-end mt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-neutral-800 hover:bg-neutral-700 text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

