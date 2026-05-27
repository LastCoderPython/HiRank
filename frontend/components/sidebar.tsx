'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Plus, MessageSquare, MoreHorizontal, LayoutPanelLeft, Pencil, Trash2, Check, X, Settings, User } from 'lucide-react';
import { UserButton, useUser } from '@clerk/nextjs';
import { cn } from '@/lib/utils';
import Image from 'next/image';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  isMobile: boolean;
  onOpenSettings: () => void;
  onOpenClearChats: () => void;
  onNewSession: () => void;
  chats: { id: string; group: string; title: string }[];
  onRenameChat: (id: string, newTitle: string) => void;
  onDeleteChat: (id: string) => void;
}

interface ChatItemProps {
  id: string;
  title: string;
  onRename: (id: string, newTitle: string) => void;
  onDelete: (id: string) => void;
}

function ChatItem({ id, title, onRename, onDelete }: ChatItemProps) {
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
      setEditValue(title); // Revert to original if empty
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
    <div className="group relative flex items-center w-full p-2 rounded-lg hover:bg-neutral-800 transition-colors text-sm text-neutral-200 cursor-pointer">
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
            {/* Fade effect for long text */}
            <div className="absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-black group-hover:from-neutral-800 to-transparent pointer-events-none" />
          </div>
          
          {/* Quick Actions (visible on hover) */}
          <div className={cn(
            "absolute right-2 flex items-center gap-1 bg-neutral-800 pl-2",
            isConfirmingDelete 
              ? "opacity-100 scale-100 animate-subtle-bounce" 
              : "opacity-0 group-hover:opacity-100 transition-all duration-200 scale-95 group-hover:scale-100"
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

export function Sidebar({ isOpen, onToggle, isMobile, onOpenSettings, onOpenClearChats, onNewSession, chats, onRenameChat, onDeleteChat }: SidebarProps) {
  const todayChats = chats.filter(c => c.group === 'Today');
  const yesterdayChats = chats.filter(c => c.group === 'Yesterday');
  const last7DaysChats = chats.filter(c => c.group === 'Last 7 Days');
  const olderChats = chats.filter(c => c.group === 'Older');
  return (
    <>
      {/* Mobile overlay */}
      {isMobile && isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 transition-opacity"
          onClick={onToggle}
        />
      )}

      {/* Sidebar container */}
      <div 
        className={cn(
          "flex flex-col h-full bg-black w-[260px] shrink-0",
          isMobile ? "fixed z-50 top-0 left-0 transition-transform duration-300 ease-in-out" : "relative z-0",
          isMobile && (isOpen ? "translate-x-0" : "-translate-x-full")
        )}
      >
        {/* Top Header */}
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
          
          {/* Toggle button inside sidebar (desktop only mostly, or mobile close) */}
          <button 
            onClick={onToggle}
            className="p-2 hover:bg-neutral-800 rounded-lg transition-colors text-neutral-400 hover:text-neutral-200"
            title="Close sidebar (⌘+Shift+S)"
          >
            <LayoutPanelLeft size={20} />
          </button>
        </div>

        {/* Chat History List */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 space-y-4 py-2 custom-scrollbar">
          
          {todayChats.length > 0 && (
            <div>
              <h3 className="px-2 text-xs font-semibold text-neutral-500 mb-1 sticky top-0 bg-black py-2 z-10">Today</h3>
              <div className="space-y-[2px]">
                {todayChats.map((chat) => (
                  <ChatItem key={chat.id} {...chat} onRename={onRenameChat} onDelete={onDeleteChat} />
                ))}
              </div>
            </div>
          )}

          {yesterdayChats.length > 0 && (
            <div>
              <h3 className="px-2 text-xs font-semibold text-neutral-500 mb-1 sticky top-0 bg-black py-2 z-10 mt-4">Yesterday</h3>
              <div className="space-y-[2px]">
                {yesterdayChats.map((chat) => (
                  <ChatItem key={chat.id} {...chat} onRename={onRenameChat} onDelete={onDeleteChat} />
                ))}
              </div>
            </div>
          )}
          
          {last7DaysChats.length > 0 && (
            <div>
              <h3 className="px-2 text-xs font-semibold text-neutral-500 mb-1 sticky top-0 bg-black py-2 z-10 mt-4">Last 7 Days</h3>
              <div className="space-y-[2px]">
                {last7DaysChats.map((chat) => (
                  <ChatItem key={chat.id} {...chat} onRename={onRenameChat} onDelete={onDeleteChat} />
                ))}
              </div>
            </div>
          )}

          {olderChats.length > 0 && (
            <div>
              <h3 className="px-2 text-xs font-semibold text-neutral-500 mb-1 sticky top-0 bg-black py-2 z-10 mt-4">Older</h3>
              <div className="space-y-[2px]">
                {olderChats.map((chat) => (
                  <ChatItem key={chat.id} {...chat} onRename={onRenameChat} onDelete={onDeleteChat} />
                ))}
              </div>
            </div>
          )}
          
        </div>

        {/* Bottom Profile Section */}
        <div className="p-3 flex flex-col gap-1">
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
            {process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ? (
              <UserButton appearance={{ elements: { userButtonAvatarBox: "w-8 h-8" } }} />
            ) : (
              <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center border border-neutral-700 shrink-0">
                 <User size={16} className="text-neutral-400" />
              </div>
            )}
            <div className="flex-1 text-left truncate">My Account</div>
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
