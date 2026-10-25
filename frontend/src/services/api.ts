import axios from 'axios';
import {
  User, Invoice, DashboardStats, DashboardAnalytics, AuditLog,
  AgentContact, AgentConversation, AgentMessage, AgentApproval, AgentSettings, SimulateResult,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor to inject JWT Bearer Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('invoshield_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response Interceptor for Session Expiry
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.includes('/login')) {
      localStorage.removeItem('invoshield_token');
      localStorage.removeItem('invoshield_user');
      window.location.href = '/login?expired=1';
    }
    return Promise.reject(error);
  }
);

// Auth Endpoints
export const authApi = {
  register: (data: any) => apiClient.post('/api/auth/register', data),
  login: (data: any) => apiClient.post('/api/auth/login', data),
  getMe: () => apiClient.get<User>('/api/auth/me'),
  changePassword: (current_password: string, new_password: string) =>
    apiClient.post<User>('/api/auth/change-password', { current_password, new_password }),
};

// Invoices Endpoints
export const invoicesApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<Invoice>('/api/invoices/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getAll: (params?: {
    search?: string;
    status?: string;
    risk_level?: string;
    validation_status?: string;
    page?: number;
    limit?: number;
  }) => apiClient.get<{ items: Invoice[]; total: number; page: number; limit: number; total_pages: number }>('/api/invoices', { params }),
  getById: (id: string | number) => apiClient.get<Invoice>(`/api/invoices/${id}`),
  update: (id: string | number, data: Partial<Invoice>) => apiClient.put<Invoice>(`/api/invoices/${id}`, data),
  revalidate: (id: string | number) => apiClient.post<Invoice>(`/api/invoices/${id}/validate`),
  approve: (id: string | number) => apiClient.post<Invoice>(`/api/invoices/${id}/approve`),
  reject: (id: string | number) => apiClient.post<Invoice>(`/api/invoices/${id}/reject`),
  markPaid: (id: string | number) => apiClient.post<Invoice>(`/api/invoices/${id}/mark-paid`),
  getDuplicates: (id: string | number) => apiClient.get<any>(`/api/invoices/${id}/duplicates`),
  getRiskAnalysis: (id: string | number) => apiClient.get<any>(`/api/invoices/${id}/risk-analysis`),
  getFileUrl: (id: string | number) => `${API_BASE_URL}/api/invoices/${id}/file`,
};

// Dashboard Endpoints
export const dashboardApi = {
  getStatistics: () => apiClient.get<DashboardStats>('/api/dashboard/statistics'),
  getAnalytics: () => apiClient.get<DashboardAnalytics>('/api/dashboard/analytics'),
};

// Admin Endpoints
export const adminApi = {
  getUsers: () => apiClient.get<User[]>('/api/admin/users'),
  updateUserRole: (id: number, role: string) => apiClient.put<User>(`/api/admin/users/${id}/role`, { role }),
  getAuditLogs: () => apiClient.get<AuditLog[]>('/api/admin/audit-logs'),
  getFlagged: () => apiClient.get<Invoice[]>('/api/admin/flagged'),
};

// InvoShield Assistant Endpoints
export type ContactInput = {
  display_name: string;
  kind: 'vendor' | 'staff';
  vendor_name?: string;
  user_email?: string;
  phone?: string;
  email?: string;
  verified: boolean;
  preferred_language: string;
  notes?: string;
};

export const agentApi = {
  getConversations: () => apiClient.get<AgentConversation[]>('/api/agent/conversations'),
  getMessages: (id: number) =>
    apiClient.get<{ conversation: AgentConversation; messages: AgentMessage[] }>(`/api/agent/conversations/${id}/messages`),
  getApprovals: (status = 'pending') => apiClient.get<AgentApproval[]>('/api/agent/approvals', { params: { status } }),
  approve: (id: number, text?: string) => apiClient.post<AgentApproval>(`/api/agent/approvals/${id}/approve`, { text }),
  reject: (id: number) => apiClient.post<AgentApproval>(`/api/agent/approvals/${id}/reject`),
  getContacts: () => apiClient.get<AgentContact[]>('/api/agent/contacts'),
  createContact: (data: ContactInput) => apiClient.post<AgentContact>('/api/agent/contacts', data),
  updateContact: (id: number, data: ContactInput) => apiClient.put<AgentContact>(`/api/agent/contacts/${id}`, data),
  deleteContact: (id: number) => apiClient.delete(`/api/agent/contacts/${id}`),
  getSettings: () => apiClient.get<AgentSettings>('/api/agent/settings'),
  updateSettings: (data: Pick<AgentSettings, 'business_name' | 'default_language' | 'auto_reply' | 'notify_vendors'>) =>
    apiClient.put<AgentSettings>('/api/agent/settings', data),
  simulate: (sender: string, text: string, channel: string, file?: File | null) => {
    const form = new FormData();
    form.append('sender', sender);
    form.append('text', text);
    form.append('channel', channel);
    if (file) form.append('file', file);
    return apiClient.post<SimulateResult>('/api/agent/simulate', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};
