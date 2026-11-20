import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UploadDrop } from "./UploadDrop";

function file(name: string, type: string, bytes: number): File {
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, "size", { value: bytes });
  return f;
}

test("rejects a non-PDF inline and does not upload", async () => {
  const onUpload = vi.fn();
  render(<UploadDrop onUpload={onUpload} busy={false} />);
  await userEvent.upload(screen.getByLabelText(/policy pdf/i), file("notes.txt", "text/plain", 10), {
    applyAccept: false,
  });
  expect(screen.getByRole("alert")).toHaveTextContent("Upload a PDF file");
  expect(onUpload).not.toHaveBeenCalled();
});

test("rejects a PDF over 25 MB inline", async () => {
  const onUpload = vi.fn();
  render(<UploadDrop onUpload={onUpload} busy={false} />);
  await userEvent.upload(
    screen.getByLabelText(/policy pdf/i),
    file("big.pdf", "application/pdf", 25 * 1024 * 1024 + 1),
  );
  expect(screen.getByRole("alert")).toHaveTextContent("over 25 MB");
  expect(onUpload).not.toHaveBeenCalled();
});

test("uploads a valid PDF", async () => {
  const onUpload = vi.fn();
  render(<UploadDrop onUpload={onUpload} busy={false} />);
  const pdf = file("policy.pdf", "application/pdf", 1000);
  await userEvent.upload(screen.getByLabelText(/policy pdf/i), pdf);
  expect(onUpload).toHaveBeenCalledWith(pdf);
  expect(screen.queryByRole("alert")).toBeNull();
});
