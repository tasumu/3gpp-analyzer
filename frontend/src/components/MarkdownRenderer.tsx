'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
  showCopyButton?: boolean;
  className?: string;
}

export default function MarkdownRenderer({
  content,
  showCopyButton = true,
  className = '',
}: MarkdownRendererProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  return (
    <div className={className}>
      {showCopyButton && content.trim() && (
        <div className="flex justify-end mb-1">
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 text-xs font-medium text-gray-700
                       bg-white border border-gray-300 rounded-md hover:bg-gray-50
                       transition-colors shadow-sm"
            aria-label="Copy markdown to clipboard"
          >
            {copied ? (
              <span className="flex items-center gap-1">
                <svg
                  className="w-3.5 h-3.5 text-green-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                Copied!
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
                Copy
              </span>
            )}
          </button>
        </div>
      )}
      <div
        className="prose prose-sm max-w-none
                   prose-headings:text-gray-900 prose-headings:font-semibold
                   prose-p:my-3 prose-p:leading-relaxed
                   prose-ul:my-3 prose-ol:my-3
                   prose-li:my-1
                   prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline
                   prose-code:text-pink-600 prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded
                   prose-pre:bg-gray-100 prose-pre:border prose-pre:border-gray-200
                   prose-blockquote:border-l-4 prose-blockquote:border-gray-300 prose-blockquote:pl-4 prose-blockquote:italic
                   prose-table:border-collapse prose-th:border prose-th:border-gray-300 prose-th:p-2 prose-th:bg-gray-100
                   prose-td:border prose-td:border-gray-300 prose-td:p-2"
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
