import { format, parseISO } from "date-fns";
import type { Case } from "@/types";

export function formatDate(dateString: string): string {
  try {
    return format(parseISO(dateString), "MMM d, yyyy HH:mm");
  } catch {
    return dateString;
  }
}

export function formatDateShort(dateString: string): string {
  try {
    return format(parseISO(dateString), "MMM d");
  } catch {
    return dateString;
  }
}

export function getCompletionPercentage(caseData: Case): number {
  if (caseData.case_type !== "loa" || caseData.required_fields.length === 0) {
    return caseData.status === "COMPLETE" ? 100 : 0;
  }

  const receivedCount = caseData.required_fields.filter(
    (field) => field in caseData.received_fields
  ).length;

  return Math.round((receivedCount / caseData.required_fields.length) * 100);
}

export function getMissingFields(caseData: Case): string[] {
  if (caseData.case_type !== "loa") {
    return [];
  }

  return caseData.required_fields.filter(
    (field) => !(field in caseData.received_fields)
  );
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    OPEN: "bg-blue-100 text-blue-800",
    IN_PROGRESS: "bg-yellow-100 text-yellow-800",
    AWAITING_INFO: "bg-orange-100 text-orange-800",
    COMPLETE: "bg-green-100 text-green-800",
    CANCELLED: "bg-gray-100 text-gray-800",
  };
  return colors[status] || "bg-gray-100 text-gray-800";
}

export function getCaseTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    loa: "LoA",
    general: "General",
    annual_review: "Annual Review",
  };
  return labels[type] || type;
}
