import { render, screen } from "@testing-library/react";
import App from "./App";
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

test("renders the product name and the sign-in form when signed out", async () => {
  render(<App auth={fakeAuth(false)} />);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Brokerage Rate Agent",
  );
  expect(
    await screen.findByRole("button", { name: "Sign in" }),
  ).toBeInTheDocument();
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
