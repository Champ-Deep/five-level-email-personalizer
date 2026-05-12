import { Navigate, Route, Routes } from "react-router-dom";

import { InternalAppRoute } from "./routes/InternalApp";
import { LeadMagnetRoute } from "./routes/LeadMagnet";
import { LoginRoute } from "./routes/Login";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/lead-magnet/lakeb2b" replace />} />
      <Route path="/lead-magnet/:brand" element={<LeadMagnetRoute />} />
      <Route path="/lead-magnet" element={<Navigate to="/lead-magnet/lakeb2b" replace />} />
      <Route path="/app" element={<InternalAppRoute />} />
      <Route path="/login" element={<LoginRoute />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
