import CaseCard from "@/components/CaseCard";
import { getCases } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CasesPage() {
  const cases = await getCases(undefined, 100);

  const statusGroups = {
    OPEN: cases.filter((c) => c.status === "OPEN"),
    IN_PROGRESS: cases.filter((c) => c.status === "IN_PROGRESS"),
    AWAITING_INFO: cases.filter((c) => c.status === "AWAITING_INFO"),
    COMPLETE: cases.filter((c) => c.status === "COMPLETE"),
  };

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">All Cases</h2>
        <p className="text-gray-600">
          View and manage all Letters of Authority cases
        </p>
      </div>

      {/* Status Tabs */}
      <div className="mb-6 flex space-x-2 overflow-x-auto">
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium whitespace-nowrap">
          All ({cases.length})
        </button>
        <button className="px-4 py-2 bg-white text-gray-700 rounded-lg font-medium hover:bg-gray-50 whitespace-nowrap">
          Open ({statusGroups.OPEN.length})
        </button>
        <button className="px-4 py-2 bg-white text-gray-700 rounded-lg font-medium hover:bg-gray-50 whitespace-nowrap">
          In Progress ({statusGroups.IN_PROGRESS.length})
        </button>
        <button className="px-4 py-2 bg-white text-gray-700 rounded-lg font-medium hover:bg-gray-50 whitespace-nowrap">
          Awaiting Info ({statusGroups.AWAITING_INFO.length})
        </button>
        <button className="px-4 py-2 bg-white text-gray-700 rounded-lg font-medium hover:bg-gray-50 whitespace-nowrap">
          Complete ({statusGroups.COMPLETE.length})
        </button>
      </div>

      {/* Cases Grid */}
      {cases.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cases.map((caseData) => (
            <CaseCard key={caseData.id} caseData={caseData} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <p className="text-gray-500">No cases found</p>
          <p className="text-sm text-gray-400 mt-1">
            Process messages using the CLI to create cases
          </p>
          <code className="text-xs bg-gray-100 px-2 py-1 rounded mt-2 inline-block">
            loa-worker process --file data.json
          </code>
        </div>
      )}
    </div>
  );
}
