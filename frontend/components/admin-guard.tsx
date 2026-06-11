'use client';
import { useAuth } from '@/lib/auth-context';
import { Loader2, ShieldX } from 'lucide-react';

export default function AdminGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoaded } = useAuth();
  if (!isLoaded) return <div className="flex items-center justify-center h-screen"><Loader2 className="w-8 h-8 animate-spin text-neutral-400" /></div>;
  if (!user || user.role !== 'admin') return (
    <div className="flex flex-col items-center justify-center h-screen text-neutral-400 gap-4">
      <ShieldX className="w-16 h-16 text-red-500" />
      <h1 className="text-2xl font-bold text-white">Access Denied</h1>
      <p>Admin privileges required.</p>
    </div>
  );
  return <>{children}</>;
}
