import Link from "next/link";
import type { Case } from "@/types";
import {
  formatDateShort,
  getCompletionPercentage,
  getStatusColor,
  getCaseTypeLabel,
} from "@/lib/utils";

interface CaseCardProps {
  caseData: Case;
}

export default function CaseCard({ caseData }: CaseCardProps) {
  const completion = getCompletionPercentage(caseData);

  return (
    <Link
      href={`/cases/${caseData.id}`}
      className="block bg-white rounded-lg shadow hover:shadow-md transition-shadow p-4"
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900 truncate">
            {caseData.client_name}
          </h3>
          <p className="text-sm text-gray-600 truncate">{caseData.case_title}</p>
        </div>
        <span
          className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(
            caseData.status
          )}`}
        >
          {caseData.status}
        </span>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">
          {getCaseTypeLabel(caseData.case_type)}
        </span>
        <span className="text-gray-400">
          {formatDateShort(caseData.updated_at)}
        </span>
      </div>

      {caseData.case_type === "loa" && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-600 mb-1">
            <span>Progress</span>
            <span>{completion}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{ width: `${completion}%` }}
            />
          </div>
        </div>
      )}
    </Link>
  );
}
