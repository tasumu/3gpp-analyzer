"use client";

import { useMeetings } from "@/lib/hooks/useDocuments";

interface MeetingSelectorProps {
  selectedMeetingId: string | null;
  onSelect: (meetingId: string | null) => void;
}

export function MeetingSelector({
  selectedMeetingId,
  onSelect,
}: MeetingSelectorProps) {
  const { meetings, isLoading, error } = useMeetings();

  if (isLoading) {
    return (
      <div className="animate-pulse">
        <div className="h-10 bg-gray-200 rounded w-48" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-sm text-red-600">
        Failed to load meetings
      </div>
    );
  }

  return (
    <div className="flex items-center space-x-2">
      <label htmlFor="meeting-select" className="text-sm font-medium text-gray-700">
        Meeting:
      </label>
      <select
        id="meeting-select"
        value={selectedMeetingId || ""}
        onChange={(e) => onSelect(e.target.value || null)}
        className="block w-64 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
      >
        <option value="">All Meetings</option>
        {meetings.map((meeting) => (
          <option key={meeting.id} value={meeting.id}>
            {meeting.name} ({meeting.indexed_count}/{meeting.document_count})
          </option>
        ))}
      </select>
    </div>
  );
}
