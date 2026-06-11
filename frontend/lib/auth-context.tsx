'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { AuthUser } from '@/lib/types';

interface AuthContextValue {
  isLoaded: boolean;
  isSignedIn: boolean;
  isOnboardingComplete: boolean;
  user: AuthUser | null;
  signIn: () => void;
  signOut: () => Promise<void>;
  fetchSession: () => Promise<void>;
  updateProfile: (data: Partial<AuthUser>) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);

  const fetchSession = useCallback(async () => {
    try {
      // First check auth session
      const authRes = await api.fetchSession();
      if (authRes.authenticated) {
        // Fetch full profile from db
        try {
          const profile = await api.getProfile();
          setUser(profile);
        } catch (err) {
          // Fallback if profile doesn't exist yet
          setUser(authRes.user);
        }
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  // Initial session fetch — inlined to avoid react-hooks/set-state-in-effect
  useEffect(() => {
    const initSession = async () => {
      try {
        const authRes = await api.fetchSession();
        if (authRes.authenticated) {
          try {
            const profile = await api.getProfile();
            setUser(profile);
          } catch {
            setUser(authRes.user);
          }
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setIsLoaded(true);
      }
    };

    initSession();
  }, []);

  const updateProfile = useCallback(async (data: Partial<AuthUser>) => {
    try {
      await api.updateProfile(data);
      await fetchSession(); // Refresh context
    } catch (err) {
      console.error("Failed to update profile", err);
      throw err;
    }
  }, [fetchSession]);

  const signIn = useCallback(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';
    window.location.href = `${apiUrl}/api/auth/google`;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.signOut();
    } catch {
      // Logout failed — clear local state anyway
    }
    setUser(null);
    // Optional: reload window to clear all app state
    window.location.reload();
  }, []);

  return (
    <AuthContext.Provider value={{ 
      isLoaded, 
      isSignedIn: !!user, 
      isOnboardingComplete: !!user?.onboarding_complete,
      user, 
      signIn, 
      signOut, 
      fetchSession,
      updateProfile
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
