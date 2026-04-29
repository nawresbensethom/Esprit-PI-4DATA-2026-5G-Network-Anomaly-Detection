import { redirect } from "next/navigation";

export default function HomePage() {
  // RoleGate on /dashboard handles the anonymous → /login bounce.
  redirect("/dashboard");
}