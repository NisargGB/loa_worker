import { db } from "./firestore";
import type { Case, AuditLog, DashboardStats } from "@/types";

// Helper to serialize Firestore data (convert Timestamps to ISO strings)
function serializeFirestoreData(data: any): any {
  if (data === null || data === undefined) {
    return data;
  }

  // Handle Firestore Timestamp objects
  if (data?.toDate && typeof data.toDate === "function") {
    return data.toDate().toISOString();
  }

  // Handle arrays
  if (Array.isArray(data)) {
    return data.map(serializeFirestoreData);
  }

  // Handle objects
  if (typeof data === "object") {
    const serialized: any = {};
    for (const key in data) {
      if (data.hasOwnProperty(key)) {
        serialized[key] = serializeFirestoreData(data[key]);
      }
    }
    return serialized;
  }

  return data;
}

export async function getCases(
  status?: string,
  limit: number = 50
): Promise<Case[]> {
  let query = db.collection("cases").orderBy("updated_at", "desc").limit(limit);

  if (status) {
    query = query.where("status", "==", status) as any;
  }

  const snapshot = await query.get();
  return snapshot.docs.map((doc) =>
    serializeFirestoreData({ id: doc.id, ...doc.data() }) as Case
  );
}

export async function getCase(id: string): Promise<Case | null> {
  const doc = await db.collection("cases").doc(id).get();
  if (!doc.exists) {
    return null;
  }
  return serializeFirestoreData({ id: doc.id, ...doc.data() }) as Case;
}

export async function getCaseAuditTrail(
  caseId: string,
  limit: number = 20
): Promise<AuditLog[]> {
  const snapshot = await db
    .collection("audit_logs")
    .where("case_id", "==", caseId)
    .orderBy("timestamp", "desc")
    .limit(limit)
    .get();

  return snapshot.docs.map((doc) =>
    serializeFirestoreData({ id: doc.id, ...doc.data() }) as AuditLog
  );
}

export async function getRecentAuditLogs(limit: number = 20): Promise<AuditLog[]> {
  const snapshot = await db
    .collection("audit_logs")
    .orderBy("timestamp", "desc")
    .limit(limit)
    .get();

  return snapshot.docs.map((doc) =>
    serializeFirestoreData({ id: doc.id, ...doc.data() }) as AuditLog
  );
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const casesSnapshot = await db.collection("cases").get();
  const cases = casesSnapshot.docs.map((doc) =>
    serializeFirestoreData(doc.data()) as Case
  );

  const total_cases = cases.length;
  const open_cases = cases.filter((c) => c.status === "OPEN").length;
  const in_progress_cases = cases.filter((c) => c.status === "IN_PROGRESS").length;
  const completed_cases = cases.filter((c) => c.status === "COMPLETE").length;
  const loa_cases = cases.filter((c) => c.case_type === "loa");
  const total_loa_cases = loa_cases.length;
  const completed_loa_cases = loa_cases.filter((c) => c.status === "COMPLETE").length;
  const loa_completion_rate =
    total_loa_cases > 0 ? (completed_loa_cases / total_loa_cases) * 100 : 0;

  return {
    total_cases,
    open_cases,
    in_progress_cases,
    completed_cases,
    total_loa_cases,
    loa_completion_rate,
  };
}
