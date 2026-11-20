import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { supabaseAuth } from "./auth";
import "./index.css";

// Public values only (the anon key is designed to be shipped to browsers); set at build time.
const auth = supabaseAuth(
  import.meta.env.VITE_SUPABASE_URL ?? "",
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? "",
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App auth={auth} />
  </StrictMode>,
);
