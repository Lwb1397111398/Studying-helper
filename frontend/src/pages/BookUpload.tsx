import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadBook } from '../api/books';

export default function BookUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const handleUpload = async (file: File) => {
    const allowedTypes = ['application/pdf', 'text/plain', 'application/epub+zip'];
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(pdf|txt|epub)$/i)) {
      setError('仅支持 PDF、TXT、EPUB 格式');
      return;
    }

    setUploading(true);
    setError('');
    setProgress(0);

    try {
      const book = await uploadBook(file, setProgress);
      navigate(`/books/${book.id}`);
    } catch (err: any) {
      setError(err.message || '上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  };

  return (
    <div className="max-w-xl mx-auto animate-fade-in">
      {/* 标题 */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-800 mb-2">上传书籍</h1>
        <p className="text-sm text-gray-400">支持 PDF、TXT、EPUB 格式，最大 100MB</p>
      </div>

      {/* 上传区域 */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !uploading && fileInputRef.current?.click()}
        className={`
          relative rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer
          transition-all duration-300 ease-out
          ${dragOver
            ? 'border-blue-400 bg-blue-50/50 scale-[1.02] shadow-lg shadow-blue-500/10'
            : uploading
              ? 'border-gray-200 bg-gray-50/50 cursor-default'
              : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/30 hover:shadow-md'
          }
        `}
      >
        {uploading ? (
          <div className="animate-fade-in">
            {/* 圆形进度 */}
            <div className="relative w-20 h-20 mx-auto mb-6">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="34" fill="none" stroke="#e2e8f0" strokeWidth="6" />
                <circle
                  cx="40" cy="40" r="34" fill="none" stroke="url(#gradient)" strokeWidth="6"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 34}`}
                  strokeDashoffset={`${2 * Math.PI * 34 * (1 - progress / 100)}`}
                  className="transition-all duration-300"
                />
                <defs>
                  <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#3b82f6" />
                    <stop offset="100%" stopColor="#8b5cf6" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-gray-700">{progress}%</span>
              </div>
            </div>
            <p className="text-sm font-medium text-gray-600 mb-1">正在上传...</p>
            <p className="text-xs text-gray-400">解析完成后将自动跳转</p>
          </div>
        ) : (
          <div>
            <div className={`w-16 h-16 mx-auto mb-5 rounded-2xl flex items-center justify-center transition-all duration-300 ${
              dragOver ? 'bg-blue-100 scale-110' : 'bg-gradient-to-br from-blue-50 to-purple-50'
            }`}>
              <svg className={`w-8 h-8 transition-colors ${dragOver ? 'text-blue-500' : 'text-blue-400'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p className="text-sm font-medium text-gray-600 mb-1">
              {dragOver ? '松开鼠标上传' : '拖拽文件到此处'}
            </p>
            <p className="text-xs text-gray-400 mb-5">或点击选择文件</p>

            {/* 格式标签 */}
            <div className="flex justify-center gap-2">
              {['PDF', 'TXT', 'EPUB'].map(fmt => (
                <span key={fmt} className="px-3 py-1 bg-gray-50 text-gray-400 text-[10px] font-semibold rounded-full uppercase tracking-wider">
                  {fmt}
                </span>
              ))}
            </div>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.epub"
          onChange={handleFileChange}
          className="hidden"
        />
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-100 rounded-xl flex items-center gap-3 animate-fade-in">
          <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-red-500" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
    </div>
  );
}
