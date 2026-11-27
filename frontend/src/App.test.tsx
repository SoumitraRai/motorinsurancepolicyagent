import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import type { Api } from "./api";
import type { Auth } from "./auth";

function fakeAuth(signedIn: boolean): Auth {
  return {
    token: async () => (signedIn ? "t" : null),
    email: () => (signedIn ? "reviewer@example.com" : null),
    signIn: vi.fn(),
    signOut: vi.fn(),
    subscribe: () => () => {},
  };
}

function switchableAuth(): Auth {
  let signedIn = true;
  const listeners = new Set<() => void>();
  const notify = () => listeners.forEach((listener) => listener());
  return {
    token: async () => (signedIn ? "t" : null),
    email: () => (signedIn ? "reviewer@example.com" : null),
    signIn: async () => {
      signedIn = true;
      notify();
    },
    signOut: async () => {
      signedIn = false;
      notify();
    },
    subscribe: (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
  };
}

test("renders the product name and the sign-in form when signed out", async () => {
  render(<App auth={fakeAuth(false)} />);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Brokerage Rate Agent",
  );
  expect(
    await screen.findByRole("button", { name: "Sign in" }),
  ).toBeInTheDocument();
});

test("switching accounts returns to the new account's history", async () => {
  window.location.hash = "#/runs/previous-account-run";
  const auth = switchableAuth();
  const getRun = vi.fn(async () => {
    throw new Error("Run not found");
  });
  const api: Api = {
    listRuns: vi.fn(async () => ({ items: [], nextCursor: null })),
    getRun,
    uploadRun: vi.fn(),
    retryRun: vi.fn(),
    clarifyRun: vi.fn(),
    pdfUrl: vi.fn(),
  };
  render(<App auth={auth} api={api} />);

  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  await userEvent.type(await screen.findByLabelText("Email"), "careers@vaatun.com");
  await userEvent.type(screen.getByLabelText("Password"), "password");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(
    await screen.findByText(/No policies yet for this account/),
  ).toBeInTheDocument();
  await waitFor(() => expect(window.location.hash).toBe("#/"));
  expect(getRun).toHaveBeenCalledWith("previous-account-run");
});

test("shows sign out and history when signed in", async () => {
  render(<App auth={fakeAuth(true)} />);
  expect(
    await screen.findByRole("button", { name: "Sign out" }),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { name: "History" }),
  ).toBeInTheDocument();
});
