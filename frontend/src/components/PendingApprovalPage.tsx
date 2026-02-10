"use client";

import { useAuth } from "@/lib/auth/AuthContext";

export function PendingApprovalPage() {
  const { signOut, userInfo } = useAuth();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow-md">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-yellow-100">
            <svg
              className="h-6 w-6 text-yellow-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            Approval Pending
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Your account is waiting for administrator approval
          </p>
        </div>

        <div className="rounded-md bg-blue-50 p-4">
          <div className="flex">
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">
                Account Information
              </h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>Email: {userInfo?.email}</p>
                <p className="mt-1">
                  Status: <span className="font-semibold">Pending</span>
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Please wait while an administrator reviews your access request. You
            will be notified via email once your account is approved.
          </p>
          <p className="text-sm text-gray-600">
            If you have any questions, please contact the system administrator.
          </p>
        </div>

        <div>
          <button
            onClick={signOut}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
