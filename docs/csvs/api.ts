const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
}

export interface Chat {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  chat_id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export async function getSession(): Promise<{ authenticated: boolean; user: User | null }> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/auth/session`, {
      credentials: 'include',
    });
    
    if (!response.ok) {
      return { authenticated: false, user: null };
    }
    
    return response.json();
  } catch {
    return { authenticated: false, user: null };
  }
}

export function getGoogleLoginUrl(): string {
  return `${BACKEND_URL}/api/auth/google`;
}

export async function logout(): Promise<{ success: boolean }> {
  const response = await fetch(`${BACKEND_URL}/api/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });
  return response.json();
}

export async function refreshSession(): Promise<{ success: boolean }> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    return response.json();
  } catch {
    return { success: false };
  }
}

export async function createChat(title: string = 'New Chat', tempSessionId?: string): Promise<{ chat_id: string; transferred?: boolean } | { error: string; requires_auth: boolean }> {
  const response = await fetch(`${BACKEND_URL}/api/chats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ title, temp_session_id: tempSessionId }),
  });
  return response.json();
}

export async function getChats(limit: number = 50, offset: number = 0): Promise<{ chats: Chat[]; authenticated: boolean }> {
  const response = await fetch(`${BACKEND_URL}/api/chats?limit=${limit}&offset=${offset}`, {
    credentials: 'include',
  });
  return response.json();
}

export async function getChat(chatId: string): Promise<{ chat: Chat; messages: Message[] }> {
  const response = await fetch(`${BACKEND_URL}/api/chats/${chatId}`, {
    credentials: 'include',
  });
  
  if (!response.ok) {
    throw new Error('Chat not found');
  }
  
  return response.json();
}

export async function updateChatTitle(chatId: string, title: string): Promise<{ success: boolean }> {
  const response = await fetch(`${BACKEND_URL}/api/chats/${chatId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ title }),
  });
  return response.json();
}

export async function deleteChat(chatId: string): Promise<{ success: boolean }> {
  const response = await fetch(`${BACKEND_URL}/api/chats/${chatId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  return response.json();
}

export async function saveMessage(
  role: 'user' | 'assistant',
  content: string,
  options?: { chatId?: string; tempSessionId?: string; metadata?: Record<string, unknown> }
): Promise<{ success: boolean; message_id?: string; chat_id?: string; temp?: boolean }> {
  const response = await fetch(`${BACKEND_URL}/api/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      chat_id: options?.chatId,
      temp_session_id: options?.tempSessionId,
      role,
      content,
      metadata: options?.metadata,
    }),
  });
  return response.json();
}

export async function getTempChat(sessionId: string): Promise<{ exists: boolean; messages: Message[]; chat?: Chat }> {
  const response = await fetch(`${BACKEND_URL}/api/temp-chats/${sessionId}`);
  return response.json();
}

export async function transferTempChat(sessionId: string): Promise<{ success: boolean; chat_id?: string; message?: string }> {
  const response = await fetch(`${BACKEND_URL}/api/transfer-temp-chat?session_id=${sessionId}`, {
    method: 'POST',
    credentials: 'include',
  });
  return response.json();
}

export async function sendMessage(message: string, history: {role: string; content: string}[] = []) {
  const response = await fetch(`${BACKEND_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({
      message,
      history,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to send message');
  }

  return response;
}

export async function* streamResponse(response: Response) {
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error('No response body');
  }

  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        
        if (data === '[DONE]' || data === '') {
          continue;
        }

        try {
          const parsed = JSON.parse(data);
          yield parsed;
        } catch {
          // Skip invalid JSON
        }
      }
    }
  }
}

export async function getColleges(
  rank: number,
  category: string = 'General',
  branch?: string,
  exam: string = 'CEE'
) {
  const params = new URLSearchParams({
    rank: rank.toString(),
    category,
    exam,
  });

  if (branch) {
    params.append('branch', branch);
  }

  const response = await fetch(`${BACKEND_URL}/api/colleges?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch colleges');
  }

  return response.json();
}

export async function checkHealth() {
  const response = await fetch(`${BACKEND_URL}/api/health`);
  return response.json();
}
