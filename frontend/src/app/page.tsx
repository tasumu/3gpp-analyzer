"use client";

import Link from "next/link";
import { AuthGuard } from "@/components/AuthGuard";

export default function Home() {
  return (
    <AuthGuard>
    <div className="py-12">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          3GPP Document Analyzer
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          AI-powered analysis system for 3GPP standardization documents (Contributions).
          Search, analyze, and extract insights from technical specifications.
        </p>
        <div className="flex justify-center gap-4">
          <Link
            href="/documents"
            className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            View Documents
          </Link>
        </div>
      </div>

      <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="text-primary-600 mb-4">
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold mb-2">Document Management</h3>
          <p className="text-gray-600">
            Sync and manage 3GPP contribution documents from FTP.
            Automatic format normalization and structure extraction.
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="text-primary-600 mb-4">
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold mb-2">Semantic Search</h3>
          <p className="text-gray-600">
            Find relevant content using AI-powered semantic search.
            Vector embeddings enable natural language queries.
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="text-primary-600 mb-4">
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold mb-2">Evidence Traceability</h3>
          <p className="text-gray-600">
            All analysis results include citations with contribution number,
            clause, and page references.
          </p>
        </div>
      </div>
    </div>
    </AuthGuard>
  );
}
