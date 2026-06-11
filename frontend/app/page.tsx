'use client';

import { useAuth } from '@/lib/auth-context';
import { ApplicationLayout } from '@/components/application-layout';
import { LandingAuth } from '@/components/landing-auth';
import { useState } from 'react';

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const [isGuestMode, setIsGuestMode] = useState(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('guest_mode') === 'true';
    }
    return false;
  });

  if (!isLoaded) return (
    <div className="flex h-full w-full items-center justify-center bg-[#0d0d0d]">
      <div className="w-6 h-6 rounded-full border-2 border-neutral-600 border-t-white animate-spin" />
    </div>
  );

  if (!isSignedIn && !isGuestMode) return <LandingAuth />;
  return <ApplicationLayout />;
}
