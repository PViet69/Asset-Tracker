/// <reference types="vite/client" />

// Non-standard but widely supported: relative path when files are picked via
// <input webkitdirectory>. Empty string otherwise.
interface File {
  readonly webkitRelativePath?: string;
}

// Non-standard but widely supported: relative path when files are picked via
// <input webkitdirectory>. Empty string otherwise.
interface File {
  readonly webkitRelativePath?: string;
}
