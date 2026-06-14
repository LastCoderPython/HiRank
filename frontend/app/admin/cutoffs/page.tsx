'use client';

import { useState, useRef } from 'react';
import { api } from '@/lib/api';
import { UploadPreview, UploadResult } from '@/lib/types';
import { Upload, FileText, ArrowLeft, CheckCircle2, AlertCircle, Loader2, Eye } from 'lucide-react';
import { cn } from '@/lib/utils';

type Step = 'select' | 'preview' | 'result';

export default function CutoffsUploadPage() {
  const [step, setStep] = useState<Step>('select');
  const [file, setFile] = useState<File | null>(null);
  const [exam, setExam] = useState<'CEE' | 'JEE'>('CEE');
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<UploadPreview | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    setFile(f);
    setError(null);
  };

  const handleValidate = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('exam', exam);
      const res = await api.validateCutoffs(fd);
      setPreview(res);
      setStep('preview');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('exam', exam);
      const res = await api.uploadCutoffs(fd);
      setResult(res);
      setStep('result');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStep('select');
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
  };

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg bg-neutral-700 flex items-center justify-center">
            <FileText className="w-4 h-4 text-emerald-400" />
          </div>
          <h1 className="text-xl font-bold text-white">Upload Cutoffs</h1>
        </div>

        {step === 'select' && (
          <div className="space-y-6">
            <div>
              <label className="text-sm font-medium text-neutral-300 mb-2 block">Exam Type</label>
              <div className="flex gap-4">
                {(['CEE', 'JEE'] as const).map((e) => (
                  <label key={e} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="exam" value={e} checked={exam === e} onChange={() => setExam(e)} className="accent-emerald-500" />
                    <span className="text-sm text-neutral-200">{e}</span>
                  </label>
                ))}
              </div>
            </div>

            <div
              className={cn(
                'border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors',
                dragging ? 'border-emerald-500 bg-emerald-500/10' : 'border-neutral-600 hover:border-neutral-500'
              )}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
              onClick={() => inputRef.current?.click()}
            >
              <Upload className="w-8 h-8 mx-auto mb-3 text-neutral-400" />
              <p className="text-sm text-neutral-300 mb-1">{file ? file.name : 'Drop CSV file or click to browse'}</p>
              <p className="text-xs text-neutral-500">CSV format recommended</p>
              <input ref={inputRef} type="file" accept=".csv,.tsv,.xlsx" className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 rounded-lg px-4 py-3">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <button
              disabled={!file || loading}
              onClick={handleValidate}
              className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-neutral-700 disabled:text-neutral-500 text-white rounded-lg transition-colors text-sm font-medium"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
              Validate
            </button>
          </div>
        )}

        {step === 'preview' && preview && (
          <div className="space-y-6">
            {preview.errors.length > 0 && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                <h3 className="text-sm font-semibold text-red-400 mb-2 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" /> {preview.errors.length} Error{preview.errors.length > 1 ? 's' : ''}
                </h3>
                <ul className="text-xs text-red-300 space-y-1">
                  {preview.errors.slice(0, 10).map((e: { row?: number; column?: string; message: string }, i) => (
                    <li key={i}>{typeof e === 'string' ? e : `Row ${e.row}: ${e.column ? `"${e.column}" — ` : ''}${e.message}`}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="bg-neutral-800/50 border border-neutral-700 rounded-xl overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-neutral-800 text-neutral-300 text-left">
                    {preview.columns.map((col) => (
                      <th key={col} className="px-4 py-2 font-medium whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview.slice(0, 10).map((row, i) => (
                    <tr key={i} className="border-t border-neutral-700 text-neutral-200">
                      {preview.columns.map((col) => (
                        <td key={col} className="px-4 py-2 whitespace-nowrap">{String(row[col] ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-xs text-neutral-500">{preview.rows} total rows · showing first {Math.min(preview.preview.length, 10)}</p>

            {error && (
              <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 rounded-lg px-4 py-3">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <div className="flex items-center gap-3">
              <button
                disabled={loading}
                onClick={handleUpload}
                className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-neutral-700 disabled:text-neutral-500 text-white rounded-lg transition-colors text-sm font-medium"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                Confirm Upload
              </button>
              <button
                disabled={loading}
                onClick={reset}
                className="flex items-center gap-2 px-4 py-2.5 bg-neutral-700 hover:bg-neutral-600 text-neutral-200 rounded-lg transition-colors text-sm"
              >
                <ArrowLeft className="w-4 h-4" />
                Cancel
              </button>
            </div>
          </div>
        )}

        {step === 'result' && result && (
          <div className="space-y-6">
            <div className={cn('rounded-xl p-6 border', result.success ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-red-500/10 border-red-500/20')}>
              <div className="flex items-center gap-3 mb-3">
                {result.success ? <CheckCircle2 className="w-6 h-6 text-emerald-400" /> : <AlertCircle className="w-6 h-6 text-red-400" />}
                <h2 className="text-lg font-semibold text-white">{result.success ? 'Upload Successful' : 'Upload Failed'}</h2>
              </div>
              {result.success && (
                <div className="text-sm text-neutral-300 space-y-1">
                  <p>Rows loaded: <span className="text-white font-medium">{result.rows_loaded}</span></p>
                  <p>Columns: <span className="text-white font-medium">{result.columns.join(', ')}</span></p>
                  <p>Backup ID: <span className="text-white font-mono text-xs">{result.backup_id}</span></p>
                </div>
              )}
            </div>

            <button
              onClick={reset}
              className="flex items-center gap-2 px-4 py-2.5 bg-neutral-700 hover:bg-neutral-600 text-neutral-200 rounded-lg transition-colors text-sm"
            >
              <Upload className="w-4 h-4" />
              Upload Another
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
