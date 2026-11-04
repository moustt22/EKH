export type User = {
  id: string;
  name: string;
  email: string;
  department_id: string;
  department_name: string;
  role: "employee" | "department_manager" | "administrator" | string;
  is_active: boolean;
};

export type Department = { id: string; name: string };

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Citation = {
  document_id: string;
  title: string;
  page: number;
  version: number;
  passage: string;
};

export type Message = {
  id: string;
  role: string;
  content: string;
  citations: Citation[];
  created_at: string;
};

export type ConversationDetail = Conversation & { messages: Message[] };

export type SearchHit = {
  document_id: string;
  chunk_id: string;
  title: string;
  snippet: string;
  page: number;
  section: string;
  version: number;
  file_type: string;
  classification: string;
  department_name: string;
  score: number;
};

export type DocumentItem = {
  id: string;
  title: string;
  original_filename: string;
  file_type: string;
  owner_id: string;
  department_id: string;
  department_name: string;
  classification: string;
  access_scope: string;
  status: string;
  current_version: number;
  size_bytes: number;
  created_at: string;
};

export type Job = {
  job_id: string;
  document_id: string;
  status: string;
  version: number;
  error: string | null;
};

export type Grant = {
  user_id: string;
  name: string;
  email: string;
  permission: string;
};

export type AuditEvent = {
  id: string;
  actor_id: string | null;
  actor_email: string;
  action: string;
  outcome: string;
  resource_type: string;
  resource_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
};
