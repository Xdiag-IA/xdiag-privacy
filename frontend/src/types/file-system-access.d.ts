// A lib.dom.d.ts do TypeScript ainda nao cobre toda a File System Access API
// (so Chromium implementa). Declaracoes minimas para o que o app usa.
export {};

type FSPermissionMode = "read" | "readwrite";
type FSPermissionState = "granted" | "denied" | "prompt";

declare global {
  interface FileSystemHandle {
    queryPermission(options?: { mode?: FSPermissionMode }): Promise<FSPermissionState>;
    requestPermission(options?: { mode?: FSPermissionMode }): Promise<FSPermissionState>;
  }

  interface Window {
    showDirectoryPicker?(options?: { mode?: FSPermissionMode }): Promise<FileSystemDirectoryHandle>;
  }
}
