'use client';

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { getSession, logout as apiLogout, User, refreshSession } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const checkAuth = useCallback(async () => {
    try {
      const result = await getSession();
      if (result.authenticated && result.user) {
        setUser(result.user);
      } else {
        setUser(null);
        
        const refreshResult = await refreshSession();
        if (refreshResult.success) {
          const retryResult = await getSession();
          if (retryResult.authenticated && retryResult.user) {
            setUser(retryResult.user);
          }
        }
      }
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = useCallback(() => {
    const loginUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000'}/api/auth/google`;
    window.location.href = loginUrl;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
      setUser(null);
      router.push('/');
    } catch {
      setUser(null);
      router.push('/');
    }
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
