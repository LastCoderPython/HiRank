import type {Metadata} from 'next';
import { Inter } from 'next/font/google';
import { ClerkProvider } from '@clerk/nextjs';
import { Toaster } from 'sonner';
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
  const hasClerkKeys = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  if (!hasClerkKeys) {
    return (
      <html lang="en" className={`dark ${inter.variable}`}>
        <body suppressHydrationWarning className="bg-neutral-900 text-neutral-100 font-sans antialiased h-dvh w-full overflow-hidden">
          {children}
          <Toaster theme="dark" position="bottom-right" />
        </body>
      </html>
    );
  }

  return (
    <ClerkProvider>
      <html lang="en" className={`dark ${inter.variable}`}>
        <body suppressHydrationWarning className="bg-neutral-900 text-neutral-100 font-sans antialiased h-dvh w-full overflow-hidden">
          {children}
          <Toaster theme="dark" position="bottom-right" />
        </body>
      </html>
    </ClerkProvider>
  );
}
