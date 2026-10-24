import axios from 'axios';
import { User, Invoice, DashboardStats, DashboardAnalytics, AuditLog } from '../types';

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
