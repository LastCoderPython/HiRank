import {
  AuthUser,
  BackupEntry,
  ChatListResponse,
  SingleChatResponse,
  TempChatResponse,
  ChatCreateResponse,
  MessageSaveResponse,
  UploadPreview,
  UploadResult,
  LogQueryResult,
  LogStats,
  SimulationResponse,
  ComparisonResponse,
  AnalyticsOverview,
  DailyAnalytics,
  PredictionAnalytics,
  CutoffStatusResponse,
} from './types';

const getApiUrl = () => process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${getApiUrl()}${endpoint}`;
  const headers: Record<string, string> = {};
  if (!(options?.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!res.ok) {
    let message = 'API Error';
    try {
      const data = await res.json();
      message = data.detail || data.error || message;
    } catch {}
    throw new Error(message);
  }
  
  return res.json() as Promise<T>;
}

export const api = {
  // Auth
  fetchSession: () => fetchApi<{ authenticated: boolean; user: AuthUser | null }>('/api/auth/session'),
  signOut: () => fetchApi<{ success: boolean }>('/api/auth/logout', { method: 'POST' }),


  // Profile
  getProfile: () => fetchApi<AuthUser>('/api/profile'),
  updateProfile: (data: Partial<AuthUser>) => fetchApi<AuthUser>('/api/profile', {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),

  // Chats (Authenticated)
  getChats: (limit = 50, offset = 0) => fetchApi<ChatListResponse>(`/api/chats?limit=${limit}&offset=${offset}`),
  createChat: (title: string, tempSessionId?: string) => 
    fetchApi<ChatCreateResponse>('/api/chats', {
      method: 'POST',
      body: JSON.stringify({ title, temp_session_id: tempSessionId }),
    }),
  getChat: (id: string) => fetchApi<SingleChatResponse>(`/api/chats/${id}`),
  renameChat: (id: string, title: string) => fetchApi<{ success: boolean; chat: any }>(`/api/chats/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  }),
  deleteChat: (id: string) => fetchApi<{ success: boolean }>(`/api/chats/${id}`, { method: 'DELETE' }),
  clearAllChats: () => fetchApi<{ success: boolean; deleted: number }>('/api/chats/clear', { method: 'POST' }),

  // Messages (Auth & Temp)
  saveMessage: (params: { chatId?: string; tempSessionId?: string; role: string; content: string; metadata?: any }) => 
    fetchApi<MessageSaveResponse>('/api/messages', {
      method: 'POST',
      body: JSON.stringify({
        chat_id: params.chatId,
        temp_session_id: params.tempSessionId,
        role: params.role,
        content: params.content,
        metadata: params.metadata,
      }),
    }),
  
  // Rank Simulator
  simulateRank: (params: { current_rank: number; target_rank: number; category?: string; exam?: string; branch?: string; limit?: number }) => {
    const q = new URLSearchParams();
    q.set('current_rank', String(params.current_rank));
    q.set('target_rank', String(params.target_rank));
    if (params.category) q.set('category', params.category);
    if (params.exam)     q.set('exam', params.exam);
    if (params.branch)   q.set('branch', params.branch);
    if (params.limit)    q.set('limit', String(params.limit));
    return fetchApi<SimulationResponse>(`/api/colleges/simulate?${q.toString()}`);
  },

  // Temp Chats
  getTempChat: (sessionId: string) => fetchApi<TempChatResponse>(`/api/temp-chats/${sessionId}`),

  // College Compare
  compareColleges: (colleges: string, branch?: string) => {
    const q = new URLSearchParams();
    q.set('colleges', colleges);
    if (branch) q.set('branch', branch);
    return fetchApi<ComparisonResponse>(`/api/colleges/compare?${q.toString()}`);
  },

  // Admin
  uploadCutoffs:     (formData: FormData) => fetchApi<UploadResult>('/api/admin/upload/cutoffs', { method: 'POST', body: formData }),
  uploadCollegeInfo: (formData: FormData) => fetchApi<UploadResult>('/api/admin/upload/college-info', { method: 'POST', body: formData }),
  validateCutoffs:   (formData: FormData) => fetchApi<UploadPreview>('/api/admin/validate/cutoffs', { method: 'POST', body: formData }),
  validateCollegeInfo: (formData: FormData) => fetchApi<UploadPreview>('/api/admin/validate/college-info', { method: 'POST', body: formData }),
  listBackups:       () => fetchApi<{ backups: BackupEntry[] }>('/api/admin/backups'),
  restoreBackup:     (id: string) => fetchApi<{ success: boolean; restored_file: string; rows: number }>(`/api/admin/restore/${id}`, { method: 'POST' }),
  // Admin Logs
  getLogs:           (params?: { event_type?: string; severity?: string; source?: string; date_from?: string; date_to?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.event_type) q.set('event_type', params.event_type);
    if (params?.severity)    q.set('severity', params.severity);
    if (params?.source)      q.set('source', params.source);
    if (params?.date_from)   q.set('date_from', params.date_from);
    if (params?.date_to)     q.set('date_to', params.date_to);
    if (params?.limit)       q.set('limit', String(params.limit));
    if (params?.offset)      q.set('offset', String(params.offset));
    const qs = q.toString();
    return fetchApi<LogQueryResult>(`/api/admin/logs${qs ? '?' + qs : ''}`);
  },
  getLogStats:       () => fetchApi<LogStats>('/api/admin/logs/stats'),

  // Cutoff Status
  getCutoffStatus:   () => fetchApi<CutoffStatusResponse>('/api/admin/cutoffs/status'),

  // Analytics
  getAnalyticsOverview:      () => fetchApi<AnalyticsOverview>('/api/admin/analytics/overview'),
  getDailyAnalytics:         (days = 30) => fetchApi<DailyAnalytics>(`/api/admin/analytics/daily?days=${days}`),
  getPredictionAnalytics:    () => fetchApi<PredictionAnalytics>('/api/admin/analytics/predictions'),
};
