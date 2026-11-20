import { createClient, type Session } from "@supabase/supabase-js";

/** The app's view of authentication; Supabase in the browser, a fake in tests. */
export interface Auth {
  token(): Promise<string | null>;
  email(): string | null;
  signIn(email: string, password: string): Promise<void>;
  signOut(): Promise<void>;
  /** Calls `cb` whenever the session changes; returns an unsubscribe function. */
  subscribe(cb: () => void): () => void;
}

export function supabaseAuth(url: string, anonKey: string): Auth {
  const client = createClient(url, anonKey, {
    auth: { persistSession: true, autoRefreshToken: true },
  });
  let session: Session | null = null;
  const ready = client.auth.getSession().then(({ data }) => {
    session = data.session;
  });
  return {
    async token() {
      await ready;
      const { data } = await client.auth.getSession();
      session = data.session;
      return session?.access_token ?? null;
    },
    email: () => session?.user.email ?? null,
    async signIn(email, password) {
      const { data, error } = await client.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
      session = data.session;
    },
    async signOut() {
      await client.auth.signOut();
      session = null;
    },
    subscribe(cb) {
      const { data } = client.auth.onAuthStateChange((_event, s) => {
        session = s;
        cb();
      });
      ready.then(cb);
      return () => data.subscription.unsubscribe();
    },
  };
}
