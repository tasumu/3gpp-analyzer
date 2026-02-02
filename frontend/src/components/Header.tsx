"use client";

import { useAuth } from "@/lib/auth/AuthContext";
import { usePathname } from "next/navigation";

export function Header() {
  const { user, loading, signOut } = useAuth();
  const pathname = usePathname();

  // Don't show header on login page
  if (pathname === "/login") {
    return null;
  }

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <a href="/" className="text-xl font-bold text-primary-600">
              3GPP Analyzer
            </a>
          </div>
          <nav className="flex items-center space-x-4">
            <a
              href="/documents"
              className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
            >
              Documents
            </a>
            <a
              href="/analysis"
              className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
            >
              Analysis
            </a>
            <a
              href="/sync"
              className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
            >
              Sync
            </a>
            {!loading && user && (
              <div className="flex items-center space-x-3 ml-4 pl-4 border-l border-gray-200">
                <span className="text-sm text-gray-600">{user.email}</span>
                <button
                  onClick={signOut}
                  className="text-sm text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                >
                  Logout
                </button>
              </div>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
}
