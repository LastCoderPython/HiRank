'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Mail, ArrowRight, Loader2, CheckCircle2 } from 'lucide-react';
import Image from 'next/image';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useChats } from '@/hooks/use-chats';

type Step = 'email' | 'otp' | 'onboarding';

export function LandingAuth() {
  const { fetchSession } = useAuth();
  const { anonSessionId } = useChats();
  
  const [step, setStep] = useState<Step>('email');
  
  // Email state
  const [email, setEmail] = useState('');
  const [normalizedEmail, setNormalizedEmail] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  
  // OTP state
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [isVerifying, setIsVerifying] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  
  // Onboarding state
  const [exam, setExam] = useState('');
  const [rankOrPct, setRankOrPct] = useState('');
  const [category, setCategory] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Focus management
  const emailInputRef = useRef<HTMLInputElement>(null);
  
  useEffect(() => {
    if (step === 'email') {
      setTimeout(() => emailInputRef.current?.focus(), 100);
    } else if (step === 'otp') {
      setTimeout(() => inputRefs.current[0]?.focus(), 100);
    }
  }, [step]);

  // Timer
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (countdown > 0) {
      timer = setInterval(() => setCountdown(prev => prev - 1), 1000);
    }
    return () => clearInterval(timer);
  }, [countdown]);

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }
    
    setIsSending(true);
    setError('');
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000'}/api/auth/email/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Failed to send code');
      
      setNormalizedEmail(data.email || email);
      setStep('otp');
      setCountdown(30);
    } catch (err: any) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setIsSending(false);
    }
  };

  const handleVerify = async (codeStr: string) => {
    if (codeStr.length !== 6) return;
    
    setIsVerifying(true);
    setError('');
    
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000'}/api/auth/email/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email: normalizedEmail, 
          token: codeStr,
          session_id: anonSessionId
        })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Invalid code');
      
      // User is logged in via cookies now. Move to onboarding step.
      setStep('onboarding');
    } catch (err: any) {
      setError(err.message || 'Verification failed');
      setOtp(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } finally {
      setIsVerifying(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    
    const newOtp = [...otp];
    // Handle paste
    if (value.length > 1) {
      const pasted = value.slice(0, 6).split('');
      pasted.forEach((char, i) => {
        if (index + i < 6) newOtp[index + i] = char;
      });
      setOtp(newOtp);
      const nextIndex = Math.min(index + pasted.length, 5);
      inputRefs.current[nextIndex]?.focus();
      if (newOtp.join('').length === 6) {
        handleVerify(newOtp.join(''));
      }
      return;
    }

    newOtp[index] = value;
    setOtp(newOtp);

    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
    
    if (newOtp.join('').length === 6) {
      handleVerify(newOtp.join(''));
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleFinishOnboarding = async (skip: boolean) => {
    setIsSaving(true);
    try {
      const payload: any = { onboarding_complete: true };
      
      if (!skip) {
        if (exam) payload.exam = exam;
        if (category) payload.category = category;
        if (rankOrPct) {
          if (rankOrPct.includes('.')) {
            payload.percentile = parseFloat(rankOrPct);
          } else {
            payload.rank = parseInt(rankOrPct, 10);
          }
        }
      }
      
      await api.updateProfile(payload);
    } catch (err) {
      console.error("Failed to save onboarding", err);
    } finally {
      // Refresh AuthContext to flip isSignedIn to true and unmount LandingAuth
      await fetchSession(); 
    }
  };

  const handleGoogleLogin = () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';
    window.location.href = `${apiUrl}/api/auth/google`;
  };

  return (
    <div className="flex h-full w-full bg-[#0d0d0d] text-white">
      {/* Left side - Branding (Hidden on mobile) */}
      <div className="hidden md:flex md:w-1/2 flex-col justify-between p-12 bg-neutral-900/30 border-r border-neutral-800">
        <div>
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-lg shadow-white/10">
              <span className="text-black font-bold text-xl">R</span>
            </div>
            <span className="text-2xl font-bold tracking-tight">RankRoute</span>
          </div>
          <h1 className="text-5xl font-bold leading-[1.1] tracking-tight mb-6">
            Your personal guide to <br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">
              college admissions.
            </span>
          </h1>
          <p className="text-lg text-neutral-400 max-w-md">
            Stop guessing. Get deterministic college predictions based on real cutoff data, powered by AI.
          </p>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex -space-x-3">
            {[1,2,3,4].map((i) => {
              const zClasses = ['z-10', 'z-20', 'z-30', 'z-40'];
              return (
                <div key={i} className={`w-10 h-10 rounded-full border-2 border-[#0d0d0d] bg-neutral-800 ${zClasses[i-1]}`} />
              );
            })}
          </div>
          <div className="text-sm font-medium text-neutral-400">
            Join <span className="text-white">10,000+</span> students finding their right college
          </div>
        </div>
      </div>

      {/* Right side - Forms */}
      <div className="w-full md:w-1/2 flex items-center justify-center p-6 sm:p-12 relative overflow-hidden">
        <div className="w-full max-w-sm relative h-[400px]">
          
          {/* STEP 1: EMAIL */}
          <div className={`absolute inset-0 transition-all duration-500 flex flex-col justify-center ${
            step === 'email' ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-12 pointer-events-none'
          }`}>
            <div className="md:hidden flex items-center gap-3 mb-8">
              <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
                <span className="text-black font-bold">R</span>
              </div>
              <span className="text-xl font-bold">RankRoute</span>
            </div>
            
            <h2 className="text-2xl font-semibold mb-2">Welcome back</h2>
            <p className="text-neutral-400 mb-8">Enter your email to sign in or create an account</p>
            
            <form onSubmit={handleSendOtp} className="space-y-4">
              <div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-neutral-500" />
                  </div>
                  <input
                    ref={emailInputRef}
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full bg-neutral-900 border border-neutral-800 rounded-xl py-3.5 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all text-white placeholder-neutral-500"
                    disabled={isSending}
                    autoComplete="email"
                  />
                </div>
                {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
              </div>
              
              <button
                type="submit"
                disabled={isSending || !email}
                className="w-full bg-white text-black font-medium py-3.5 rounded-xl hover:bg-neutral-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isSending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>Continue with Email <ArrowRight className="w-4 h-4" /></>
                )}
              </button>
            </form>
            
            <div className="relative my-8">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-neutral-800"></div></div>
              <div className="relative flex justify-center text-sm"><span className="px-4 bg-[#0d0d0d] text-neutral-500">or</span></div>
            </div>
            
            <button
              onClick={handleGoogleLogin}
              className="w-full bg-transparent border border-neutral-800 text-white font-medium py-3 rounded-xl hover:bg-neutral-900 transition-colors flex items-center justify-center gap-3"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Continue with Google
            </button>

            <button
              onClick={() => {
                sessionStorage.setItem('guest_mode', 'true');
                window.location.reload();
              }}
              className="mt-6 w-full text-sm font-medium text-neutral-500 hover:text-white transition-colors"
            >
              Try without an account
            </button>
          </div>

          {/* STEP 2: OTP */}
          <div className={`absolute inset-0 transition-all duration-500 flex flex-col justify-center ${
            step === 'otp' ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-12 pointer-events-none'
          }`}>
            <button 
              onClick={() => { setStep('email'); setOtp(['','','','','','']); setError(''); }}
              className="text-neutral-400 hover:text-white transition-colors flex items-center gap-2 mb-6 w-fit -ml-2 p-2 rounded-lg hover:bg-neutral-900"
            >
              <ArrowRight className="w-4 h-4 rotate-180" /> Back
            </button>
            
            <h2 className="text-2xl font-semibold mb-2">Check your inbox</h2>
            <p className="text-neutral-400 mb-8">
              We sent a 6-digit code to <span className="text-white font-medium">{normalizedEmail}</span>
            </p>
            
            <div className="flex gap-2 sm:gap-3 mb-6">
              {otp.map((digit, i) => (
                <input
                  key={i}
                  ref={el => { inputRefs.current[i] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={digit}
                  onChange={e => handleOtpChange(i, e.target.value)}
                  onKeyDown={e => handleKeyDown(i, e)}
                  disabled={isVerifying}
                  className="w-10 sm:w-12 h-12 sm:h-14 bg-neutral-900 border border-neutral-700 rounded-lg text-center text-xl font-semibold text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 transition-colors"
                />
              ))}
            </div>
            
            {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
            
            <div className="flex items-center justify-between text-sm">
              <span className="text-neutral-500">Didn&apos;t receive the code?</span>
              <button 
                onClick={handleSendOtp}
                disabled={countdown > 0 || isVerifying || isSending}
                className="text-blue-400 font-medium hover:text-blue-300 disabled:text-neutral-600 disabled:cursor-not-allowed transition-colors"
              >
                {countdown > 0 ? `Resend in ${countdown}s` : 'Resend code'}
              </button>
            </div>
          </div>
          
          {/* STEP 3: ONBOARDING */}
          <div className={`absolute inset-0 transition-all duration-500 flex flex-col justify-center ${
            step === 'onboarding' ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-12 pointer-events-none'
          }`}>
            <div className="flex items-center gap-2 text-emerald-400 mb-2">
              <CheckCircle2 className="w-5 h-5" />
              <span className="font-medium">You&apos;re in!</span>
            </div>
            <h2 className="text-2xl font-semibold mb-2">Personalize your results</h2>
            <p className="text-neutral-400 mb-8">Just a few details to get the most accurate college predictions.</p>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-neutral-300 mb-3">Which exam?</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: 'JEE_MAIN', label: 'JEE Main' },
                    { id: 'JEE_ADV', label: 'JEE Adv' },
                    { id: 'NEET', label: 'NEET' },
                    { id: 'CEE', label: 'Assam CEE' },
                  ].map(e => (
                    <button
                      key={e.id}
                      onClick={() => setExam(e.id)}
                      className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                        exam === e.id 
                          ? 'bg-blue-500 text-white' 
                          : 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'
                      }`}
                    >
                      {e.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-neutral-300 mb-2">Rank or Percentile</label>
                  <input
                    type="text"
                    value={rankOrPct}
                    onChange={(e) => setRankOrPct(e.target.value.replace(/[^0-9.]/g, ''))}
                    placeholder="e.g. 4521 or 94.5"
                    className="w-full bg-neutral-900 border border-neutral-800 rounded-lg py-2.5 px-3 focus:outline-none focus:ring-1 focus:ring-blue-500 text-white placeholder-neutral-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-300 mb-3">Category</label>
                <div className="flex flex-wrap gap-2">
                  {['General', 'OBC', 'SC', 'ST', 'EWS'].map(c => (
                    <button
                      key={c}
                      onClick={() => setCategory(c)}
                      className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                        category === c 
                          ? 'bg-blue-500 text-white' 
                          : 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'
                      }`}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-8 flex gap-3">
              <button
                onClick={() => handleFinishOnboarding(true)}
                disabled={isSaving}
                className="flex-1 py-3 px-4 rounded-xl font-medium text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
              >
                Skip for now
              </button>
              <button
                onClick={() => handleFinishOnboarding(false)}
                disabled={isSaving || !exam}
                className="flex-1 bg-white text-black font-medium py-3 px-4 rounded-xl hover:bg-neutral-200 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isSaving ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Start Chatting'}
              </button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
