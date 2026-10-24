import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  AlertCircle,
  Clock,
  ArrowRight,
  ShieldCheck,
  Check,
  FileCode,
  X,
  Layers,
} from 'lucide-react';
import { invoicesApi } from '../services/api';

const STAGES = [
  { id: 'uploading', label: 'Multipart Document Ingestion' },
  { id: 'ocr', label: 'Tesseract OCR Layout Parsing' },
  { id: 'extracting', label: 'Entity & Key-Value Extraction' },
  { id: 'validating', label: 'Mathematical Reconciliation' },
  { id: 'duplicates', label: 'RapidFuzz Duplicate Scan' },
  { id: 'risk', label: 'Deterministic Risk Evaluation' },
  { id: 'completed', label: 'Ledger Archival Ready' },
];

export const UploadInvoicePage: React.FC = () => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStageIndex, setCurrentStageIndex] = useState<number>(-1);
  const [error, setError] = useState<string | null>(null);
  const [processedInvoiceId, setProcessedInvoiceId] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = (file: File) => {
    const validTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg', 'text/plain'];
    if (!validTypes.includes(file.type) && !file.name.endsWith('.txt')) {
      setError('Please upload a PDF, PNG, JPG, or structured text invoice file.');
      return;
    }
    setError(null);
    setSelectedFile(file);
  };

  const loadSampleInvoice = () => {
    const sampleText = `INVOICE
Invoice Number: INV-2024-9988
Date: 2024-09-02
Due Date: 2024-10-02
Vendor: CloudShield Cyber Solutions Inc
Vendor Address: 100 Tech Enterprise Blvd, Suite 400
Customer: Apex FinTech Global
Customer Address: 742 Evergreen Terrace, Sector 7
GST Number: 29ABCDE1234F1Z5
PO Number: PO-2024-7712

Description                         Qty    Price      Total
Enterprise Security Sentinel Core    1     3000.00    3000.00
Threat Intelligence Feed (1 Year)   1     1500.00    1500.00
Cloud Backup Vault Storage          1      500.00     500.00

Subtotal: $5000.00
Tax Amount: $500.00
Discount: $100.00
Total Amount: $5400.00
`;
    const blob = new Blob([sampleText], { type: 'text/plain' });
    const file = new File([blob], 'Sample_Invoice_INV-9988.txt', { type: 'text/plain' });
    handleFileSelected(file);
  };

  const startUploadPipeline = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setError(null);
    setCurrentStageIndex(0);

    // Realistic stepped progress sequence
    const stageInterval = setInterval(() => {
      setCurrentStageIndex((prev) => {
        if (prev < 5) return prev + 1;
        return prev;
      });
    }, 450);

    try {
      const res = await invoicesApi.upload(selectedFile);
      clearInterval(stageInterval);
      setCurrentStageIndex(6); // Completed
      setProcessedInvoiceId(res.data.id);
    } catch (err: any) {
      clearInterval(stageInterval);
      setIsProcessing(false);
      setError(err.response?.data?.detail || 'Failed to process invoice.');
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Upload Invoice</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload PDF documents, scanned images, or text invoices for OCR extraction, math validation, and duplicate screening.
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Upload Dropzone */}
      {!isProcessing && currentStageIndex === -1 && (
        <div className="space-y-4">
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors bg-white ${
              dragActive
                ? 'border-blue-500 bg-blue-50/50'
                : 'border-gray-300 hover:border-blue-500 hover:bg-gray-50/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.txt"
              onChange={handleFileInput}
              className="hidden"
            />
            <div className="w-12 h-12 rounded bg-gray-100 border border-gray-200 flex items-center justify-center text-gray-600 mx-auto mb-3">
              <UploadCloud className="w-6 h-6 text-gray-500" />
            </div>

            <h3 className="text-sm font-semibold text-gray-800">
              {selectedFile ? selectedFile.name : 'Select or drag & drop an invoice file'}
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              Supports PDF, PNG, JPG, JPEG, or structured text (.txt) up to 25MB
            </p>

            {selectedFile ? (
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1 rounded bg-blue-50 border border-blue-200 text-xs font-medium text-blue-700">
                <FileText className="w-3.5 h-3.5" />
                <span>{(selectedFile.size / 1024).toFixed(1)} KB selected</span>
              </div>
            ) : (
              <div className="mt-4 flex items-center justify-center gap-2 text-[11px] text-gray-400">
                <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200">PDF</span>
                <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200">JPG</span>
                <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200">PNG</span>
                <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200">TXT</span>
              </div>
            )}
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-lg bg-white border border-gray-200">
            <button
              type="button"
              onClick={loadSampleInvoice}
              className="px-3 py-1.5 rounded-md bg-gray-50 hover:bg-gray-100 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors border border-gray-200"
            >
              <FileCode className="w-3.5 h-3.5 text-blue-600" />
              <span>Load Sample Invoice</span>
            </button>

            {selectedFile && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 text-gray-600 text-xs border border-gray-200 transition-colors"
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={startUploadPipeline}
                  className="px-4 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs flex items-center gap-1.5 transition-colors shadow-xs"
                >
                  <span>Process Invoice</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Processing Pipeline Timeline */}
      {(isProcessing || currentStageIndex >= 0) && (
        <div className="p-6 rounded-lg bg-white border border-gray-200 space-y-5">
          <div className="flex items-center justify-between border-b border-gray-200 pb-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-600" />
                Invoice Processing Pipeline
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">Target: {selectedFile?.name}</p>
            </div>
            {currentStageIndex === 6 ? (
              <span className="px-2.5 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                Processing Complete
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
                Step {currentStageIndex + 1} of 7...
              </span>
            )}
          </div>

          <div className="space-y-2">
            {STAGES.map((stage, idx) => {
              const isPast = idx < currentStageIndex;
              const isCurrent = idx === currentStageIndex;
              const isPending = idx > currentStageIndex;

              return (
                <div
                  key={stage.id}
                  className={`flex items-center justify-between p-3 rounded-md border text-xs transition-colors ${
                    isPast
                      ? 'bg-gray-50 border-gray-200 text-gray-700'
                      : isCurrent
                      ? 'bg-blue-50 border-blue-200 text-blue-900 font-medium'
                      : 'bg-white border-gray-100 text-gray-400'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <div
                      className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold ${
                        isPast
                          ? 'bg-green-600 text-white'
                          : isCurrent
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-400'
                      }`}
                    >
                      {isPast ? <Check className="w-3 h-3" /> : idx + 1}
                    </div>
                    <span>{stage.label}</span>
                  </div>

                  <span className="text-[11px]">
                    {isPast && <span className="text-green-600 font-medium">Done</span>}
                    {isCurrent && <span className="text-blue-600 font-medium">Processing...</span>}
                    {isPending && <span className="text-gray-400">Waiting</span>}
                  </span>
                </div>
              );
            })}
          </div>

          {currentStageIndex === 6 && processedInvoiceId && (
            <div className="pt-3 border-t border-gray-200 flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => {
                  setSelectedFile(null);
                  setCurrentStageIndex(-1);
                  setIsProcessing(false);
                }}
                className="px-3.5 py-2 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium transition-colors"
              >
                Upload Another
              </button>
              <button
                type="button"
                onClick={() => navigate(`/invoices/${processedInvoiceId}/result`)}
                className="px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <span>View Extracted Results</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
