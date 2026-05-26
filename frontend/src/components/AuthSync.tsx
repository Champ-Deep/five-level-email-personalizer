import { useEffect } from "react";
import { useAuth } from "@clerk/clerk-react";
import { setClerkTokenGetter } from "@/lib/api";

/**
 * Bridges Clerk's React-hook-only `useAuth().getToken()` into the plain-JS
 * `api` module. Mount once near the top of the tree (inside `<ClerkProvider>`)
 * and every `request()` call elsewhere will pick up a fresh session token
 * automatically — no prop drilling, no `useAuth()` repeated in 20 hooks.
 *
 * `getToken` is stable per Clerk session, but we keep this effect cheap so
 * StrictMode's double-invoke in dev doesn't cause grief.
 */
export function AuthSync({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded } = useAuth();

  useEffect(() => {
    if (!isLoaded) return;
    setClerkTokenGetter(() => getToken());
    return () => setClerkTokenGetter(null);
  }, [getToken, isLoaded]);

  return <>{children}</>;
}
