export type UserRole = 'admin' | 'reviewer' | 'user';

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  organization: string;
  must_change_password?: boolean;
  created_at?: string;
}

export interface InvoiceItem {
  id?: number;
  invoice_id?: number;
  description: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface ValidationResult {
  id?: number;
  invoice_id?: number;
  field_name: string;
  extracted_value?: string;
  validation_status: 'Valid' | 'Warning' | 'Invalid' | 'Missing';
  confidence_score: number;
  validation_message?: string;
}

export interface DuplicateCheck {
  id?: number;
  invoice_id: number;
  compared_invoice_id?: number;
  similarity_score: number;
  duplicate_status: 'Highly Likely Duplicate' | 'Possible Duplicate' | 'No Significant Duplicate';
  matching_fields?: any;
}

export interface FraudAlert {
  id?: number;
  invoice_id: number;
  risk_score: number;
  risk_level: 'Low' | 'Medium' | 'High';
  alert_reason: string;
  created_at?: string;
}

export interface AuditLog {
  id: number;
  user_id?: number;
  invoice_id?: number;
  action: string;
  timestamp: string;
  details?: string;
  user_name?: string;
  user_role?: string;
}

export interface Invoice {
  id: number;
  invoice_number?: string;
  vendor_name?: string;
  vendor_address?: string;
  customer_name?: string;
  customer_address?: string;
  gst_number?: string;
  tax_id?: string;
  bank_details?: string;
  po_number?: string;
  invoice_date?: string;
  due_date?: string;
  subtotal: number;
  tax_amount: number;
  discount: number;
  total_amount: number;
  currency: string;
  cloud_file_path: string;
  original_filename?: string;
  status: 'uploaded' | 'processing' | 'pending_review' | 'approved' | 'rejected' | 'flagged';
  validation_status: 'valid' | 'warning' | 'invalid';
  risk_score: number;
  risk_level: 'Low' | 'Medium' | 'High';
  duplicate_status: string;
  sha256_checksum?: string;
  organization?: string;
  user_id?: number;
  created_at?: string;
  updated_at?: string;
  items?: InvoiceItem[];
  validation_results?: ValidationResult[];
  duplicate_checks?: DuplicateCheck[];
  fraud_alerts?: FraudAlert[];
  audit_logs?: AuditLog[];
}

export interface DashboardStats {
  total_invoices: number;
  pending_invoices: number;
  approved_invoices: number;
  rejected_invoices: number;
  flagged_invoices: number;
  duplicate_alerts: number;
  high_risk_count: number;
  total_amount_processed: number;
}

export interface DashboardAnalytics {
  processing_over_time: { date: string; count: number; amount: number }[];
  status_distribution: { name: string; count: number; color: string }[];
  risk_distribution: { level: string; count: number; color: string }[];
  vendor_distribution: { vendor: string; count: number; total_amount: number }[];
  monthly_totals: { month: string; count: number; amount: number }[];
  recent_activities: AuditLog[];
}

// ---------------- InvoShield Assistant ----------------
export interface AgentContact {
  id: number;
  display_name: string;
  kind: 'vendor' | 'staff';
  vendor_name?: string | null;
  user_id?: number | null;
  user_email?: string | null;
  user_role?: string | null;
  phone_e164?: string | null;
  email?: string | null;
  verified: boolean;
  preferred_language: string;
  notes?: string | null;
  created_at?: string;
}

export interface AgentConversation {
  id: number;
  channel: string;
  sender_address: string;
  contact: AgentContact | null;
  last_message_at?: string;
  last_inbound_at?: string;
  last_message: string;
  last_direction: 'inbound' | 'outbound' | null;
}

export interface AgentToolCall {
  name: string;
  input: Record<string, unknown>;
  outcome: string;
}

export interface AgentMessage {
  id: number;
  direction: 'inbound' | 'outbound';
  content: string;
  status: string;
  media: { filename: string; mime_type: string }[];
  tool_calls: AgentToolCall[];
  created_at: string;
}

export interface AgentApproval {
  id: number;
  type: 'invoice_action' | 'outbound_message' | 'document_copy' | 'held_reply' | 'handoff';
  status: string;
  summary: string;
  payload: Record<string, any>;
  conversation_id?: number | null;
  requested_by: AgentContact | null;
  decided_at?: string | null;
  created_at: string;
}

export interface AgentSettings {
  organization: string;
  business_name: string;
  default_language: string;
  auto_reply: boolean;
  notify_vendors: boolean;
  channel_mode: 'mock' | 'live';
  llm: { provider: string; model?: string | null };
  whatsapp: { configured: boolean; webhook_secret_set: boolean; verify_token_set: boolean; webhook_path: string };
  email: { configured: boolean; webhook_secret_set: boolean; imap_configured: boolean; webhook_path: string };
  templates: Record<string, string>;
}

export interface SimulateResult {
  conversation_id: number | null;
  status: string;
  replies: string[];
  tool_calls: AgentToolCall[];
  outbox: { to: string; text: string; template?: string | null; buttons: [string, string][] }[];
}
