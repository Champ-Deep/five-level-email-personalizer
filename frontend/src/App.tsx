import { Navigate, Route, Routes } from "react-router-dom";
import { RedirectToSignIn, SignedIn, SignedOut } from "@clerk/clerk-react";

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

      {/* Legacy auth routes — bounce anyone landing on them to Clerk. */}
      <Route path="/login" element={<RedirectToSignIn />} />
      <Route path="/signup" element={<RedirectToSignIn />} />
      <Route path="/forgot-password" element={<RedirectToSignIn />} />
      <Route path="/reset-password" element={<RedirectToSignIn />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
