/**
 * Workspace & Identity Administration API (P2.17).
 *
 * Self-service tenant creation + the member roster (add/role/suspend/remove),
 * ownership transfer, workspace settings and admin password reset — over
 * /api/v1/workspaces/. Member endpoints are workspace-slug scoped.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface WorkspaceMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  status: string;
  custom_role_id: string | null;
  joined_at: string | null;
  is_owner: boolean;
}

export interface WorkspaceDetail {
  id: string;
  name: string;
  slug: string;
  plan: string;
  logo_url: string;
  owner: string | null;
  max_members: number;
  max_entities: number;
  max_records: number;
  max_storage_bytes: number;
  settings: Record<string, unknown>;
  is_active: boolean;
  role?: string;
}

export interface CreateWorkspaceInput {
  name: string;
  slug?: string;
  plan?: string;
}

export interface AddMemberInput {
  email: string;
  full_name?: string;
  role?: "admin" | "member" | "viewer";
}

export interface WorkspaceInvitation {
  id: string;
  email: string;
  role: string;
  status: "pending" | "accepted" | "rejected" | "cancelled" | "expired";
  invited_by: string | null;
  expires_at: string;
  responded_at: string | null;
  created_at: string;
}

const base = "/api/v1/workspaces";

export const workspaceAdminApi = {
  create: (data: CreateWorkspaceInput) =>
    apiSend<WorkspaceDetail & { role: string }>(`${base}/`, "POST", data),
  detail: (slug: string) => apiGet<WorkspaceDetail>(`${base}/${slug}/`),
  update: (slug: string, data: Partial<WorkspaceDetail>) =>
    apiSend<WorkspaceDetail>(`${base}/${slug}/`, "PATCH", data),

  members: (slug: string) => apiGet<WorkspaceMember[]>(`${base}/${slug}/members/`),
  addMember: (slug: string, data: AddMemberInput) =>
    apiSend<WorkspaceMember & { created_user: boolean }>(`${base}/${slug}/members/`, "POST", data),
  assignRole: (slug: string, memberId: string, role: string) =>
    apiSend<WorkspaceMember>(`${base}/${slug}/members/${memberId}/`, "PATCH", { role }),
  removeMember: (slug: string, memberId: string) =>
    apiSend<void>(`${base}/${slug}/members/${memberId}/`, "DELETE"),
  suspendMember: (slug: string, memberId: string) =>
    apiSend<WorkspaceMember>(`${base}/${slug}/members/${memberId}/suspend/`, "POST"),
  reactivateMember: (slug: string, memberId: string) =>
    apiSend<WorkspaceMember>(`${base}/${slug}/members/${memberId}/reactivate/`, "POST"),
  resetPassword: (slug: string, memberId: string) =>
    apiSend<{ detail: string }>(`${base}/${slug}/members/${memberId}/reset-password/`, "POST"),
  transferOwnership: (slug: string, memberId: string) =>
    apiSend<WorkspaceMember>(`${base}/${slug}/transfer-ownership/`, "POST", { member_id: memberId }),

  // Invitation lifecycle
  invitations: (slug: string, status?: string) =>
    apiGet<WorkspaceInvitation[]>(`${base}/${slug}/invitations/${status ? `?status=${status}` : ""}`),
  invite: (slug: string, data: { email: string; role?: string }) =>
    apiSend<WorkspaceInvitation>(`${base}/${slug}/invitations/`, "POST", data),
  resendInvitation: (slug: string, id: string) =>
    apiSend<WorkspaceInvitation>(`${base}/${slug}/invitations/${id}/resend/`, "POST"),
  cancelInvitation: (slug: string, id: string) =>
    apiSend<WorkspaceInvitation>(`${base}/${slug}/invitations/${id}/cancel/`, "POST"),
  acceptInvitation: (token: string) =>
    apiSend<WorkspaceMember>(`${base}/invitations/accept/`, "POST", { token }),
  rejectInvitation: (token: string) =>
    apiSend<{ detail: string }>(`${base}/invitations/reject/`, "POST", { token }),

  // Lifecycle (archive / delete / restore)
  archivedWorkspaces: () => apiGet<WorkspaceDetail[]>(`${base}/?archived=true`),
  archiveWorkspace: (slug: string) =>
    apiSend<WorkspaceDetail>(`${base}/${slug}/archive/`, "POST"),
  restoreWorkspace: (slug: string) =>
    apiSend<WorkspaceDetail>(`${base}/${slug}/restore/`, "POST"),
  softDeleteWorkspace: (slug: string) => apiSend<void>(`${base}/${slug}/`, "DELETE"),
  requestHardDelete: (slug: string) =>
    apiSend<{ confirmation_token: string; detail: string }>(`${base}/${slug}/delete-permanently/`, "POST"),
  confirmHardDelete: (slug: string, token: string) =>
    apiSend<void>(`${base}/${slug}/delete-permanently/confirm/`, "POST", { token }),
};
