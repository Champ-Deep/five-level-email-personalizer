// Deprecated post-Clerk migration. Kept as a thin redirect so any old
// bookmarks land on the Clerk-managed sign-in flow on the home page.
import { Navigate } from "react-router-dom";

export function LoginRoute() {
  return <Navigate to="/" replace />;
}
