export type DocumentStatus = "pending" | "verified" | "cancelled" | "error";

export type DocumentRecord = {
  documentId: string;
  uploadTime: string;
  documentType: string;
  userCategory: string;
  tags: string[];
  status: DocumentStatus;
  amount?: number;
  sourceImage?: string;
  markdownContent?: string;
  issuedDate?: string;
};

export type ClassificationSummary = {
  categoryDistribution: Record<string, number>;
  recentTrend: Array<{ date: string; count: number }>;
  frequentTags: Array<{ tag: string; count: number }>;
  totalDocuments: number;
  pendingDocuments: number;
  ruleCount: number;
};

export type UploadResponse = {
  success: boolean;
  sessionId?: string;
  documentId?: string;
  state?: string;
  error?: string;
  recognition?: {
    markdown_content?: string;
    document_type?: string;
  };
  classification?: {
    professional_category?: string;
    user_category?: string;
    tags?: string[];
    reasoning?: string;
  };
};

export type ProfileOptimizationResponse = {
  success: boolean;
  triggered?: boolean;
  updated_profile?: string[];
  operations_count?: number;
  message?: string;
  error?: string;
};
