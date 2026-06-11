export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  phone?: string;
  role?: 'user' | 'admin' | 'moderator';
  // Onboarding fields
  onboarding_complete: boolean;
  exam?: 'JEE_MAIN' | 'JEE_ADV' | 'NEET' | 'CEE' | 'OTHER';
  rank?: number;
  percentile?: number;
  category?: 'General' | 'OBC' | 'SC' | 'ST' | 'EWS';
  home_state?: string;
  branch_preferences?: string[];
  whatsapp_number?: string;
  budget_range?: string;
  hostel_required?: boolean;
  location_preference?: string;
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
  session_id?: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface ChatListResponse {
  chats: Chat[];
  authenticated: boolean;
}

export interface SingleChatResponse {
  chat: Chat;
  messages: Message[];
}

export interface TempChatResponse {
  exists: boolean;
  messages: Message[];
  chat?: Record<string, any>;
}

export interface ChatCreateResponse {
  chat_id: string;
  transferred?: boolean;
  error?: string;
  requires_auth?: boolean;
}

export interface MessageSaveResponse {
  success: boolean;
  message_id: string;
  temp?: boolean;
  chat_id?: string;
}

export interface StreamEvent {
  type: 'token' | 'colleges' | 'session' | 'auth_required' | 'done' | 'error';
  data?: any;
  session_id?: string;
  reason?: string;
  used?: number;
  limit?: number;
  tavily_skipped?: boolean;
  resets_on?: string;
}

export interface UploadPreview {
  valid: boolean;
  rows: number;
  columns: string[];
  errors: { row?: number; column?: string; message: string }[];
  preview: Record<string, any>[];
}

export interface UploadResult {
  success: boolean;
  rows_loaded: number;
  columns: string[];
  chroma_job_id?: string;
  backup_id: string;
}

export interface BackupEntry {
  id: string;
  filename: string;
  size_bytes: number;
  created_at: string;
}

export interface AdminStats {
  collections: Record<string, number>;
}

export interface LogEntry {
  id: string;
  event_type: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  actor_id?: string;
  actor_role: string;
  summary: string;
  details?: Record<string, any>;
  source: string;
  created_at: string;
}

export interface LogQueryResult {
  entries: LogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface SimulatedOption {
  college_name: string;
  college_code: string;
  branch: string;
  closing_rank: number;
  match_percentage: number;
  band: string;
  is_unlocked: boolean;
}

export interface SimulationResponse {
  current_rank: number;
  target_rank: number;
  category: string;
  exam: string;
  current_options: SimulatedOption[];
  target_options: SimulatedOption[];
  newly_unlocked: SimulatedOption[];
  summary: string;
}

export interface ComparisonMetric {
  label: string;
  values: Record<string, string>;
  source?: string;
}

export interface ComparisonResponse {
  colleges: string[];
  branch?: string;
  metrics: ComparisonMetric[];
  has_data: boolean;
}

export interface CutoffStatusEntry {
  years: number[];
  records: number;
  colleges: number;
}

export interface CutoffStatusResponse {
  cee: CutoffStatusEntry;
  jee: CutoffStatusEntry;
  data_loaded: boolean;
}

export interface AnalyticsOverview {
  total_chats: number;
  chats_today: number;
  total_messages: number;
  total_users: number;
  total_predictions: number;
}

export interface DailyAnalytics {
  daily: { date: string; chats: number }[];
  total_days: number;
}

export interface PredictionAnalytics {
  band_distribution: Record<string, number>;
  total_prediction_events: number;
}

export interface LogStats {
  total: number;
  by_severity: Record<string, number>;
  last_24h: number;
}
