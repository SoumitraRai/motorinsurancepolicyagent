import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ApiContext, httpApi, type Api } from "./api";
import type { Auth } from "./auth";
import { History } from "./pages/History";
import { Home } from "./pages/Home";
import { RunPage } from "./pages/RunPage";
import { SignIn } from "./pages/SignIn";

/** Hash routes keep the backend's static serving simple: "#/" is the start screen, "#/runs/<id>" a run. */
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

// `api` is only passed by the local preview (src/preview.tsx); the real app talks to the backend.
export default function App({ auth, api: given }: { auth: Auth; api?: Api }) {
  const signedIn = useSignedIn(auth);
  const hash = useHashRoute();
  const api = useMemo(
    () => given ?? httpApi(() => auth.token()),
    [auth, given],
  );
  const queryClient = useMemo(() => new QueryClient(), []);
  const runId = /^#\/runs\/([\w-]+)$/.exec(hash)?.[1] ?? null;

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-10 focus:rounded focus:bg-sheet focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="border-b border-rule bg-sheet">
        <div className="mx-auto flex h-16 max-w-[90rem] items-center justify-between gap-4 px-4 sm:px-8">
          <h1 className="whitespace-nowrap text-lg font-bold tracking-tight sm:text-xl">
            <a href="#/" className="rounded-sm">
              Brokerage Rate Agent
            </a>
          </h1>
          {signedIn && (
            <div className="flex items-center gap-2 sm:gap-4">
              <a href="#/" className="btn-quiet">
                Upload
              </a>
              {auth.email() && (
                <span className="hidden text-sm text-ink-muted sm:inline">
                  {auth.email()}
                </span>
              )}
              <button
                type="button"
                onClick={async () => {
                  await auth.signOut();
                  queryClient.clear();
                }}
                className="btn-quiet"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      {signedIn === false && (
        <main
          id="main"
          className="flex flex-1 items-start justify-center px-4 py-16"
        >
          <SignIn signIn={(e, p) => auth.signIn(e, p)} />
        </main>
      )}
      {signedIn && (
        <QueryClientProvider client={queryClient}>
          <ApiContext.Provider value={api}>
            <div className="mx-auto grid w-full max-w-[90rem] flex-1 grid-cols-[minmax(0,1fr)] content-start lg:content-stretch lg:grid-cols-[22rem_minmax(0,1fr)]">
              <aside
                aria-label="Runs"
                className={`border-rule bg-sheet px-4 py-6 sm:px-8 lg:border-r lg:px-5 ${runId ? "max-lg:hidden" : "max-lg:order-2 max-lg:border-t"}`}
              >
                <History currentId={runId} showUpload={runId !== null} />
              </aside>
              <main id="main" className="min-w-0 px-4 py-8 sm:px-8 lg:px-12">
                {runId ? <RunPage runId={runId} /> : <Home />}
              </main>
            </div>
          </ApiContext.Provider>
        </QueryClientProvider>
      )}
    </div>
  );
}
