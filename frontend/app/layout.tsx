import type {Metadata} from 'next';
import { Inter } from 'next/font/google';
import { AuthProvider } from '@/lib/auth-context';
import { Toaster } from 'sonner';
import { Analytics } from '@vercel/analytics/next';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
});

export const metadata: Metadata = {
  title: 'RankRoute AI',
  description: 'Intelligent admission counseling system for engineering aspirants',
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <AuthProvider>
      <html lang="en" className={`dark ${inter.variable}`}>
        <body suppressHydrationWarning className="bg-neutral-900 text-neutral-100 font-sans antialiased h-dvh w-full overflow-hidden">
          {children}
          <Analytics />
          <Toaster theme="dark" position="bottom-right" />
        </body>
      </html>
    </AuthProvider>
  );
}
