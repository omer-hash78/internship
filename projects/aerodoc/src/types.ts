export interface User {
  id: number;
  username: string;
  role: string;
}

export interface ComplianceFinding {
  severity: 'low' | 'medium' | 'high';
  issue: string;
  suggestion: string;
}

export interface Document {
  id: number;
  title: string;
  content: string;
  lastModified: string;
  status: 'Draft' | 'Review' | 'Approved';
  authorId: number;
}

export interface DocumentVersion {
  id: number;
  documentId: number;
  content: string;
  createdAt: string;
  authorId: number;
  authorName: string;
  versionNumber: number;
  reasonForChange?: string;
}
