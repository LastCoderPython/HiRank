'use client';

import React, { useRef, useEffect } from 'react';
import { LayoutPanelLeft, ChevronDown, Check, User, Paperclip, Mic, ArrowUp, Copy, RefreshCw, ThumbsUp, ThumbsDown, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import Image from 'next/image';
import { toast } from 'sonner';

import { TypewriterGreeting } from '@/components/typewriter-greeting';

interface ChatAreaProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  isMobile: boolean;
  onOpenSettings: () => void;
}

export function ChatArea({ isSidebarOpen, onToggleSidebar, isMobile, onOpenSettings }: ChatAreaProps) {
  const [messages, setMessages] = React.useState<any[]>([]);
  const [inputValue, setInputValue] = React.useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      // Max height around 200px (approx 8-10 lines) then scroll
      const scrollHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${scrollHeight}px`;
      
      // Auto toggle scrollbar if exceeding max height
      textareaRef.current.style.overflowY = textareaRef.current.scrollHeight > 200 ? 'auto' : 'hidden';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    if (!inputValue.trim()) return;

    const query = inputValue.trim();
    // Add user message immediately
    const userMessage = { role: 'user', content: query };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'; // Reset height
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    
    if (!apiUrl) {
      // Fallback: Simulate assistant reply
      setTimeout(() => {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: `(Simulation) I am RankRoute AI. I received your query: "${query}". Set NEXT_PUBLIC_API_URL to connect to the backend.` 
        }]);
      }, 1000);
      return;
    }

    // Add empty assistant message that will be streamed into
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      const { fetchEventSource } = await import('@microsoft/fetch-event-source');
      let streamContent = '';
      
      await fetchEventSource(`${apiUrl}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({ message: query }),
        onmessage(msg) {
          if (msg.event === 'error') {
            throw new Error(msg.data);
          }
          if (msg.data) {
            try {
              // Parse data if it is JSON, otherwise append raw text.
              // Assuming API returns chunks in { "text": "..." } or plain text
              const parsed = JSON.parse(msg.data);
              const textChunk = parsed.text || parsed.content || parsed.chunk || msg.data;
              streamContent += textChunk;
            } catch (e) {
              streamContent += msg.data;
            }
            setMessages(prev => {
              const clone = [...prev];
              clone[clone.length - 1].content = streamContent;
              return clone;
            });
          }
        },
        onerror(err) {
          console.error("SSE Error:", err);
          toast.error("Failed to connect to AI backend.");
          throw err; // Stop retrying
        }
      });
    } catch (error) {
      console.error('Chat error:', error);
      toast.error('An error occurred while fetching the response.');
    }
  };

  return (
    <div className="flex flex-col h-full w-full relative">
      {/* Header */}
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

        <div className="flex items-center">
          {/* Header empty on right side, settings moved to bottom left */}
        </div>
      </header>

      {/* Main Scrollable Content */}
      <div className="flex-1 overflow-y-auto w-full custom-scrollbar">
        {messages.length === 0 ? (
          // Empty State
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
          // Chat History
          <div className="flex flex-col items-center w-full pb-40 pt-6">
            {messages.map((msg, index) => (
              <div 
                key={index} 
                className={cn(
                  "w-full px-4 py-6 flex justify-center group",
                  msg.role === 'assistant' && "animate-in fade-in slide-in-from-bottom-3 duration-500 ease-out"
                )}
              >
                <div className={cn(
                  "flex gap-4 w-full max-w-3xl",
                  msg.role === 'user' ? "justify-end" : ""
                )}>
                  {/* Assistant Avatar */}
                  {msg.role === 'assistant' && (
                    <div className="shrink-0 w-8 h-8 bg-white rounded-full flex items-center justify-center border border-neutral-200">
                      <Image src="https://picsum.photos/seed/rankroute/32/32" alt="RankRoute AI logo" width={24} height={24} className="rounded-full invert" referrerPolicy="no-referrer" />
                    </div>
                  )}

                  {/* Message Bubble */}
                  <div className={cn(
                    "flex flex-col gap-2 max-w-[80%]",
                    msg.role === 'user' ? "items-end" : "items-start min-w-[50%]"
                  )}>
                    <div className={cn(
                      "text-[15px] leading-relaxed",
                      msg.role === 'user' 
                        ? "bg-neutral-800 px-5 py-2.5 rounded-3xl text-neutral-100" 
                        : "text-neutral-100 py-1"
                    )}>
                      {msg.content}
                    </div>

                    {/* Assistant Action Buttons */}
                    {msg.role === 'assistant' && (
                      <div className="flex items-center gap-1 text-neutral-400 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button 
                          className="p-1.5 hover:bg-neutral-800 rounded text-neutral-400 hover:text-neutral-200 transition-colors" 
                          title="Copy"
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

      {/* Input Area */}
      <div className="absolute w-full bottom-0 left-0 bg-gradient-to-t from-neutral-900 via-neutral-900 to-transparent pt-6 pb-2 sm:pb-6 px-4">
        
        {/* Floating Settings Button for collapsed sidebar */}
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
              placeholder="Message RankRoute AI"
              className="grow max-h-[200px] bg-transparent border-0 resize-none outline-none focus:ring-0 py-3.5 px-2 text-[15px] text-zinc-100 placeholder:text-zinc-400 custom-scrollbar wrap"
              rows={1}
            />

            <div className="flex items-center gap-1 pr-1 pb-1 shrink-0">
              {/*!inputValue.trim() && (
                <button className="p-2 text-neutral-300 hover:text-white rounded-full transition-colors">
                  <Mic size={20} />
                </button>
              )*/}
              
              <button 
                onClick={handleSubmit}
                disabled={!inputValue.trim()}
                className={cn(
                  "p-1.5 rounded-full flex items-center justify-center transition-all mb-0.5 ml-1",
                  inputValue.trim() 
                    ? "bg-white text-black hover:bg-neutral-200" 
                    : "bg-[#424242] text-neutral-400"
                )}
              >
                <ArrowUp size={20} strokeWidth={2.5} />
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
    </div>
  );
}
