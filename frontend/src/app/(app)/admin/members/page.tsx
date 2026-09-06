import { InvitationsPanel } from "@/components/admin/invitations-panel";
import { MembersAdmin } from "@/components/admin/members-admin";

export default function MembersPage() {
  return (
    <div className="space-y-8">
      <MembersAdmin />
      <InvitationsPanel />
    </div>
  );
}
