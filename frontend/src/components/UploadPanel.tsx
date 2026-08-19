import { useRef, useState, type ChangeEvent } from "react";
import { ApiError, uploadFiles } from "../api/client";
import type { FileEmbeddingItem } from "../types";

type UploadState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "result"; items: FileEmbeddingItem[] }
  | { kind: "error"; message: string };

function badgeClassFor(status: FileEmbeddingItem["status"]): string {
  return status === "success" ? "badge stored" : "badge error";
}

function badgeLabel(status: FileEmbeddingItem["status"]): string {
  return status === "success" ? "stored" : "failed";
}

export function UploadPanel(): JSX.Element {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [state, setState] = useState<UploadState>({ kind: "idle" });
  const [pending, setPending] = useState<File[]>([]);

  function onPick(event: ChangeEvent<HTMLInputElement>): void {
    const files = event.target.files ? Array.from(event.target.files) : [];
    setPending(files);
  }

  function openPicker(): void {
    inputRef.current?.click();
  }

  async function onSubmit(): Promise<void> {
    if (pending.length === 0) return;
    setState({ kind: "submitting" });
    try {
      const res = await uploadFiles(pending);
      setState({ kind: "result", items: res.data });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Upload failed";
      setState({ kind: "error", message });
    }
  }

  return (
    <section className="glass panel-card" role="tabpanel">
      <input
        ref={inputRef}
        type="file"
        multiple
        onChange={onPick}
        style={{ display: "none" }}
        accept=".pdf,.txt,.md,.png,.jpg,.jpeg,application/pdf,text/plain,text/markdown,image/png,image/jpeg"
      />

      <button
        type="button"
        className="drop"
        onClick={openPicker}
        aria-label="Choose files"
      >
        <strong>Click to browse</strong> or drop files here
        <div className="meta">PDF, TXT, MD, PNG, JPG · up to 10 files</div>
      </button>

      <div className="actions">
        <span className="meta">
          {pending.length} file{pending.length === 1 ? "" : "s"} selected
        </span>
        <button
          className="primary"
          type="button"
          onClick={onSubmit}
          disabled={state.kind === "submitting" || pending.length === 0}
        >
          Upload &amp; embed
        </button>
      </div>

      {state.kind === "error" && (
        <div className="banner" role="alert">
          {state.message}
        </div>
      )}

      {state.kind === "result" && (
        <div className="results">
          <h3>Results</h3>
          <ul className="list">
            {state.items.map((item, index) => (
              <li key={`${item.filename}-${index}`}>
                <div className="row-line">
                  <span className="fname">{item.filename}</span>
                  <span className={badgeClassFor(item.status)}>
                    {badgeLabel(item.status)}
                  </span>
                </div>
                <div className="meta-row">
                  {item.content_type}
                  {item.reason ? ` · ${item.reason}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
