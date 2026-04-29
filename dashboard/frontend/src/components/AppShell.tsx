"use client";

import { type ReactNode } from "react";
import { RoleGate } from "@/components/RoleGate";
import { Shell } from "@/components/Shell";
import type { Role, User } from "@/lib/api";

/**
 * One-line page wrapper.
 *
 *   <AppShell crumbs={["Workspace", "Dashboard"]} roles={["admin"]}>
 *     {(user) => <YourPageContent user={user} />}
 *   </AppShell>
 *
 * Combines the role gate (auth + redirect) with the sidebar/topbar shell.
 */
export function AppShell({
  roles,
  crumbs,
  topbarStatus,
  topbarActions,
  children,
}: {
  roles?: Role[];
  crumbs: string[];
  topbarStatus?: ReactNode;
  topbarActions?: ReactNode;
  children: (user: User) => ReactNode;
}) {
  return (
    <RoleGate roles={roles}>
      {(user) => (
        <Shell user={user} crumbs={crumbs} topbarStatus={topbarStatus} topbarActions={topbarActions}>
          {children(user)}
        </Shell>
      )}
    </RoleGate>
  );
}
