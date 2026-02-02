"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { listMeetings } from "@/lib/api";
import type { Meeting } from "@/lib/types";

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadMeetings() {
      try {
        setIsLoading(true);
        const response = await listMeetings();
        setMeetings(response.meetings);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load meetings");
      } finally {
        setIsLoading(false);
      }
    }
    loadMeetings();
  }, []);

  return (
    <AuthGuard>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Meetings</h1>
          <p className="text-sm text-gray-500 mt-1">
            Browse 3GPP working group meetings and generate reports.
          </p>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="text-center py-12 text-gray-500">
            Loading meetings...
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && meetings.length === 0 && (
          <div className="text-center py-12 border border-dashed rounded-lg">
            <p className="text-gray-500">No meetings found.</p>
            <Link
              href="/sync"
              className="mt-2 inline-block text-blue-600 hover:text-blue-800"
            >
              Sync documents from FTP
            </Link>
          </div>
        )}

        {/* Meeting list */}
        {!isLoading && meetings.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {meetings.map((meeting) => (
              <Link
                key={meeting.id}
                href={`/meetings/${encodeURIComponent(meeting.id)}`}
                className="block bg-white shadow-sm rounded-lg p-6 hover:shadow-md
                         transition-shadow border border-gray-200"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-medium text-gray-900 truncate">
                      {meeting.name}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                      {meeting.working_group}
                    </p>
                  </div>
                  {meeting.indexed_count === meeting.document_count && (
                    <span className="ml-2 px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">
                      Ready
                    </span>
                  )}
                </div>

                <div className="mt-4 flex items-center justify-between text-sm">
                  <span className="text-gray-600">
                    {meeting.indexed_count} / {meeting.document_count} documents indexed
                  </span>
                  <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-600 rounded-full transition-all"
                      style={{
                        width: `${
                          meeting.document_count > 0
                            ? (meeting.indexed_count / meeting.document_count) * 100
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AuthGuard>
  );
}
