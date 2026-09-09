export interface User {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'investigator' | 'reviewer';
}

export interface CaseRecord {
  id: string;
  title: string;
  description?: string;
  case_number?: string;
  created_at: string;
}

export interface EvidenceRecord {
  id: string;
  case_id: string;
  original_filename: string;
  mime_type?: string;
  size_bytes?: number;
  sha256?: string;
  collector_id?: string;
  collection_timestamp?: string;
}
