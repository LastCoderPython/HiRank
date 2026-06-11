import { useState, useCallback, useEffect } from 'react';
import { api } from '@/lib/api';
import { Chat, Message } from '@/lib/types';
import { useAuth } from '@/lib/auth-context';

import FingerprintJS from '@fingerprintjs/fingerprintjs';

export function useChats() {
  const { isSignedIn, isLoaded: authLoaded } = useAuth();
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [anonSessionId, setAnonSessionId] = useState<string | null>(null);

  // Initialize anonymous session ID
  useEffect(() => {
    const initSession = async () => {
      if (typeof window === 'undefined') return;
      
      try {
        const fp = await FingerprintJS.load();
        const result = await fp.get();
        const visitorId = result.visitorId;
        localStorage.setItem('rankroute_session_id', visitorId);
        setAnonSessionId(visitorId);
      } catch (err) {
        // Fallback if FingerprintJS blocked
        let sid = localStorage.getItem('rankroute_session_id');
        if (!sid) {
          sid = crypto.randomUUID();
          localStorage.setItem('rankroute_session_id', sid);
        }
        setAnonSessionId(sid);
      }
    };
    initSession();
  }, []);

  const loadChats = useCallback(async () => {
    if (!isSignedIn) {
      if (anonSessionId) {
        try {
          const res = await api.getTempChat(anonSessionId);
          if (res.exists && res.chat) {
            setChats([{
              id: anonSessionId,
              title: res.chat.title || 'Temporary Chat',
              created_at: res.chat.created_at,
              updated_at: res.chat.updated_at
            }]);
          } else {
             setChats([]);
          }
        } catch (e) {
          console.error('Failed to load temp chat:', e);
        }
      }
      return;
    }

    setIsLoadingList(true);
    try {
      const res = await api.getChats();
      setChats(res.chats || []);
    } catch (error) {
      console.error('Failed to load chats:', error);
    } finally {
      setIsLoadingList(false);
    }
  }, [isSignedIn, anonSessionId]);

  // Initial load — inlined to avoid set-state-in-effect via indirect callback
  useEffect(() => {
    if (!authLoaded) return;

    const initialLoad = async () => {
      if (!isSignedIn) {
        if (anonSessionId) {
          try {
            const res = await api.getTempChat(anonSessionId);
            if (res.exists && res.chat) {
              setChats([{
                id: anonSessionId,
                title: res.chat.title || 'Temporary Chat',
                created_at: res.chat.created_at,
                updated_at: res.chat.updated_at
              }]);
            } else {
               setChats([]);
            }
          } catch (e) {
            console.error('Failed to load temp chat:', e);
          }
        }
        return;
      }

      setIsLoadingList(true);
      try {
        const res = await api.getChats();
        setChats(res.chats || []);
      } catch (error) {
        console.error('Failed to load chats:', error);
      } finally {
        setIsLoadingList(false);
      }
    };

    initialLoad();
  }, [authLoaded, isSignedIn, anonSessionId]);

  const selectChat = useCallback(async (chatId: string | null) => {
    setActiveChatId(chatId);
    if (!chatId) {
      setMessages([]);
      return;
    }

    setIsLoadingMessages(true);
    try {
      if (!isSignedIn && chatId === anonSessionId) {
        const res = await api.getTempChat(anonSessionId);
        setMessages(res.messages || []);
      } else {
        const res = await api.getChat(chatId);
        setMessages(res.messages || []);
      }
    } catch (error) {
      console.error('Failed to load chat messages:', error);
      setMessages([]);
    } finally {
      setIsLoadingMessages(false);
    }
  }, [isSignedIn, anonSessionId]);

  const createNewChat = useCallback(async (title = 'New Chat') => {
    if (!isSignedIn) {
      setActiveChatId(null);
      setMessages([]);
      const newSid = crypto.randomUUID();
      localStorage.setItem('rankroute_session_id', newSid);
      setAnonSessionId(newSid);
      setChats([]);
      return;
    }

    try {
      const res = await api.createChat(title);
      await loadChats();
      setActiveChatId(res.chat_id);
      setMessages([]);
      return res.chat_id;
    } catch (error) {
      console.error('Failed to create chat:', error);
    }
  }, [isSignedIn, loadChats]);

  const saveMessages = useCallback(async (userContent: string, assistantContent: string, metadata?: any) => {
    let currentChatId = activeChatId;

    if (!currentChatId) {
      if (isSignedIn) {
        const title = userContent.substring(0, 60) + (userContent.length > 60 ? '...' : '');
        const res = await api.createChat(title);
        currentChatId = res.chat_id;
        setActiveChatId(currentChatId);
      } else {
        currentChatId = anonSessionId;
        setActiveChatId(currentChatId);
      }
    }

    try {
      await api.saveMessage({
        chatId: isSignedIn ? currentChatId! : undefined,
        tempSessionId: !isSignedIn ? currentChatId! : undefined,
        role: 'user',
        content: userContent
      });

      await api.saveMessage({
        chatId: isSignedIn ? currentChatId! : undefined,
        tempSessionId: !isSignedIn ? currentChatId! : undefined,
        role: 'assistant',
        content: assistantContent,
        metadata
      });

      await selectChat(currentChatId);
      await loadChats();
    } catch (error) {
      console.error('Failed to save messages:', error);
    }
  }, [activeChatId, isSignedIn, anonSessionId, selectChat, loadChats]);

  const renameChat = useCallback(async (chatId: string, title: string) => {
    try {
      await api.renameChat(chatId, title);
      await loadChats();
    } catch (error) {
      console.error('Failed to rename chat:', error);
    }
  }, [loadChats]);

  const deleteChat = useCallback(async (chatId: string) => {
    try {
      await api.deleteChat(chatId);
      if (activeChatId === chatId) {
        setActiveChatId(null);
        setMessages([]);
      }
      await loadChats();
    } catch (error) {
      console.error('Failed to delete chat:', error);
    }
  }, [activeChatId, loadChats]);

  return {
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
    refreshChats: loadChats
  };
}
