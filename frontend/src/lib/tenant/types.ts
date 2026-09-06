export interface WorkspaceLimits {
  max_members: number;
  max_entities: number;
  max_records: number;
  max_storage_bytes: number;
}

export interface Workspace {
  id: string;
  slug: string;
  name: string;
  plan: string;
  logo_url: string;
  role: string;
  limits: WorkspaceLimits;
}

export type FeatureFlags = Record<string, { enabled: boolean; config: Record<string, unknown> }>;
