"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getUser, type Role, type User } from "@/lib/api";
import { canAccess } from "@/lib/nav";

/**
 * Client-side gate. Three states:
 *   1. no token  -> redirect to /login
 *   2. token but role not in `roles` (or path not allowed) -> redirect to /dashboard
 *   3. authorized -> render children with the user available
 *
 * Backend role-checks at the gateway are the real enforcement; this is UX.
 */
export function RoleGate({
  roles,
  children,
}: {
  roles?: Role[];
  children: (user: User) => ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const u = getUser();
    if (!u) {
      router.replace("/login");
      return;
    }
    if (roles && !roles.includes(u.role)) {
      router.replace("/dashboard");
      return;
    }
    if (pathname && !canAccess(u.role, pathname)) {
      router.replace("/dashboard");
      return;
    }
    setUser(u);
    setReady(true);
  }, [pathname, roles, router]);

  if (!ready || !user) return null;
  return <>{children(user)}</>;
}
