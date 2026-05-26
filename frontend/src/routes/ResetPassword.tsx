// Deprecated post-Clerk migration. Password resets are handled by Clerk.
import { Navigate } from "react-router-dom";

export function ResetPasswordRoute() {
  return <Navigate to="/" replace />;
}
