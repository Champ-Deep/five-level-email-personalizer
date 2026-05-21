import { Navigate, Route, Routes } from "react-router-dom";

import { ApiKeysRoute } from "./routes/ApiKeys";
import { ForgotPasswordRoute } from "./routes/ForgotPassword";
import { HistoryRoute } from "./routes/History";
import { IcpProfilesRoute } from "./routes/IcpProfiles";
import { IntegrationsRoute } from "./routes/Integrations";
import { InternalAppRoute } from "./routes/InternalApp";
import { LeadMagnetRoute } from "./routes/LeadMagnet";
import { LoginRoute } from "./routes/Login";
import { RepliesRoute } from "./routes/Replies";
import { ResetPasswordRoute } from "./routes/ResetPassword";
import { SendersRoute } from "./routes/Senders";
import { SettingsRoute } from "./routes/Settings";
import { SignupRoute } from "./routes/Signup";
import { SuppressionsRoute } from "./routes/Suppressions";
import { WebhooksRoute } from "./routes/Webhooks";

// SPAN Global Services branch. Backend LOCKED_BRAND=span-global enforces this server-side too.
const BRAND_SLUG = "span-global";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to={`/lead-magnet/${BRAND_SLUG}`} replace />} />
      <Route path="/lead-magnet" element={<Navigate to={`/lead-magnet/${BRAND_SLUG}`} replace />} />
      <Route path="/lead-magnet/:brand" element={<LeadMagnetRoute />} />

      <Route path="/app" element={<InternalAppRoute />} />
      <Route path="/app/history" element={<HistoryRoute />} />
      <Route path="/app/senders" element={<SendersRoute />} />
      <Route path="/app/icp" element={<IcpProfilesRoute />} />
      <Route path="/app/suppressions" element={<SuppressionsRoute />} />
      <Route path="/app/replies" element={<RepliesRoute />} />
      <Route path="/app/integrations" element={<IntegrationsRoute />} />
      <Route path="/app/api-keys" element={<ApiKeysRoute />} />
      <Route path="/app/webhooks" element={<WebhooksRoute />} />
      <Route path="/app/settings" element={<SettingsRoute />} />

      <Route path="/login" element={<LoginRoute />} />
      <Route path="/signup" element={<SignupRoute />} />
      <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
      <Route path="/reset-password" element={<ResetPasswordRoute />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
