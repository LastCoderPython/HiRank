import AdminGuard from '@/components/admin-guard';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminGuard>
      <div className="h-dvh flex flex-col bg-neutral-900">
        {children}
      </div>
    </AdminGuard>
  );
}
