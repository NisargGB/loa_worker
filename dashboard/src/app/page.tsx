import StatsCard from "@/components/StatsCard";
import CaseCard from "@/components/CaseCard";
import { getDashboardStats, getCases } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const stats = await getDashboardStats();
  const recentCases = await getCases(undefined, 6);

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Dashboard Overview
        </h2>
        <p className="text-gray-600">
          Monitor Letters of Authority processing in real-time
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatsCard title="Total Cases" value={stats.total_cases} />
        <StatsCard title="Open Cases" value={stats.open_cases} />
        <StatsCard title="In Progress" value={stats.in_progress_cases} />
        <StatsCard
          title="Completed"
          value={stats.completed_cases}
          subtitle={`${Math.round(
            (stats.completed_cases / stats.total_cases) * 100
          )}% completion rate`}
        />
      </div>

      {/* LoA Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <StatsCard
          title="Total LoA Cases"
          value={stats.total_loa_cases}
          subtitle="Letters of Authority"
        />
        <StatsCard
          title="LoA Completion Rate"
          value={`${Math.round(stats.loa_completion_rate)}%`}
          subtitle="Percentage of LoA cases completed"
        />
      </div>

      {/* Recent Cases */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Recent Cases</h3>
          <a
            href="/cases"
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            View all →
          </a>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {recentCases.map((caseData) => (
            <CaseCard key={caseData.id} caseData={caseData} />
          ))}
        </div>
        {recentCases.length === 0 && (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <p className="text-gray-500">No cases found</p>
            <p className="text-sm text-gray-400 mt-1">
              Process messages to create cases
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
