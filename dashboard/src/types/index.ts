export type CaseType = "loa" | "general" | "annual_review";

export type CaseStatus =
  | "OPEN"
  | "IN_PROGRESS"
  | "AWAITING_INFO"
  | "COMPLETE"
  | "CANCELLED";

export interface FieldValue {
  field_name: string;
  value: string;
  received_at: string;
  source_message_id: string;
  confidence: number;
}

export interface Case {
  id: string;
  client_name: string;
  case_title: string;
  case_type: CaseType;
  status: CaseStatus;
  required_fields: string[];
  received_fields: Record<string, FieldValue>;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  assigned_to?: string;
  tags: string[];
  notes: string;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  case_id: string;
  action_type: string;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  triggered_by: string;
  success: boolean;
  error_message?: string;
}

export interface DashboardStats {
  total_cases: number;
  open_cases: number;
  in_progress_cases: number;
  completed_cases: number;
  total_loa_cases: number;
  loa_completion_rate: number;
}
