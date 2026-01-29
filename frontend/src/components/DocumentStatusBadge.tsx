"use client";

import type { DocumentStatus } from "@/lib/types";
import { statusColors, statusLabels } from "@/lib/types";

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
  className?: string;
}

export function DocumentStatusBadge({
  status,
  className = "",
}: DocumentStatusBadgeProps) {
  const colorClass = statusColors[status];
  const label = statusLabels[status];

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass} ${className}`}
    >
      {label}
    </span>
  );
}
