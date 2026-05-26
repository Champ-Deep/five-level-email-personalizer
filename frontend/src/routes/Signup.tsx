// Deprecated post-Clerk migration. Kept as a thin redirect.
import { Navigate } from "react-router-dom";

export function SignupRoute() {
  return <Navigate to="/" replace />;
}
