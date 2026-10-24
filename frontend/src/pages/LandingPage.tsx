import React from 'react';
import { Link } from 'react-router-dom';
import {
  Shield,
  FileSearch,
  CheckCircle2,
  CopyCheck,
  AlertTriangle,
  Lock,
  ArrowRight,
  Database,
  Cpu,
  Layers,
  FileText,
} from 'lucide-react';
import { Navbar } from '../components/Navbar';

export const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 text-gray-900 flex flex-col font-sans">
      <Navbar />

      {/* Hero Section */}
      <section className="py-14 md:py-20 border-b border-gray-200 bg-white">
        <div className="max-w-4xl mx-auto px-4 text-center space-y-5">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-blue-50 border border-blue-200 text-blue-800 text-xs font-mono">
            <span>BCSE497J — Project I</span>
            <span className="text-gray-300">•</span>
            <span>B.Tech CSE Capstone Project</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-gray-900 leading-tight">
            Automated Invoice Processing & <br className="hidden sm:inline" />
            Fraud Detection System
          </h1>

          <p className="max-w-2xl mx-auto text-sm sm:text-base text-gray-600 leading-relaxed">
            An accounts payable security platform that automates invoice data extraction,
            mathematical verification, RapidFuzz duplicate detection, and risk anomaly scoring,
            enforcing four-eyes Segregation of Duties (SoD).
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <Link
              to="/dashboard"
              className="px-4 py-2 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 transition-colors shadow-xs"
            >
              <span>Launch Application</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <Link
              to="/login"
              className="px-4 py-2 rounded text-xs font-medium bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 transition-colors"
            >
              Sign In to Account
            </Link>
          </div>

          {/* Technical Pillar Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-3xl mx-auto pt-6 text-left">
            <div className="p-3 rounded border border-gray-200 bg-slate-50 space-y-1">
              <span className="text-[10px] font-mono uppercase text-gray-500 font-medium">DOCUMENT PARSER</span>
              <p className="text-sm font-bold text-gray-900 font-mono">Tesseract + PyPDF</p>
              <p className="text-xs text-gray-500">OCR & table extraction</p>
            </div>
            <div className="p-3 rounded border border-gray-200 bg-slate-50 space-y-1">
              <span className="text-[10px] font-mono uppercase text-gray-500 font-medium">DUPLICATE ENGINE</span>
              <p className="text-sm font-bold text-gray-900 font-mono">RapidFuzz</p>
              <p className="text-xs text-gray-500">Token-sort ratio matching</p>
            </div>
            <div className="p-3 rounded border border-gray-200 bg-slate-50 space-y-1">
              <span className="text-[10px] font-mono uppercase text-gray-500 font-medium">RISK HEURISTICS</span>
              <p className="text-sm font-bold text-gray-900 font-mono">0–100 Engine</p>
              <p className="text-xs text-gray-500">Deterministic scoring</p>
            </div>
            <div className="p-3 rounded border border-gray-200 bg-slate-50 space-y-1">
              <span className="text-[10px] font-mono uppercase text-gray-500 font-medium">DATA PROTECTION</span>
              <p className="text-sm font-bold text-gray-900 font-mono">AES-256-GCM</p>
              <p className="text-xs text-gray-500">Zero-Trust PII encryption</p>
            </div>
          </div>
        </div>
      </section>

      {/* Processing Pipeline Section */}
      <section className="py-12 max-w-4xl mx-auto px-4 w-full">
        <div className="text-center space-y-1.5 mb-8">
          <span className="text-xs font-mono text-blue-600 uppercase tracking-wide font-medium">System Architecture</span>
          <h2 className="text-xl font-bold text-gray-900">End-to-End Processing Pipeline</h2>
          <p className="text-xs text-gray-500 max-w-lg mx-auto">
            Invoices progress through a multi-stage validation workflow before reaching accounts payable authorization.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {[
            { step: '01', title: 'File Ingestion', desc: 'PDF / Image multipart upload', icon: FileText },
            { step: '02', title: 'OCR Extraction', desc: 'Vendor, totals & line items', icon: FileSearch },
            { step: '03', title: 'Math Audit', desc: 'Subtotal & tax reconciliation', icon: CheckCircle2 },
            { step: '04', title: 'Duplicate Check', desc: 'RapidFuzz historical search', icon: CopyCheck },
            { step: '05', title: 'Risk Scoring', desc: '0–100 anomaly rule engine', icon: AlertTriangle },
            { step: '06', title: 'Reviewer Action', desc: 'Four-Eyes SoD approval', icon: Shield },
          ].map((item, idx) => {
            const Icon = item.icon;
            return (
              <div key={idx} className="p-3 rounded bg-white border border-gray-200 space-y-1.5">
                <span className="text-[11px] font-mono text-blue-600 font-semibold">{item.step}</span>
                <div className="w-6 h-6 rounded bg-gray-100 flex items-center justify-center text-gray-600">
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <h3 className="font-semibold text-gray-900 text-xs">{item.title}</h3>
                <p className="text-[11px] text-gray-500 leading-snug">{item.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Key Core Modules */}
      <section className="py-12 bg-white border-y border-gray-200">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center space-y-1.5 mb-8">
            <span className="text-xs font-mono text-blue-600 uppercase tracking-wide font-medium">Core Capabilities</span>
            <h2 className="text-xl font-bold text-gray-900">Fraud Prevention & Control Mechanisms</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded border border-gray-200 bg-slate-50 space-y-2">
              <div className="w-7 h-7 rounded bg-blue-100 text-blue-700 flex items-center justify-center">
                <CopyCheck className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-semibold text-gray-900">RapidFuzz Duplicate Detection</h3>
              <p className="text-xs text-gray-600 leading-relaxed">
                Calculates weighted similarity across invoice numbers, vendor names, dates, and amounts. Flags partial or near-duplicate submissions to prevent duplicate payouts.
              </p>
            </div>

            <div className="p-4 rounded border border-gray-200 bg-slate-50 space-y-2">
              <div className="w-7 h-7 rounded bg-emerald-100 text-emerald-700 flex items-center justify-center">
                <Shield className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-semibold text-gray-900">Segregation of Duties (SoD)</h3>
              <p className="text-xs text-gray-600 leading-relaxed">
                Implements the Four-Eyes Principle. A submitter cannot approve their own invoice. Enforces separation between uploaders and finance reviewers.
              </p>
            </div>

            <div className="p-4 rounded border border-gray-200 bg-slate-50 space-y-2">
              <div className="w-7 h-7 rounded bg-purple-100 text-purple-700 flex items-center justify-center">
                <Lock className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-semibold text-gray-900">Zero-Trust AES-256-GCM</h3>
              <p className="text-xs text-gray-600 leading-relaxed">
                Vendor Tax IDs, GSTINs, and remittance data are encrypted with authenticated ciphers before persistence. Plaintext PII is masked by default in the UI.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="py-8 max-w-4xl mx-auto px-4 text-center space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-gray-500">Technology Stack</h3>
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-gray-600 font-mono">
          <span className="px-2.5 py-1 rounded bg-white border border-gray-200">FastAPI & Pydantic v2</span>
          <span className="px-2.5 py-1 rounded bg-white border border-gray-200">PostgreSQL / SQLite & SQLAlchemy</span>
          <span className="px-2.5 py-1 rounded bg-white border border-gray-200">RapidFuzz & Tesseract OCR</span>
          <span className="px-2.5 py-1 rounded bg-white border border-gray-200">React 19 & TypeScript</span>
          <span className="px-2.5 py-1 rounded bg-white border border-gray-200">Tailwind CSS & Recharts</span>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto py-5 border-t border-gray-200 bg-white text-center text-xs text-gray-500 font-mono space-y-1">
        <div>InvoShield — Automated Invoice Processing & Fraud Detection System</div>
        <div className="text-[11px] text-gray-400">
          BCSE497J Project I • K Pranathi (23BCT0260) • Tejasree Lehya (23BCI0075) • Sai Thanmaye (23BCI0102) • Guide: Prof. Rakhi Mol V
        </div>
      </footer>
    </div>
  );
};
