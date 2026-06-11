'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '@/components/sidebar';
import { ChatArea } from '@/components/chat-area';
import { SettingsModal } from '@/components/settings-modal';
import { ClearChatsModal } from '@/components/clear-chats-modal';
import { cn } from '@/lib/utils';
import { useChats } from '@/hooks/use-chats';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

export function ApplicationLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isClearChatsModalOpen, setIsClearChatsModalOpen] = useState(false);

  const { isSignedIn } = useAuth();
  const {
    chats,
    messages,
    activeChatId,
    anonSessionId,
    isLoadingList,
    isLoadingMessages,
    selectChat,
    createNewChat,
    saveMessages,
    renameChat,
    deleteChat,
    refreshChats
  } = useChats();

  const handleClearAllChats = async () => {
    if (isSignedIn) {
      try {
        await api.clearAllChats();
        await refreshChats();
      } catch (e) {
        console.error('Failed to clear chats:', e);
      }
    }
    setIsClearChatsModalOpen(false);
  };

  const toggleSidebar = React.useCallback(() => {
    const newState = !isSidebarOpen;
    setIsSidebarOpen(newState);
    if (!isMobile) {
      localStorage.setItem('sidebarOpen', String(newState));
    }
  }, [isSidebarOpen, isMobile]);

  useEffect(() => {
    const timer = setTimeout(() => {
      const savedState = localStorage.getItem('sidebarOpen');
      const isMobileView = window.innerWidth < 768;
      setIsMobile(isMobileView);
      
      if (isMobileView) {
        setIsSidebarOpen(false);
      } else if (savedState !== null) {
        setIsSidebarOpen(savedState === 'true');
      } else {
        setIsSidebarOpen(true);
      }
      
      setIsInitialized(true);
    }, 0);

    const handleResize = () => {
      const mobile = window.innerWidth < 768;
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

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 's') {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar]);

  if (!isInitialized) return null;

  return (
    <div className="flex h-full w-full overflow-hidden bg-neutral-900 text-neutral-100">
      
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
            onNewSession={() => createNewChat()}
            chats={chats}
            activeChatId={activeChatId}
            onSelectChat={selectChat}
            isLoading={isLoadingList}
            onRenameChat={renameChat}
            onDeleteChat={deleteChat}
          />
        </div>
      </div>

      <div className="md:hidden">
        <Sidebar 
          isOpen={isSidebarOpen} 
          onToggle={toggleSidebar} 
          isMobile={true} 
          onOpenSettings={() => setIsSettingsOpen(true)} 
          onOpenClearChats={() => setIsClearChatsModalOpen(true)}
          onNewSession={() => createNewChat()}
          chats={chats}
          activeChatId={activeChatId}
          onSelectChat={selectChat}
          isLoading={isLoadingList}
          onRenameChat={renameChat}
          onDeleteChat={deleteChat}
        />
      </div>

      <main className="flex-1 flex flex-col min-w-0 h-full relative transition-all duration-300">
        <ChatArea 
          isSidebarOpen={isSidebarOpen} 
          onToggleSidebar={toggleSidebar} 
          isMobile={isMobile} 
          onOpenSettings={() => setIsSettingsOpen(true)}
          messages={messages}
          isLoadingMessages={isLoadingMessages}
          activeChatId={activeChatId}
          sessionId={anonSessionId}
          onStreamComplete={saveMessages}
        />
      </main>
      
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      <ClearChatsModal isOpen={isClearChatsModalOpen} onClose={() => setIsClearChatsModalOpen(false)} onConfirm={handleClearAllChats} />
    </div>
  );
}
