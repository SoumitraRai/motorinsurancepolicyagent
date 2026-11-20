import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SignIn } from "./SignIn";

test("signs in with visible labels and shows an inline error on failure", async () => {
  const signIn = vi
    .fn()
    .mockRejectedValueOnce(new Error("bad"))
    .mockResolvedValueOnce(undefined);
  render(<SignIn signIn={signIn} />);
  await userEvent.type(screen.getByLabelText("Email"), "reviewer@example.com");
  await userEvent.type(screen.getByLabelText("Password"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Email or password is wrong. Try again.",
  );
  expect(screen.getByLabelText("Email")).toHaveValue("reviewer@example.com"); // input preserved
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(signIn).toHaveBeenLastCalledWith("reviewer@example.com", "wrong");
});
