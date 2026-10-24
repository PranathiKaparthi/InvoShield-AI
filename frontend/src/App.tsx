import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { CurrencyProvider } from './context/CurrencyContext';
import { DashboardLayout } from './layouts/DashboardLayout';

// Pages
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { UploadInvoicePage } from './pages/UploadInvoicePage';
import { InvoiceResultPage } from './pages/InvoiceResultPage';
import { DuplicateDetectionPage } from './pages/DuplicateDetectionPage';
import { RiskAnalysisPage } from './pages/RiskAnalysisPage';
import { InvoiceManagementPage } from './pages/InvoiceManagementPage';
import { InvoiceDetailsPage } from './pages/InvoiceDetailsPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';

// Protected Route Guard
const ProtectedRoute: React.FC<{ children: React.ReactNode; allowedRoles?: string[] }> = ({
  children,
  allowedRoles,
}) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <CurrencyProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Landing & Auth Routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected Dashboard Routes */}
            <Route
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/upload" element={<UploadInvoicePage />} />
              <Route path="/invoices" element={<InvoiceManagementPage />} />
              <Route path="/invoices/:id/result" element={<InvoiceResultPage />} />
              <Route path="/invoices/:id/details" element={<InvoiceDetailsPage />} />
              <Route path="/duplicates" element={<DuplicateDetectionPage />} />
              <Route path="/invoices/:id/duplicates" element={<DuplicateDetectionPage />} />
              <Route path="/risk-analysis" element={<RiskAnalysisPage />} />
              <Route path="/invoices/:id/risk-analysis" element={<RiskAnalysisPage />} />

              {/* Admin Only Route */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminDashboardPage />
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* Fallback Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </CurrencyProvider>
    </AuthProvider>
  );
};

export default App;
