'use client';

import React, { useRef, useEffect, useState, useMemo } from 'react';
import { LayoutPanelLeft, ChevronDown, Paperclip, ArrowUp, Copy, RefreshCw, ThumbsUp, ThumbsDown, Settings, Loader2, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import Image from 'next/image';
import { toast } from 'sonner';

import { useAuth } from '@/lib/auth-context';
import { TypewriterGreeting } from '@/components/typewriter-greeting';
import { SimulatorModal } from '@/components/simulator-modal';
import { Message } from '@/lib/types';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Custom renderer for Markdown links to look like Perplexity citation pills
const CustomCitationPill = ({ href, children }: { href?: string, children?: React.ReactNode }) => {
  if (!href) return <span>{children}</span>;
  
  try {
    const url = new URL(href);
    const domain = url.hostname.replace('www.', '');
    
    return (
      <a 
        href={href} 
        target="_blank" 
        rel="noopener noreferrer"
        className="inline-flex items-center mx-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-neutral-800 text-neutral-300 hover:bg-neutral-700 hover:text-white transition-colors border border-neutral-700/50 align-middle no-underline"
        title={href}
      >
        {domain}
      </a>
    );
  } catch (e) {
    // Fallback if URL parsing fails
    return <a href={href} className="text-blue-400 hover:underline">{children}</a>;
  }
};

interface ChatAreaProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  isMobile: boolean;
  onOpenSettings: () => void;
  messages: Message[];
  isLoadingMessages: boolean;
  activeChatId: string | null;
  sessionId: string | null;
  onStreamComplete: (userContent: string, assistantContent: string, metadata?: Record<string, unknown>) => Promise<void>;
}

export function ChatArea({ 
  isSidebarOpen, 
  onToggleSidebar, 
  isMobile, 
  onOpenSettings,
  messages,
  isLoadingMessages,
  activeChatId,
  sessionId,
  onStreamComplete
}: ChatAreaProps) {
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessages, setStreamingMessages] = useState<Message[] | null>(null);
  const [simulatorOpen, setSimulatorOpen] = useState(false);

  const handleSimulatorSend = (msg: string) => {
    setInputValue(msg);
    setTimeout(() => {
      const form = textareaRef.current?.closest('form');
      if (form) {
        form.requestSubmit?.();
      } else {
        handleSubmit();
      }
    }, 100);
  };
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const displayMessages = useMemo<Message[]>(() => {
    return streamingMessages ?? messages;
  }, [messages, streamingMessages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [displayMessages]);

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${scrollHeight}px`;
      textareaRef.current.style.overflowY = textareaRef.current.scrollHeight > 200 ? 'auto' : 'hidden';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming) {
        handleSubmit();
      }
    }
  };

  const handleSubmit = async () => {
    if (!inputValue.trim() || isStreaming) return;

    const query = inputValue.trim();
    const tempUserMsg: Message = { id: `temp-${Date.now()}`, role: 'user', content: query, created_at: new Date().toISOString() };
    setStreamingMessages([...messages, tempUserMsg]);
    setInputValue('');
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost';

    const tempAsstMsg: Message = { id: `temp-${Date.now()}-ai`, role: 'assistant', content: '', created_at: new Date().toISOString() };
    setStreamingMessages(prev => [...(prev ?? []), tempAsstMsg]);
    setIsStreaming(true);

    try {
      const { fetchEventSource } = await import('@microsoft/fetch-event-source');
      let streamContent = '';
      let streamMetadata: Record<string, unknown> | undefined = undefined;
      let authBlocked = false;
      
      const requestHistory = [...messages.slice(-9), { role: 'user', content: query }].map(m => ({ role: m.role, content: m.content }));

      await fetchEventSource(`${apiUrl}/api/v1/chat`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({ 
          message: query,
          session_id: sessionId || undefined,
          history: requestHistory
        }),
        onmessage(msg) {
          if (msg.event === 'error') {
            throw new Error(msg.data);
          }
          
          if (msg.data) {
            try {
              const parsed = JSON.parse(msg.data);
              if (parsed.type === 'auth_required') {
                authBlocked = true;
                setStreamingMessages(null);
                toast.error("You've used all 3 free prompts. Sign in to continue.", {
                  action: { label: '📱 Sign in', onClick: () => onOpenSettings() },
                  duration: Infinity,
                });
                return;
              }
              if (parsed.type === 'colleges') {
                streamMetadata = { colleges: parsed.data };
              }
              if (parsed.type === 'error') {
                throw new Error(parsed.data);
              }
              
              const textChunk = parsed.data || parsed.text || parsed.content || parsed.chunk || '';
              if (parsed.type === 'token') {
                streamContent += textChunk;
              } else if (typeof parsed === 'string') {
                 streamContent += parsed;
              }
            } catch (e) {
              streamContent += msg.data;
            }
            
            if (!authBlocked) {
              setStreamingMessages(prev => {
                if (!prev) return prev;
                const clone = [...prev];
                clone[clone.length - 1] = { ...clone[clone.length - 1], content: streamContent };
                return clone;
              });
            }
          }
        },
        onerror(err) {
          console.error("SSE Error:", err);
          toast.error("Failed to connect to AI backend.");
        }
      });

      if (!authBlocked && streamContent) {
        await onStreamComplete(query, streamContent, streamMetadata);
      }
    } catch (error) {
      console.error('Chat error:', error);
      toast.error('An error occurred while fetching the response.');
      setStreamingMessages(null);
    } finally {
      setIsStreaming(false);
      setStreamingMessages(null);
    }
  };

  return (
    <div className="flex flex-col h-full w-full relative">
      <header className="sticky top-0 z-10 flex items-center justify-between px-4 h-14 w-full text-gray-100 bg-neutral-900">
        <div className="flex items-center gap-2">
          {!isSidebarOpen && (
            <button 
              onClick={onToggleSidebar}
              className="p-2 hover:bg-neutral-800 rounded-lg transition-colors text-neutral-400 hover:text-neutral-200"
              title="Open sidebar (⌘+Shift+S)"
            >
              <LayoutPanelLeft size={20} />
            </button>
          )}

          <button className="flex items-center gap-1 hover:bg-neutral-800 rounded-lg px-2 py-1.5 transition-colors text-sm font-semibold text-neutral-200 group">
            RankRoute AI
            <ChevronDown size={16} className="text-neutral-400 group-hover:text-neutral-200" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setSimulatorOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/30 text-xs font-medium text-blue-400 hover:bg-blue-500/20 transition-colors"
            title="Rank Simulator"
          >
            <TrendingUp size={14} />
            Simulate
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto w-full custom-scrollbar">
        {isLoadingMessages ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="animate-spin text-neutral-500" size={32} />
          </div>
        ) : displayMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-full px-4 pt-10 sm:pt-20 pb-40">
            <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center mb-8 p-1 shadow-sm">
                <Image src="https://picsum.photos/seed/rankroute/64/64" alt="RankRoute AI Logo" width={56} height={56} className="rounded-full invert" referrerPolicy="no-referrer" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-semibold mb-12 text-center h-10">
              <TypewriterGreeting />
            </h1>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-3xl mt-auto mx-auto">
              {[
                { title: "Predict my college", desc: "Based on Assam CEE rank 1200" },
                { title: "Compare colleges", desc: "AEC vs JEC for Computer Science" },
                { title: "Check cutoffs", desc: "For OBC category in JEE Mains" }
              ].map((card, i) => (
                <button 
                  key={i} 
                  className="flex flex-col items-start p-4 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700/50 rounded-xl transition-colors text-left"
                  onClick={() => { setInputValue(card.title + " " + card.desc); if(textareaRef.current) textareaRef.current.focus(); }}
                >
                  <span className="font-medium text-sm text-neutral-200">{card.title}</span>
                  <span className="text-sm text-neutral-400 mt-1">{card.desc}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center w-full pb-40 pt-6">
            {displayMessages.map((msg, index) => (
              <div 
                key={msg.id || index} 
                className={cn(
                  "w-full px-4 py-6 flex justify-center group",
                  msg.role === 'assistant' && "animate-in fade-in slide-in-from-bottom-3 duration-500 ease-out"
                )}
              >
                <div className={cn(
                  "flex gap-4 w-full max-w-3xl",
                  msg.role === 'user' ? "justify-end" : ""
                )}>
                  {msg.role === 'assistant' && (
                    <div className="shrink-0 w-8 h-8 bg-white rounded-full flex items-center justify-center border border-neutral-200">
                      <Image src="https://picsum.photos/seed/rankroute/32/32" alt="RankRoute AI logo" width={24} height={24} className="rounded-full invert" referrerPolicy="no-referrer" />
                    </div>
                  )}

                  <div className={cn(
                    "flex flex-col gap-2 max-w-[80%]",
                    msg.role === 'user' ? "items-end" : "items-start min-w-[50%]"
                  )}>
                    <div className={cn(
                      "text-[15px] leading-relaxed whitespace-pre-wrap",
                      msg.role === 'user' 
                        ? "bg-neutral-800 px-5 py-2.5 rounded-3xl text-neutral-100" 
                        : "text-neutral-100 py-1 prose prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-neutral-900 prose-pre:border prose-pre:border-neutral-800 prose-a:no-underline"
                    )}>
                      {msg.role === 'user' ? (
                        msg.content
                      ) : (
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm]}
                          components={{ a: CustomCitationPill }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      )}
                    </div>

                    {msg.role === 'assistant' && (
                      <div className="flex items-center gap-1 text-neutral-400 mt-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity">
                        <button 
                          className="p-1.5 hover:bg-neutral-800 rounded text-neutral-400 hover:text-neutral-200 transition-colors" 
                          title="Copy"
                          aria-label="Copy"
                          onClick={() => {
                            navigator.clipboard.writeText(msg.content);
                            toast.success("Copied to clipboard");
                          }}
                        >
                          <Copy size={16} />
                        </button>
                        <button className="p-1.5 hover:bg-neutral-800 rounded text-neutral-400 hover:text-neutral-200 transition-colors" title="Regenerate" onClick={() => toast.info("Regenerate not implemented yet.")}>
                          <RefreshCw size={16} />
                        </button>
                        <button className="p-1.5 hover:bg-neutral-800 rounded text-neutral-400 hover:text-neutral-200 transition-colors" title="Good response" onClick={() => toast.success("Feedback logged. Thank you!")}>
                          <ThumbsUp size={16} />
                        </button>
                        <button className="p-1.5 hover:bg-neutral-800 rounded text-neutral-400 hover:text-neutral-200 transition-colors" title="Bad response" onClick={() => toast.success("Feedback logged. Thank you!")}>
                          <ThumbsDown size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="absolute w-full bottom-0 left-0 bg-gradient-to-t from-neutral-900 via-neutral-900 to-transparent pt-6 pb-2 sm:pb-6 px-4">
        
        {!isSidebarOpen && (
          <button 
            onClick={onOpenSettings}
            className="absolute bottom-4 left-4 p-2.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 rounded-full transition-colors text-neutral-400 hover:text-neutral-200 z-20 shadow-sm hidden sm:flex items-center justify-center"
            title="Settings"
          >
            <Settings size={20} />
          </button>
        )}

        <div className="w-full max-w-3xl mx-auto">
          <div className="relative flex items-end w-full p-2 bg-neutral-800 border border-neutral-700/50 rounded-[28px] shadow-sm focus-within:ring-1 focus-within:ring-neutral-500 transition-shadow">
            
            <button className="p-2.5 text-neutral-300 hover:text-white rounded-full transition-colors shrink-0 mb-0.5" onClick={() => toast.info("File uploads coming soon!")}>
              <Paperclip size={20} />
            </button>

            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              placeholder="Message RankRoute AI"
              aria-label="Message input"
              className="grow max-h-[200px] bg-transparent border-0 resize-none outline-none focus:ring-0 py-3.5 px-2 text-[15px] text-zinc-100 placeholder:text-zinc-400 custom-scrollbar wrap disabled:opacity-50"
              rows={1}
            />

            <div className="flex items-center gap-1 pr-1 pb-1 shrink-0">
              <button 
                onClick={handleSubmit}
                disabled={!inputValue.trim() || isStreaming}
                className={cn(
                  "p-1.5 rounded-full flex items-center justify-center transition-all mb-0.5 ml-1",
                  inputValue.trim() && !isStreaming
                    ? "bg-white text-black hover:bg-neutral-200" 
                    : "bg-[#424242] text-neutral-400"
                )}
              >
                {isStreaming ? <Loader2 size={20} className="animate-spin text-neutral-400" /> : <ArrowUp size={20} strokeWidth={2.5} />}
              </button>
            </div>
          </div>
          
          <div className="text-center mt-2 px-4">
            <span className="text-[11px] text-neutral-400">
              RankRoute AI can make mistakes. Always verify with official DTE Assam or JoSAA guidelines.
            </span>
          </div>
        </div>
      </div>

      <SimulatorModal
        isOpen={simulatorOpen}
        onClose={() => setSimulatorOpen(false)}
        onSendToChat={handleSimulatorSend}
      />
    </div>
  );
}
