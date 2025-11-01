import { notFound } from "next/navigation";
import { getCase, getCaseAuditTrail } from "@/lib/api";
import {
  formatDate,
  getStatusColor,
  getCaseTypeLabel,
  getMissingFields,
  getCompletionPercentage,
} from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function CaseDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const caseData = await getCase(params.id);
  if (!caseData) {
    notFound();
  }

  const auditLogs = await getCaseAuditTrail(params.id);
  const missingFields = getMissingFields(caseData);
  const completion = getCompletionPercentage(caseData);

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-2xl font-bold text-gray-900">
            {caseData.client_name}
          </h2>
          <span
            className={`px-3 py-1 text-sm font-medium rounded-full ${getStatusColor(
              caseData.status
            )}`}
          >
            {caseData.status}
          </span>
        </div>
        <p className="text-gray-600">{caseData.case_title}</p>
        <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
          <span>{getCaseTypeLabel(caseData.case_type)}</span>
          <span>•</span>
          <span>Updated {formatDate(caseData.updated_at)}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Progress (for LoA cases) */}
          {caseData.case_type === "loa" && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Field Progress
              </h3>
              <div className="mb-4">
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <span>Completion</span>
                  <span className="font-medium">{completion}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className="bg-blue-600 h-3 rounded-full transition-all"
                    style={{ width: `${completion}%` }}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Required:</span>{" "}
                  <span className="font-medium">
                    {caseData.required_fields.length}
                  </span>
                </div>
                <div>
                  <span className="text-gray-600">Received:</span>{" "}
                  <span className="font-medium">
                    {Object.keys(caseData.received_fields).length}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Received Fields */}
          {Object.keys(caseData.received_fields).length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Received Fields
              </h3>
              <div className="space-y-3">
                {Object.entries(caseData.received_fields).map(
                  ([fieldName, fieldValue]) => (
                    <div
                      key={fieldName}
                      className="border-l-4 border-green-500 pl-4 py-2"
                    >
                      <div className="font-medium text-gray-900">
                        {fieldName}
                      </div>
                      <div className="text-sm text-gray-700 mt-1">
                        {fieldValue.value}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        {formatDate(fieldValue.received_at)}
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* Missing Fields */}
          {missingFields.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Missing Fields
              </h3>
              <div className="space-y-2">
                {missingFields.map((field) => (
                  <div
                    key={field}
                    className="border-l-4 border-orange-500 pl-4 py-2 text-gray-700"
                  >
                    {field}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Audit Trail */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Audit Trail
            </h3>
            <div className="space-y-4">
              {auditLogs.length > 0 ? (
                auditLogs.map((log) => (
                  <div
                    key={log.id}
                    className="border-l-2 border-gray-300 pl-4 pb-4"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="font-medium text-gray-900">
                          {log.action_type}
                        </div>
                        <div className="text-sm text-gray-600 mt-1">
                          {formatDate(log.timestamp)}
                        </div>
                      </div>
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          log.success
                            ? "bg-green-100 text-green-800"
                            : "bg-red-100 text-red-800"
                        }`}
                      >
                        {log.success ? "Success" : "Failed"}
                      </span>
                    </div>
                    {log.error_message && (
                      <div className="text-sm text-red-600 mt-2">
                        {log.error_message}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-gray-500 text-sm">No audit logs found</p>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Case Info */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Case Details
            </h3>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-600">Case ID</dt>
                <dd className="text-gray-900 font-mono text-xs mt-1 break-all">
                  {caseData.id}
                </dd>
              </div>
              <div>
                <dt className="text-gray-600">Type</dt>
                <dd className="text-gray-900 mt-1">
                  {getCaseTypeLabel(caseData.case_type)}
                </dd>
              </div>
              <div>
                <dt className="text-gray-600">Created</dt>
                <dd className="text-gray-900 mt-1">
                  {formatDate(caseData.created_at)}
                </dd>
              </div>
              {caseData.completed_at && (
                <div>
                  <dt className="text-gray-600">Completed</dt>
                  <dd className="text-gray-900 mt-1">
                    {formatDate(caseData.completed_at)}
                  </dd>
                </div>
              )}
              {caseData.assigned_to && (
                <div>
                  <dt className="text-gray-600">Assigned To</dt>
                  <dd className="text-gray-900 mt-1">{caseData.assigned_to}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Tags */}
          {caseData.tags.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {caseData.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-full"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Notes */}
          {caseData.notes && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Notes
              </h3>
              <p className="text-sm text-gray-700">{caseData.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
