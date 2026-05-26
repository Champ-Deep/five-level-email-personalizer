import { Navigate, Route, Routes } from "react-router-dom";
import { RedirectToSignIn, SignedIn, SignedOut, SignIn, SignUp } from "@clerk/clerk-react";

import { ApiKeysRoute } from "./routes/ApiKeys";
import { HistoryRoute } from "./routes/History";
import { IcpProfilesRoute } from "./routes/IcpProfiles";
import { IntegrationsRoute } from "./routes/Integrations";
import { InternalAppRoute } from "./routes/InternalApp";
import { LeadMagnetRoute } from "./routes/LeadMagnet";
import { RepliesRoute } from "./routes/Replies";
import { SendersRoute } from "./routes/Senders";
import { SettingsRoute } from "./routes/Settings";
import { SuppressionsRoute } from "./routes/Suppressions";
import { WebhooksRoute } from "./routes/Webhooks";

/** Wraps a route in Clerk's auth gate. Signed-out visitors are bounced
 *  to Clerk's hosted sign-in (the Account portal). Sign-in/up live in
 *  the modal on the header for in-app starts, but a deep link straight
 *  to a /app/* URL still works because RedirectToSignIn captures the
 *  current path and returns the user there post-auth. */
function Protected({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SignedIn>{children}</SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/lead-magnet/lakeb2b" replace />} />
      <Route path="/lead-magnet/:brand" element={<LeadMagnetRoute />} />
      <Route path="/lead-magnet" element={<Navigate to="/lead-magnet/lakeb2b" replace />} />

      <Route path="/app" element={<Protected><InternalAppRoute /></Protected>} />
      <Route path="/app/history" element={<Protected><HistoryRoute /></Protected>} />
      <Route path="/app/senders" element={<Protected><SendersRoute /></Protected>} />
      <Route path="/app/icp" element={<Protected><IcpProfilesRoute /></Protected>} />
      <Route path="/app/suppressions" element={<Protected><SuppressionsRoute /></Protected>} />
      <Route path="/app/replies" element={<Protected><RepliesRoute /></Protected>} />
      <Route path="/app/integrations" element={<Protected><IntegrationsRoute /></Protected>} />
      <Route path="/app/api-keys" element={<Protected><ApiKeysRoute /></Protected>} />
      <Route path="/app/webhooks" element={<Protected><WebhooksRoute /></Protected>} />
      <Route path="/app/settings" element={<Protected><SettingsRoute /></Protected>} />

      {/* Clerk-mounted auth surfaces. `routing="path"` makes Clerk own
          the URL — every method enabled in the Clerk dashboard (email,
          password, Google, magic link, phone, 2FA, etc.) renders here
          with zero extra code. Path-based instead of modal so the page
          can carry the brand chrome and survive deep links / refreshes. */}
      <Route path="/login/*" element={
        <SignedOut>
          <ClerkPage>
            <SignIn routing="path" path="/login" signUpUrl="/signup" fallbackRedirectUrl="/app" />
          </ClerkPage>
        </SignedOut>
      } />
      <Route path="/signup/*" element={
        <SignedOut>
          <ClerkPage>
            <SignUp routing="path" path="/signup" signInUrl="/login" fallbackRedirectUrl="/app" />
          </ClerkPage>
        </SignedOut>
      } />

      {/* Already-signed-in users hitting /login or /signup bounce into the app. */}
      <Route path="/login/signed-in" element={<Navigate to="/app" replace />} />

      {/* Legacy reset-password routes — Clerk owns the flow now. */}
      <Route path="/forgot-password" element={<Navigate to="/login" replace />} />
      <Route path="/reset-password" element={<Navigate to="/login" replace />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

/** Centers Clerk's <SignIn>/<SignUp> on the page with brand tokens applied. */
function ClerkPage({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="grid min-h-screen place-items-center px-4"
      style={{ background: "var(--brand-bg, #ffffff)" }}
    >
      {children}
    </div>
  );
}
