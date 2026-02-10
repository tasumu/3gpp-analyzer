"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth/AuthContext";
import { listUsers, approveUser, rejectUser } from "@/lib/api";
import type { AdminUser, UserStatus } from "@/lib/types";
import { userStatusColors, userStatusLabels } from "@/lib/types";

export default function AdminUsersPage() {
  const { userInfo } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<UserStatus | "all">("all");
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    loadUsers();
  }, [statusFilter]);

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const filter = statusFilter === "all" ? undefined : statusFilter;
      const response = await listUsers(filter);
      setUsers(response.users);
    } catch (err) {
      console.error("Failed to load users:", err);
      setError("Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (uid: string) => {
    try {
      await approveUser(uid);
      setSuccessMessage("User approved successfully");
      setTimeout(() => setSuccessMessage(null), 3000);
      loadUsers();
    } catch (err) {
      console.error("Failed to approve user:", err);
      setError("Failed to approve user");
      setTimeout(() => setError(null), 3000);
    }
  };

  const handleReject = async (uid: string) => {
    try {
      await rejectUser(uid);
      setSuccessMessage("User rejected");
      setTimeout(() => setSuccessMessage(null), 3000);
      loadUsers();
    } catch (err) {
      console.error("Failed to reject user:", err);
      setError("Failed to reject user");
      setTimeout(() => setError(null), 3000);
    }
  };

  // Check if user is admin
  if (userInfo?.role !== "admin") {
    return (
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-700">Admin access required</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">
          User Management
        </h1>

        {/* Success/Error Messages */}
        {successMessage && (
          <div className="mb-4 bg-green-50 border border-green-200 rounded-md p-4">
            <p className="text-green-700">{successMessage}</p>
          </div>
        )}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Filter */}
        <div className="mb-4">
          <label className="mr-2 text-sm font-medium text-gray-700">
            Status:
          </label>
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as UserStatus | "all")
            }
            className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        {/* User Table */}
        {loading ? (
          <div className="text-center py-8">
            <div className="text-gray-500">Loading...</div>
          </div>
        ) : users.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500">No users found</p>
          </div>
        ) : (
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Display Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created At
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users.map((user) => (
                  <tr key={user.uid}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.email}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {user.display_name || "-"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${userStatusColors[user.status]}`}
                      >
                        {userStatusLabels[user.status]}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <span className="capitalize">{user.role}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                      {user.status === "pending" && (
                        <>
                          <button
                            onClick={() => handleApprove(user.uid)}
                            className="text-green-600 hover:text-green-900"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(user.uid)}
                            className="text-red-600 hover:text-red-900"
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {user.status !== "pending" && (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
