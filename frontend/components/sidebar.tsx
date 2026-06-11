'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Plus, LayoutPanelLeft, Pencil, Trash2, Check, X, Settings, User, Loader2, Shield } from 'lucide-react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';
import Image from 'next/image';
import { Chat } from '@/lib/types';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  isMobile: boolean;
  onOpenSettings: () => void;
  onOpenClearChats: () => void;
  onNewSession: () => void;
  chats: Chat[];
  activeChatId: string | null;
  onSelectChat: (id: string | null) => void;
  isLoading: boolean;
  onRenameChat: (id: string, newTitle: string) => void;
  onDeleteChat: (id: string) => void;
}

interface ChatItemProps {
  id: string;
  title: string;
  isActive: boolean;
  onSelect: (id: string) => void;
  onRename: (id: string, newTitle: string) => void;
  onDelete: (id: string) => void;
}

function ChatItem({ id, title, isActive, onSelect, onRename, onDelete }: ChatItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(title);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  const handleSaveRename = () => {
    if (editValue.trim() !== '') {
      onRename(id, editValue);
    } else {
      setEditValue(title);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSaveRename();
    if (e.key === 'Escape') {
      setEditValue(title);
      setIsEditing(false);
    }
  };

  return (
    <div 
      className={cn(
        "group relative flex items-center w-full p-2 rounded-lg transition-colors text-sm cursor-pointer",
        isActive ? "bg-neutral-800 text-white" : "hover:bg-neutral-800 text-neutral-200"
      )}
      onClick={() => {
        if (!isEditing && !isConfirmingDelete) {
          onSelect(id);
        }
      }}
    >
      {isEditing ? (
        <div className="flex-1 w-full relative z-10 bg-neutral-800 rounded">
          <input
            ref={inputRef}
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            onBlur={handleSaveRename}
            onKeyDown={handleKeyDown}
            className="w-full bg-transparent outline-none text-sm text-white m-0 p-0"
            onClick={e => e.stopPropagation()}
          />
        </div>
      ) : (
        <>
          <div className="relative grow overflow-hidden whitespace-nowrap text-ellipsis pr-8">
            {title}
            <div className="absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-black group-hover:from-neutral-800 to-transparent pointer-events-none" />
          </div>
          
          <div className={cn(
            "absolute right-2 flex items-center gap-1 bg-neutral-800 pl-2",
            isConfirmingDelete 
              ? "opacity-100 scale-100 animate-subtle-bounce" 
              : "opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-all duration-200 scale-95 group-hover:scale-100"
          )}>
            {isConfirmingDelete ? (
              <>
                <button className="p-1 text-green-400 hover:text-green-300 transition-colors rounded bg-neutral-800" title="Confirm Delete" onClick={(e) => { e.stopPropagation(); onDelete(id); }}>
                  <Check size={14} />
                </button>
                <button className="p-1 text-neutral-400 hover:text-white transition-colors rounded bg-neutral-800" title="Cancel" onClick={(e) => { e.stopPropagation(); setIsConfirmingDelete(false); }}>
                  <X size={14} />
                </button>
              </>
            ) : (
              <>
                <button className="p-1 text-neutral-400 hover:text-white transition-colors rounded bg-neutral-800" title="Rename" onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}>
                  <Pencil size={14} />
                </button>
                <button className="p-1 text-neutral-400 hover:text-red-400 transition-colors rounded bg-neutral-800" title="Delete" onClick={(e) => { e.stopPropagation(); setIsConfirmingDelete(true); }}>
                  <Trash2 size={14} />
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export function Sidebar({ 
  isOpen, 
  onToggle, 
  isMobile, 
  onOpenSettings, 
  onOpenClearChats, 
  onNewSession, 
  chats, 
  activeChatId,
  onSelectChat,
  isLoading,
  onRenameChat, 
  onDeleteChat 
}: SidebarProps) {
  const { isSignedIn, user } = useAuth();
  
  const groupedChats = useMemo(() => {
    const groups = {
      today: [] as Chat[],
      yesterday: [] as Chat[],
      last7Days: [] as Chat[],
      older: [] as Chat[]
    };
    
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const last7Days = new Date(today);
    last7Days.setDate(last7Days.getDate() - 7);
    
    chats.forEach(chat => {
      const d = new Date(chat.updated_at || chat.created_at || 0);
      if (d >= today) {
        groups.today.push(chat);
      } else if (d >= yesterday) {
        groups.yesterday.push(chat);
      } else if (d >= last7Days) {
        groups.last7Days.push(chat);
      } else {
        groups.older.push(chat);
      }
    });
    return groups;
  }, [chats]);

  return (
    <>
      {isMobile && isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 transition-opacity"
          onClick={onToggle}
        />
      )}

      <div 
        className={cn(
          "flex flex-col h-full bg-black w-[260px] shrink-0",
          isMobile ? "fixed z-50 top-0 left-0 transition-transform duration-300 ease-in-out" : "relative z-0",
          isMobile && (isOpen ? "translate-x-0" : "-translate-x-full")
        )}
      >
        <div className="flex items-center justify-between p-3 gap-2 h-14">
          <button 
            className="flex items-center justify-between hover:bg-neutral-800 rounded-lg p-2 transition-colors flex-1 text-sm font-medium h-10"
            title="Start a new conversation"
            onClick={() => {
              onNewSession();
              if (isMobile) onToggle();
            }}
          >
            <div className="flex items-center gap-2">
              <div className="bg-white rounded-full p-[2px]">
                <Image src="https://picsum.photos/seed/rankroute/32/32" alt="RankRoute AI logo" width={24} height={24} className="rounded-full invert" referrerPolicy="no-referrer" />
              </div>
              <span>New Session</span>
            </div>
            <Plus size={16} />
          </button>
          
          <button 
            onClick={onToggle}
            className="p-2 hover:bg-neutral-800 rounded-lg transition-colors text-neutral-400 hover:text-neutral-200"
            title="Close sidebar (⌘+Shift+S)"
          >
            <LayoutPanelLeft size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 space-y-4 py-2 custom-scrollbar">
          
          {isLoading && chats.length === 0 ? (
            <div className="flex justify-center items-center py-10">
               <Loader2 className="animate-spin text-neutral-500" size={24} />
            </div>
          ) : (
            <>
              {groupedChats.today.length > 0 && (
                <div>
                  <h3 className="px-2 text-xs font-semibold text-neutral-500 mb-1 sticky top-0 bg-black py-2 z-10">Today</h3>
                  <div className="space-y-[2px]">
                    {groupedChats.today.map((chat) => (
                      <ChatItem key={chat.id} {...chat} isActive={activeChatId === chat.id} onSelect={onSelectChat} onRename={onRenameChat} onDelete={onDeleteChat} />
                    ))}
                  </div>
                </div>
              )}

              {groupedChats.yesterday.length > 0 && (
                <div>
                  <h3 className="px-2 text-xs font-semibold text-neutral-500 mb-1 sticky top-0 bg-black py-2 z-10 mt-4">Yesterday</h3>
                  <div className="space-y-[2px]">
                    {groupedChats.yesterday.map((chat) => (
                      <ChatItem key={chat.id} {...chat} isActive={activeChatId === chat.id} onSelect={onSelectChat} onRename={onRenameChat} onDelete={onDeleteChat} />
                    ))}
                  </div>
                </div>
              )}
              
              {groupedChats.last7Days.length > 0 && (
                <div>
                  <h3 className="px-2 text-xs font-semibold text-neutral-500 mb-1 sticky top-0 bg-black py-2 z-10 mt-4">Last 7 Days</h3>
                  <div className="space-y-[2px]">
                    {groupedChats.last7Days.map((chat) => (
                      <ChatItem key={chat.id} {...chat} isActive={activeChatId === chat.id} onSelect={onSelectChat} onRename={onRenameChat} onDelete={onDeleteChat} />
                    ))}
                  </div>
                </div>
              )}

              {groupedChats.older.length > 0 && (
                <div>
                  <h3 className="px-2 text-xs font-semibold text-neutral-500 mb-1 sticky top-0 bg-black py-2 z-10 mt-4">Older</h3>
                  <div className="space-y-[2px]">
                    {groupedChats.older.map((chat) => (
                      <ChatItem key={chat.id} {...chat} isActive={activeChatId === chat.id} onSelect={onSelectChat} onRename={onRenameChat} onDelete={onDeleteChat} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          
        </div>

        <div className="p-3 flex flex-col gap-1">
          {user?.role === 'admin' && (
            <Link href="/admin" className="flex items-center gap-2 px-3 py-2 text-sm text-neutral-400 hover:text-white hover:bg-neutral-800 rounded-lg transition-colors">
              <Shield className="w-4 h-4" />
              <span>Admin Panel</span>
            </Link>
          )}
          {chats.length > 0 && (
            <button 
              onClick={() => onOpenClearChats()}
              className="w-full flex items-center gap-2 p-2 hover:bg-neutral-800 rounded-lg transition-colors text-sm font-medium text-neutral-400 hover:text-white"
            >
              <Trash2 size={16} />
              <span className="flex-1 text-left">Clear All Chats</span>
            </button>
          )}
          <div className="w-full flex items-center gap-2 p-2 hover:bg-neutral-800 rounded-lg transition-colors text-sm font-medium">
            {isSignedIn && user ? (
              <div className="w-8 h-8 rounded-full overflow-hidden shrink-0 relative bg-neutral-800 flex items-center justify-center border border-neutral-700">
                {user.avatar_url ? (
                  <Image src={user.avatar_url} alt={user.name} fill referrerPolicy="no-referrer" className="object-cover" />
                ) : (
                  <span className="text-sm font-medium text-neutral-200">{user.name?.[0]?.toUpperCase() || '?'}</span>
                )}
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center border border-neutral-700 shrink-0">
                 <User size={16} className="text-neutral-400" />
              </div>
            )}
            <div className="flex-1 text-left truncate">{isSignedIn && user ? user.name : 'My Account'}</div>
            <button 
              onClick={(e) => { e.stopPropagation(); onOpenSettings(); }}
              className="p-1.5 hover:bg-neutral-700 rounded-md transition-colors text-neutral-400 hover:text-white shrink-0"
              title="Settings"
            >
              <Settings size={16} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
