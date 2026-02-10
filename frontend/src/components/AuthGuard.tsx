"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/AuthContext";
import { PendingApprovalPage } from "./PendingApprovalPage";

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { user, userInfo, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Show pending approval page
  if (userInfo?.status === "pending") {
    return <PendingApprovalPage />;
  }

  // Show access denied page for rejected users
  if (userInfo?.status === "rejected") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full p-8 bg-white rounded-lg shadow-md">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
              <svg
                className="h-6 w-6 text-red-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h2 className="mt-6 text-2xl font-bold text-red-600">
              Access Denied
            </h2>
            <p className="mt-4 text-gray-600">
              Your access request has been rejected. Please contact the
              administrator if you believe this is an error.
            </p>
            <p className="mt-2 text-sm text-gray-500">Email: {userInfo?.email}</p>
          </div>
        </div>
      </div>
    );
  }

  // Only approved users can access the content
  return <>{children}</>;
}
