"use client";

import { useState, useRef, useEffect } from "react";
import { useMeetings } from "@/lib/hooks/useDocuments";

interface MultipleMeetingSelectorProps {
  selectedMeetingIds: string[];
  onSelect: (meetingIds: string[]) => void;
  maxSelections?: number;
}

export function MultipleMeetingSelector({
  selectedMeetingIds,
  onSelect,
  maxSelections = 2,
}: MultipleMeetingSelectorProps) {
  const { meetings, isLoading, error } = useMeetings();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  const handleToggle = (meetingId: string) => {
    if (selectedMeetingIds.includes(meetingId)) {
      // Remove from selection
      onSelect(selectedMeetingIds.filter((id) => id !== meetingId));
    } else {
      // Add to selection if not at max
      if (selectedMeetingIds.length < maxSelections) {
        onSelect([...selectedMeetingIds, meetingId]);
      }
    }
  };

  const handleRemove = (meetingId: string) => {
    onSelect(selectedMeetingIds.filter((id) => id !== meetingId));
  };

  const getDisplayText = () => {
    if (selectedMeetingIds.length === 0) {
      return "Select meetings...";
    }
    const selectedNames = selectedMeetingIds
      .map((id) => meetings.find((m) => m.id === id)?.name)
      .filter(Boolean);
    return selectedNames.join(", ") || "Select meetings...";
  };

  if (isLoading) {
    return (
      <div className="animate-pulse">
        <div className="h-10 bg-gray-200 rounded w-64" />
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
    <div className="relative" ref={dropdownRef}>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        Meetings:
      </label>

      {/* Dropdown button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="relative w-full md:w-96 bg-white border border-gray-300 rounded-md shadow-sm pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
      >
        <span className="block truncate text-gray-900">
          {getDisplayText()}
        </span>
        <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
          <svg
            className="h-5 w-5 text-gray-400"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </span>
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute z-10 mt-1 w-full md:w-96 bg-white shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none sm:text-sm">
          {meetings.length === 0 ? (
            <div className="px-3 py-2 text-gray-500">No meetings available</div>
          ) : (
            <>
              <div className="px-3 py-2 text-xs text-gray-500 border-b border-gray-200">
                {selectedMeetingIds.length === 0
                  ? `Select up to ${maxSelections} meetings`
                  : `${selectedMeetingIds.length} / ${maxSelections} selected`}
              </div>
              {meetings.map((meeting) => {
                const isSelected = selectedMeetingIds.includes(meeting.id);
                const isDisabled = !isSelected && selectedMeetingIds.length >= maxSelections;

                return (
                  <label
                    key={meeting.id}
                    className={`flex items-center px-3 py-2 hover:bg-gray-100 ${
                      isDisabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => !isDisabled && handleToggle(meeting.id)}
                      disabled={isDisabled}
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    />
                    <span className="ml-3 block truncate">
                      {meeting.name}{" "}
                      <span className="text-gray-500 text-xs">
                        ({meeting.indexed_count}/{meeting.document_count})
                      </span>
                    </span>
                  </label>
                );
              })}
            </>
          )}
        </div>
      )}

      {/* Selected tags */}
      {selectedMeetingIds.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {selectedMeetingIds.map((id) => {
            const meeting = meetings.find((m) => m.id === id);
            return (
              <span
                key={id}
                className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-primary-100 text-primary-800"
              >
                {meeting?.name || id}
                <button
                  type="button"
                  onClick={() => handleRemove(id)}
                  className="ml-1 inline-flex items-center justify-center w-4 h-4 text-primary-600 hover:text-primary-800 focus:outline-none"
                >
                  <svg
                    className="w-3 h-3"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
