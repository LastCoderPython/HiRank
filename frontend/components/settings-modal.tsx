'use client';

import React, { useState, useEffect } from 'react';
import { X, Loader2, User, Key } from 'lucide-react';
import Image from 'next/image';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

function GuestAccountDetails() {
  const handleSignUp = () => {
    sessionStorage.removeItem('guest_mode');
    window.location.reload();
  };

  return (
    <div className="w-full">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-full overflow-hidden shrink-0 relative bg-neutral-800 flex items-center justify-center border border-neutral-700">
          <User size={20} className="text-neutral-400" />
        </div>
        <div>
          <p className="text-sm font-medium text-white">Guest Account</p>
          <p className="text-xs text-neutral-400">Sign in to unlock all features</p>
        </div>
      </div>

      <div className="space-y-1 pl-1 mb-4">
        <p className="text-xs text-neutral-400">• Save your chat history</p>
        <p className="text-xs text-neutral-400">• Unlimited questions</p>
        <p className="text-xs text-neutral-400">• Personalized recommendations</p>
      </div>

      <button
        onClick={handleSignUp}
        className="w-full py-2.5 rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 transition-colors flex items-center justify-center gap-2"
      >
        <Key size={16} />
        Create Free Account
      </button>
    </div>
  );
}

export function SettingsModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { user, isSignedIn, signOut, updateProfile } = useAuth();
  
  const [isEditing, setIsEditing] = useState(false);
  const [state, setState] = useState(user?.home_state || '');
  const [whatsapp, setWhatsapp] = useState(user?.whatsapp_number || '');
  const [budgetRange, setBudgetRange] = useState(user?.budget_range || '');
  const [hostelRequired, setHostelRequired] = useState(user?.hostel_required ?? false);
  const [locationPref, setLocationPref] = useState(user?.location_preference || '');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  if (!isSignedIn) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200" role="dialog" aria-modal="true" aria-label="Settings">
        <div 
          className="w-full max-w-md bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
          onClick={e => e.stopPropagation()}
        >
          <div className="flex justify-between items-center p-4 border-b border-neutral-800 bg-neutral-900">
            <h2 className="text-lg font-semibold text-white">Settings</h2>
            <button onClick={onClose} className="p-1 rounded-md text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors" aria-label="Close settings">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="p-6">
            <div className="mb-6">
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Account</h3>
              <div className="p-3 bg-neutral-800/50 rounded-lg border border-neutral-700/50">
                <GuestAccountDetails />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const handleSave = async () => {
    if (!user) return;
    setIsSaving(true);
    try {
      await updateProfile({
        home_state: state || undefined,
        whatsapp_number: whatsapp || undefined,
        budget_range: budgetRange || undefined,
        hostel_required: hostelRequired || undefined,
        location_preference: locationPref || undefined,
      });
      setIsEditing(false);
    } catch (e) {
      console.error("Failed to save profile", e);
    } finally {
      setIsSaving(false);
    }
  };

  if (!user) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200" role="dialog" aria-modal="true" aria-label="Settings">
      <div 
        className="w-full max-w-md bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-4 border-b border-neutral-800 bg-neutral-900">
          <h2 className="text-lg font-semibold text-white">Settings</h2>
          <button onClick={onClose} className="p-1 rounded-md text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors" aria-label="Close settings">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 space-y-8 max-h-[80vh] overflow-y-auto">
          
          {/* Identity Section */}
          <div className="flex justify-between items-center w-full">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full overflow-hidden shrink-0 relative bg-neutral-800">
                {user.avatar_url ? (
                  <Image src={user.avatar_url} alt={user.name || "User"} fill referrerPolicy="no-referrer" className="object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <span className="text-xl font-medium text-neutral-300">{user.name?.[0]?.toUpperCase() || 'U'}</span>
                  </div>
                )}
              </div>
              <div>
                <p className="text-base font-medium text-white">{user.name || "User"}</p>
                <p className="text-sm text-neutral-400">{user.email || user.phone}</p>
              </div>
            </div>
            <button 
              onClick={signOut}
              className="text-xs text-red-400 font-medium px-4 py-2 rounded-lg border border-red-900/30 hover:bg-red-900/20 transition-colors"
            >
              Sign out
            </button>
          </div>

          <hr className="border-neutral-800" />

          {/* Exam Profile Section */}
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Exam Profile</h3>
            </div>
            {user.exam ? (
              <div className="bg-neutral-800/50 rounded-xl p-4 space-y-2 text-sm text-neutral-300">
                <div className="flex justify-between">
                  <span className="text-neutral-500">Exam</span>
                  <span className="font-medium text-white">{user.exam}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Rank / Percentile</span>
                  <span className="font-medium text-white">{user.percentile ? `${user.percentile} %ile` : (user.rank || 'N/A')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Category</span>
                  <span className="font-medium text-white">{user.category || 'General'}</span>
                </div>
              </div>
            ) : (
              <div className="bg-neutral-800/50 rounded-xl p-4 text-sm text-neutral-400">
                Not set — finish your profile in chat!
              </div>
            )}
          </div>

          <hr className="border-neutral-800" />

          {/* Preferences Section */}
          <div>
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Preferences</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-2 border-b border-neutral-800/50">
                <span className="text-neutral-500">Budget</span>
                <span className={user?.budget_range ? 'text-white' : 'text-neutral-600 italic'}>
                  {user?.budget_range || 'Not set'}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-neutral-800/50">
                <span className="text-neutral-500">Hostel</span>
                <span className={user?.hostel_required !== undefined ? 'text-white' : 'text-neutral-600 italic'}>
                  {user?.hostel_required === true ? 'Required' : user?.hostel_required === false ? 'Not required' : 'Not set'}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-neutral-800/50">
                <span className="text-neutral-500">Location</span>
                <span className={user?.location_preference ? 'text-white' : 'text-neutral-600 italic'}>
                  {user?.location_preference || 'Not set'}
                </span>
              </div>
            </div>
          </div>

          <hr className="border-neutral-800" />

          {/* Additional Details Section (Progressive Onboarding) */}
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Additional Details</h3>
              {!isEditing && (
                <button 
                  onClick={() => setIsEditing(true)}
                  className="text-xs text-blue-400 font-medium hover:text-blue-300"
                >
                  {user.home_state || user.whatsapp_number ? 'Edit' : 'Complete Profile'}
                </button>
              )}
            </div>

            {isEditing ? (
              <div className="space-y-4 bg-neutral-800/50 p-4 rounded-xl">
                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">Home State</label>
                  <select 
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    className="w-full bg-neutral-900 border border-neutral-700 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="">Select State</option>
                    <option value="Assam">Assam</option>
                    <option value="Delhi">Delhi</option>
                    <option value="Maharashtra">Maharashtra</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">WhatsApp Number (Optional)</label>
                  <input 
                    type="text"
                    value={whatsapp}
                    onChange={(e) => setWhatsapp(e.target.value)}
                    placeholder="+91..."
                    className="w-full bg-neutral-900 border border-neutral-700 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div className="pt-2 border-t border-neutral-700/50">
                  <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Preferences</h4>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-medium text-neutral-400 mb-1">Budget Range</label>
                      <div className="flex gap-2">
                        {['', 'low', 'medium', 'high'].map((b) => (
                          <button
                            key={b}
                            type="button"
                            onClick={() => setBudgetRange(b)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                              budgetRange === b
                                ? 'bg-blue-500/20 border-blue-500/50 text-blue-300'
                                : 'bg-neutral-900 border-neutral-700 text-neutral-400 hover:text-white'
                            }`}
                          >
                            {b || 'Any'}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-neutral-400 mb-1">Hostel Required</label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setHostelRequired(true)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                            hostelRequired === true
                              ? 'bg-blue-500/20 border-blue-500/50 text-blue-300'
                              : 'bg-neutral-900 border-neutral-700 text-neutral-400 hover:text-white'
                          }`}
                        >
                          Yes
                        </button>
                        <button
                          type="button"
                          onClick={() => setHostelRequired(false)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                            hostelRequired === false
                              ? 'bg-blue-500/20 border-blue-500/50 text-blue-300'
                              : 'bg-neutral-900 border-neutral-700 text-neutral-400 hover:text-white'
                          }`}
                        >
                          No
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-neutral-400 mb-1">Location Preference</label>
                      <select
                        value={locationPref}
                        onChange={(e) => setLocationPref(e.target.value)}
                        className="w-full bg-neutral-900 border border-neutral-700 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-blue-500"
                      >
                        <option value="">Any</option>
                        <option value="urban">Urban</option>
                        <option value="semi-urban">Semi-Urban</option>
                        <option value="rural">Rural</option>
                      </select>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end gap-2 mt-4">
                  <button 
                    onClick={() => setIsEditing(false)}
                    className="px-3 py-1.5 text-xs font-medium text-neutral-400 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={handleSave}
                    disabled={isSaving}
                    className="px-4 py-1.5 text-xs font-medium bg-white text-black rounded-lg hover:bg-neutral-200 transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {isSaving && <Loader2 className="w-3 h-3 animate-spin" />}
                    Save
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between py-2 border-b border-neutral-800/50">
                  <span className="text-neutral-500">State</span>
                  <span className={user.home_state ? 'text-white' : 'text-neutral-600 italic'}>
                    {user.home_state || 'Not set'}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b border-neutral-800/50">
                  <span className="text-neutral-500">WhatsApp</span>
                  <span className={user.whatsapp_number ? 'text-white' : 'text-neutral-600 italic'}>
                    {user.whatsapp_number || 'Not set'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
