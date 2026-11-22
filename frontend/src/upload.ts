import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, useApi } from "./api";

/** One upload flow shared by the run list and the start screen: upload, refresh the list, open the run. */
export function useUpload() {
  const api = useApi();
  const qc = useQueryClient();
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadRun(file),
    onSuccess: ({ id }) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      window.location.hash = `#/runs/${id}`;
    },
  });
  const serverError =
    upload.error instanceof ApiError
      ? upload.error.message
      : upload.error
        ? "Upload failed. Try again."
        : null;
  return {
    start: (f: File) => upload.mutate(f),
    busy: upload.isPending,
    serverError,
  };
}
