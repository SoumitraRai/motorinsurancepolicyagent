import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ApiContext, httpApi } from "./api";
import type { Auth } from "./auth";
import { History } from "./pages/History";
import { RunPage } from "./pages/RunPage";
import { SignIn } from "./pages/SignIn";

/** Hash routes keep the backend's static serving simple: "#/" is History, "#/runs/<id>" is a run. */
function useHashRoute(): string {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

function useSignedIn(auth: Auth): boolean | null {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  useEffect(() => {
    const check = () => auth.token().then((t) => setSignedIn(t !== null));
    check();
    return auth.subscribe(check);
  }, [auth]);
  return signedIn;
}

export default function App({ auth }: { auth: Auth }) {
  const signedIn = useSignedIn(auth);
  const hash = useHashRoute();
  const api = useMemo(() => httpApi(() => auth.token()), [auth]);
  const queryClient = useMemo(() => new QueryClient(), []);
  const runId = /^#\/runs\/([\w-]+)$/.exec(hash)?.[1] ?? null;

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Brokerage Rate Agent</h1>
        {signedIn && (
          <button
            type="button"
            onClick={async () => {
              await auth.signOut();
              queryClient.clear();
            }}
            className="min-h-11 rounded border border-slate-300 px-3"
          >
            Sign out
          </button>
        )}
      </header>
      {signedIn === false && <SignIn signIn={(e, p) => auth.signIn(e, p)} />}
      {signedIn && (
        <QueryClientProvider client={queryClient}>
          <ApiContext.Provider value={api}>
            {runId ? <RunPage runId={runId} /> : <History />}
          </ApiContext.Provider>
        </QueryClientProvider>
      )}
    </main>
  );
}
