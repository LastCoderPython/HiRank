'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '@/components/sidebar';
import { ChatArea } from '@/components/chat-area';
import { SettingsModal } from '@/components/settings-modal';
import { ClearChatsModal } from '@/components/clear-chats-modal';
import { cn } from '@/lib/utils';
import { LayoutPanelLeft } from 'lucide-react';

const initialChats = [
  { id: '1', group: 'Today', title: 'Best colleges for 150 marks in Assam CEE' },
  { id: '2', group: 'Today', title: 'Jorhat Engineering College cutoffs' },
  { id: '3', group: 'Today', title: 'JEE Mains vs Assam CEE counseling process' },
  { id: '4', group: 'Yesterday', title: 'AEC Civil Engineering placement stats' },
  { id: '5', group: 'Yesterday', title: 'Documents required for counseling' },
  { id: '6', group: 'Yesterday', title: 'How does the multi-agent system work?' },
  { id: '7', group: 'Last 7 Days', title: 'Previous year cutoff for NIT Silchar' },
  { id: '8', group: 'Last 7 Days', title: 'How to apply for state quota in JEE?' },
  { id: '9', group: 'Older', title: 'Preparation strategies for Physics' },
  { id: '10', group: 'Older', title: 'Understanding JoSAA round 1 results' },
];

export function ApplicationLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [sessionId, setSessionId] = useState(() => Date.now().toString());
  
  const [chats, setChats] = useState(initialChats);
  const [isClearChatsModalOpen, setIsClearChatsModalOpen] = useState(false);

  const handleRenameChat = (id: string, newTitle: string) => {
    setChats(chats.map(chat => chat.id === id ? { ...chat, title: newTitle } : chat));
  };

  const handleDeleteChat = (id: string) => {
    setChats(chats.filter(chat => chat.id !== id));
  };

  const handleClearAllChats = () => {
    setChats([]);
    setIsClearChatsModalOpen(false);
  };

  const handleNewSession = () => {
    setSessionId(Date.now().toString());
  };

  const toggleSidebar = React.useCallback(() => {
    const newState = !isSidebarOpen;
    setIsSidebarOpen(newState);
    if (!isMobile) {
      localStorage.setItem('sidebarOpen', String(newState));
    }
  }, [isSidebarOpen, isMobile]);

  useEffect(() => {
    // Determine initial state from local storage or default to true on desktop
    const timer = setTimeout(() => {
      const savedState = localStorage.getItem('sidebarOpen');
      const isMobileView = window.innerWidth < 768;
      setIsMobile(isMobileView);
      
      if (isMobileView) {
        setIsSidebarOpen(false); // Always start closed on mobile
      } else if (savedState !== null) {
        setIsSidebarOpen(savedState === 'true');
      } else {
        setIsSidebarOpen(true);
      }
      
      setIsInitialized(true);
    }, 0);

    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      // Only force close if crossing the breakpoint from desktop to mobile
      if (mobile && !isMobile) {
        setIsSidebarOpen(false);
      }
      setIsMobile(mobile);
    };
    
    window.addEventListener('resize', handleResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
    }
  }, [isMobile]);

  // Keyboard shortcut for toggling sidebar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + Shift + S
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 's') {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar]);

  if (!isInitialized) return null; // Prevent hydration mismatch

  return (
    <div className="flex h-full w-full overflow-hidden bg-neutral-900 text-neutral-100">
      
      {/* Sidebar - Desktop and Mobile are handled inside */}
      {/* For desktop, we wrap it in a container that animates width to push content */}
      <div 
        className={cn(
          "shrink-0 transition-all duration-300 ease-in-out relative z-40 hidden md:block",
          isSidebarOpen ? "w-[260px]" : "w-0"
        )}
      >
        <div className={cn(
          "absolute top-0 left-0 h-full w-[260px] transition-transform duration-300 ease-in-out",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}>
          <Sidebar 
            isOpen={isSidebarOpen} 
            onToggle={toggleSidebar} 
            isMobile={false} 
            onOpenSettings={() => setIsSettingsOpen(true)} 
            onOpenClearChats={() => setIsClearChatsModalOpen(true)}
            onNewSession={handleNewSession}
            chats={chats}
            onRenameChat={handleRenameChat}
            onDeleteChat={handleDeleteChat}
          />
        </div>
      </div>

      {/* Mobile Sidebar */}
      <div className="md:hidden">
        <Sidebar 
          isOpen={isSidebarOpen} 
          onToggle={toggleSidebar} 
          isMobile={true} 
          onOpenSettings={() => setIsSettingsOpen(true)} 
          onOpenClearChats={() => setIsClearChatsModalOpen(true)}
          onNewSession={handleNewSession}
          chats={chats}
          onRenameChat={handleRenameChat}
          onDeleteChat={handleDeleteChat}
        />
      </div>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 h-full relative transition-all duration-300">
        <ChatArea key={sessionId} isSidebarOpen={isSidebarOpen} onToggleSidebar={toggleSidebar} isMobile={isMobile} onOpenSettings={() => setIsSettingsOpen(true)} />
      </main>
      
      {/* Global Modals */}
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      <ClearChatsModal isOpen={isClearChatsModalOpen} onClose={() => setIsClearChatsModalOpen(false)} onConfirm={handleClearAllChats} />
    </div>
  );
}
