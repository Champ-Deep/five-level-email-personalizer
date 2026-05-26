import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ClerkProvider } from "@clerk/clerk-react";

import App from "./App";
import { AuthSync } from "./components/AuthSync";
import "./styles/tokens.css";

const PUBLISHABLE_KEY = (import.meta as any).env?.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

if (!PUBLISHABLE_KEY) {
  // Failing loudly here is the right call: a silently-missing key
  // gets Clerk to render an unhelpful "Missing publishable key" toast
  // and breaks every page in non-obvious ways. The console message
  // tells the next dev exactly what's wrong.
  throw new Error(
    "Missing VITE_CLERK_PUBLISHABLE_KEY. Set it in frontend/.env.local " +
    "(see .env.example) and rebuild.",
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
      <BrowserRouter>
        <AuthSync>
          <App />
        </AuthSync>
      </BrowserRouter>
    </ClerkProvider>
  </React.StrictMode>,
);
