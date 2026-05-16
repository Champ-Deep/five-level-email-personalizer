import { Navigate, Route, Routes } from "react-router-dom";

import { ApiKeysRoute } from "./routes/ApiKeys";
import { HistoryRoute } from "./routes/History";
import { InternalAppRoute } from "./routes/InternalApp";
import { LeadMagnetRoute } from "./routes/LeadMagnet";
import { LoginRoute } from "./routes/Login";
import { SendersRoute } from "./routes/Senders";
import { SettingsRoute } from "./routes/Settings";
import { SignupRoute } from "./routes/Signup";
import { WebhooksRoute } from "./routes/Webhooks";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/lead-magnet/lakeb2b" replace />} />
      <Route path="/lead-magnet/:brand" element={<LeadMagnetRoute />} />
      <Route path="/lead-magnet" element={<Navigate to="/lead-magnet/lakeb2b" replace />} />

      <Route path="/app" element={<InternalAppRoute />} />
      <Route path="/app/history" element={<HistoryRoute />} />
      <Route path="/app/senders" element={<SendersRoute />} />
      <Route path="/app/api-keys" element={<ApiKeysRoute />} />
      <Route path="/app/webhooks" element={<WebhooksRoute />} />
      <Route path="/app/settings" element={<SettingsRoute />} />

      <Route path="/login" element={<LoginRoute />} />
      <Route path="/signup" element={<SignupRoute />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
