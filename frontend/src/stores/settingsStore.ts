import { create } from "zustand";
import { persist } from "zustand/middleware";
import { clearDirHandle, loadDirHandle, saveDirHandle } from "../lib/dirHandleStore";

export type ExportFormat = "png" | "txt" | "both";

// Sem {base} de proposito: o nome original do arquivo enviado costuma
// carregar o nome do paciente (ex: "laudo_joao_silva.pdf"), e reaproveitar
// isso no arquivo exportado vazaria justamente o dado que a anonimizacao
// deveria remover. {id} garante um nome sem PII mesmo sem o usuario mexer
// em nada.
export const DEFAULT_FILENAME_TEMPLATE = "anonimizado_{date}_{id}.{ext}";

interface SettingsState {
  defaultThreshold: number;
  defaultExportFormat: ExportFormat;
  filenameTemplate: string;
  outputDirName: string | null;
  // Suporte a File System Access API: so navegadores Chromium implementam
  // showDirectoryPicker hoje (Firefox/Safari nao). Calculado uma vez.
  fsAccessSupported: boolean;

  setDefaultThreshold: (v: number) => void;
  setDefaultExportFormat: (v: ExportFormat) => void;
  setFilenameTemplate: (v: string) => void;
  chooseOutputDir: () => Promise<void>;
  clearOutputDir: () => Promise<void>;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      defaultThreshold: 0.5,
      defaultExportFormat: "both",
      filenameTemplate: DEFAULT_FILENAME_TEMPLATE,
      outputDirName: null,
      fsAccessSupported: typeof window !== "undefined" && typeof window.showDirectoryPicker === "function",

      setDefaultThreshold: (v) => set({ defaultThreshold: v }),
      setDefaultExportFormat: (v) => set({ defaultExportFormat: v }),
      // Aceita vazio de proposito. Trocar "" pelo padrao aqui impedia o
      // usuario de limpar o campo para digitar outro template: a cada tecla
      // de apagar, o default voltava. O fallback vive em buildFilename, no
      // ponto de uso, onde ele realmente importa.
      setFilenameTemplate: (v) => set({ filenameTemplate: v }),

      chooseOutputDir: async () => {
        if (!window.showDirectoryPicker) return;
        const handle = await window.showDirectoryPicker({ mode: "readwrite" });
        await saveDirHandle(handle);
        set({ outputDirName: handle.name });
      },

      clearOutputDir: async () => {
        await clearDirHandle();
        set({ outputDirName: null });
      },
    }),
    {
      name: "xdiag-settings",
      // O handle real do FileSystemDirectoryHandle vive no IndexedDB
      // (dirHandleStore); aqui so persiste o nome, so para exibicao.
      partialize: (s) => ({
        defaultThreshold: s.defaultThreshold,
        defaultExportFormat: s.defaultExportFormat,
        filenameTemplate: s.filenameTemplate,
        outputDirName: s.outputDirName,
      }),
    },
  ),
);

function randomId(): string {
  return Math.random().toString(36).slice(2, 8);
}

// Resolve um nome de arquivo a partir do template configurado. `base` ja
// vem sem extensao (so existe para quem optar por usar {base} de proposito);
// `ext` e a extensao alvo do export (sem ponto). `id` e opcional so para a
// preview no painel de configuracoes conseguir mostrar um valor estavel; um
// export de verdade sempre gera um id novo.
export function buildFilename(template: string, base: string, ext: string, id: string = randomId()): string {
  const today = new Date().toISOString().slice(0, 10);
  const safeBase = base || "documento";
  // Template vazio cai no padrao: nunca exportar com nome vazio, e o padrao e
  // o unico que garante nome sem dado pessoal.
  const safeTemplate = template.trim() || DEFAULT_FILENAME_TEMPLATE;
  return safeTemplate
    .replace(/\{base\}/g, safeBase)
    .replace(/\{ext\}/g, ext)
    .replace(/\{date\}/g, today)
    .replace(/\{id\}/g, id);
}

// Confere se ainda existe permissao de escrita no diretorio salvo; se o
// handle nao estiver mais la (nunca escolhido, ou apagado), retorna null.
export async function getWritableOutputDir(): Promise<FileSystemDirectoryHandle | null> {
  const handle = await loadDirHandle();
  if (!handle) return null;
  const state = await handle.queryPermission({ mode: "readwrite" });
  if (state !== "granted") return null;
  return handle;
}
