import { create } from "zustand";
import { postRedact } from "../api/client";
import type { BBox, Entity, OCRBlock, PageResult, RedactResponse } from "../api/types";
import { useSettingsStore } from "./settingsStore";

// Regiao marcada manualmente pelo usuario (falso negativo do modelo): o
// OCR/PII nao detectou nada ali, entao nao existe char_span nem score, so
// um retangulo em coordenadas de pixel da pagina.
export interface ManualBox {
  id: string;
  bbox: BBox;
  label: string;
}

export type Status =
  | "idle"
  | "uploading"
  | "processing"
  | "animating"
  | "done"
  | "error";

export type DocStatus = "queued" | "processing" | "done" | "error";

// Um documento da sessao (menu principal). Guarda o resultado completo para
// que trocar de documento nao exija reprocessar nem perca o historico.
export interface DocEntry {
  id: string;
  file: File;
  fileName: string;
  isSynthetic: boolean;
  status: DocStatus;
  error: string | null;
  pages: PageResult[];
  elapsedMs: number;
  threshold: number;
  // Correcoes manuais (indices marcados como "nao anonimizar") por pagina.
  // Sobrevive a troca de documento/pagina; e descartada quando o documento
  // e reprocessado (novo threshold muda os indices detectados).
  excludedByPage: Map<number, Set<number>>;
  // Areas desenhadas manualmente (falso negativo) por pagina. Sobrevive a
  // reprocessamento: a imagem da pagina nao muda com o threshold, so as
  // deteccoes do modelo, entao as coordenadas continuam validas.
  manualByPage: Map<number, ManualBox[]>;
}

interface RedactionState {
  // sessao: todos os documentos ja adicionados (fila + concluidos)
  documents: DocEntry[];
  activeDocId: string | null;

  // input
  file: File | null;
  fileName: string;
  isSynthetic: boolean;
  imageUrl: string | null;

  // results (documento completo)
  pages: PageResult[];
  currentPage: number;

  // visao da pagina ativa (espelho de pages[currentPage], para os
  // componentes nao mudarem de shape)
  imageDimensions: { w: number; h: number } | null;
  ocrBlocks: OCRBlock[];
  entities: Entity[]; // sorted by visual position (top to bottom)
  deidentifiedText: string;
  originalText: string | null;
  elapsedMs: number;

  // animation
  visibleCount: number;
  currentLabel: string | null;

  // ui
  showOriginalText: boolean;
  threshold: number;
  hoveredEntityIndex: number | null;
  selectedEntityIndex: number | null;
  // Correcao manual: indices (na pagina ativa) que o usuario marcou para NAO
  // ser anonimizados, mesmo tendo sido detectados pelo modelo (falso
  // positivo). Espelha DocEntry.excludedByPage do documento ativo; persiste
  // ao trocar de documento/pagina e ao voltar, e so e descartada quando o
  // documento e reprocessado (os indices deixam de corresponder).
  excludedEntityIndices: Set<number>;

  // Areas adicionadas manualmente na pagina ativa (falso negativo do
  // modelo). Espelha DocEntry.manualByPage; ao contrario das exclusoes,
  // sobrevive a reprocessamento.
  manualBoxes: ManualBox[];
  drawMode: boolean;

  // lifecycle
  status: Status;
  error: string | null;

  // actions
  addFiles: (files: File[], opts?: { isSynthetic?: boolean }) => void;
  selectDocument: (id: string) => void;
  reprocessActive: (opts?: { reveal?: boolean }) => Promise<void>;
  reset: () => void;
  setPage: (index: number) => void;
  setShowOriginal: (v: boolean) => void;
  setThreshold: (v: number) => void;
  setHoveredEntity: (i: number | null) => void;
  setSelectedEntity: (i: number | null) => void;
  toggleEntityExcluded: (i: number) => void;
  setDrawMode: (v: boolean) => void;
  addManualBox: (bbox: BBox, label?: string) => void;
  removeManualBox: (id: string) => void;
  // animation control (driven by ProgressTracker)
  bumpVisible: () => void;
  finishAnimation: () => void;
}

const SYNTHETIC_HINTS = ["sample", "synthetic", "laudo_us_obstetrico", "ficha_admissao", "prescricao_medica"];

function looksSynthetic(name: string): boolean {
  const lower = name.toLowerCase();
  return SYNTHETIC_HINTS.some((h) => lower.includes(h));
}

function sortByPosition(entities: Entity[]): Entity[] {
  return [...entities].sort((a, b) => {
    // Entidades sem bbox vao para o FIM da lista; a animacao percorre so
    // as mapeadas e a secao "nao mapeadas" da UI as exibe em separado.
    const ay = a.unmapped ? Infinity : a.bboxes[0]?.[0]?.[1] ?? 0;
    const by = b.unmapped ? Infinity : b.bboxes[0]?.[0]?.[1] ?? 0;
    if (ay === Infinity && by === Infinity) return 0;
    if (Math.abs(ay - by) > 6) return ay - by;
    const ax = a.bboxes[0]?.[0]?.[0] ?? 0;
    const bx = b.bboxes[0]?.[0]?.[0] ?? 0;
    return ax - bx;
  });
}

export function mappedCount(entities: Entity[]): number {
  return entities.filter((e) => !e.unmapped).length;
}

export function unmappedCount(entities: Entity[]): number {
  return entities.filter((e) => e.unmapped).length;
}

// Contagem global de nao mapeadas: o bloqueio de export considera TODAS as
// paginas, nao apenas a exibida.
export function unmappedCountAll(pages: PageResult[]): number {
  return pages.reduce((acc, p) => acc + unmappedCount(p.entities), 0);
}

export function fullDeidentifiedText(pages: PageResult[]): string {
  if (pages.length === 1) return pages[0]?.deidentified_text ?? "";
  return pages
    .map((p, i) => `--- página ${i + 1} ---\n${p.deidentified_text}`)
    .join("\n\n");
}

const initial = {
  file: null,
  fileName: "",
  isSynthetic: false,
  imageUrl: null,
  pages: [] as PageResult[],
  currentPage: 0,
  imageDimensions: null,
  ocrBlocks: [] as OCRBlock[],
  entities: [] as Entity[],
  deidentifiedText: "",
  originalText: null as string | null,
  elapsedMs: 0,
  visibleCount: 0,
  currentLabel: null as string | null,
  showOriginalText: false,
  threshold: useSettingsStore.getState().defaultThreshold,
  hoveredEntityIndex: null as number | null,
  selectedEntityIndex: null as number | null,
  manualBoxes: [] as ManualBox[],
  drawMode: false,
  status: "idle" as Status,
  error: null as string | null,
};

function emptyExclusions(): Set<number> {
  return new Set<number>();
}

function newDocId(): string {
  return `doc-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export const useRedactionStore = create<RedactionState>((set, get) => {
  // Processa a fila sequencialmente (um documento por vez, o backend roda
  // OCR + PII num unico worker CPU). Atualiza sempre a entrada em
  // `documents`; so espelha nos campos "planos" (a visao ativa) se o
  // documento ainda for o ativo quando a resposta chegar.
  function updateDoc(id: string, patch: Partial<DocEntry>) {
    set((s) => ({
      documents: s.documents.map((d) => (d.id === id ? { ...d, ...patch } : d)),
    }));
  }

  async function processDoc(id: string) {
    const doc = get().documents.find((d) => d.id === id);
    if (!doc) return;
    const isActive = () => get().activeDocId === id;

    updateDoc(id, { status: "processing", error: null });
    if (isActive()) set({ status: "processing", error: null });

    try {
      const result: RedactResponse = await postRedact(doc.file, {
        threshold: doc.threshold,
        reveal: false,
        isSynthetic: doc.isSynthetic,
      });
      const pages = result.pages.map((p) => ({
        ...p,
        entities: sortByPosition(p.entities),
      }));
      updateDoc(id, {
        status: "done",
        pages,
        elapsedMs: result.elapsed_ms,
        excludedByPage: new Map<number, Set<number>>(),
      });

      if (isActive()) {
        const first = pages[0];
        const firstMapped = first ? mappedCount(first.entities) : 0;
        const prevUrl = get().imageUrl;
        if (prevUrl) URL.revokeObjectURL(prevUrl);
        set({
          pages,
          currentPage: 0,
          imageUrl: first?.rendered_image_data_url || null,
          imageDimensions: first?.image_dimensions ?? null,
          ocrBlocks: first?.ocr_blocks ?? [],
          entities: first?.entities ?? [],
          deidentifiedText: first?.deidentified_text ?? "",
          originalText: first?.original_text ?? null,
          elapsedMs: result.elapsed_ms,
          status: firstMapped > 0 ? "animating" : "done",
          visibleCount: 0,
          currentLabel: null,
          excludedEntityIndices: emptyExclusions(),
        });
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "erro desconhecido";
      updateDoc(id, { status: "error", error: message });
      if (isActive()) set({ status: "error", error: message });
    }
  }

  let queueRunning = false;
  async function runQueue() {
    if (queueRunning) return;
    queueRunning = true;
    try {
      for (;;) {
        const next = get().documents.find((d) => d.status === "queued");
        if (!next) break;
        await processDoc(next.id);
      }
    } finally {
      queueRunning = false;
    }
  }

  return {
    ...initial,
    documents: [] as DocEntry[],
    activeDocId: null as string | null,
    excludedEntityIndices: emptyExclusions(),

    reset: () => {
      // Volta ao menu principal (tela de upload) SEM apagar o historico da
      // sessao: os documentos ja processados continuam acessiveis no menu.
      const { imageUrl } = get();
      if (imageUrl) URL.revokeObjectURL(imageUrl);
      set({ ...initial, activeDocId: null, excludedEntityIndices: emptyExclusions() });
    },

    addFiles: (files, opts) => {
      if (!files.length) return;
      const entries: DocEntry[] = files.map((file) => ({
        id: newDocId(),
        file,
        fileName: file.name,
        isSynthetic: opts?.isSynthetic ?? looksSynthetic(file.name),
        status: "queued",
        error: null,
        pages: [],
        elapsedMs: 0,
        threshold: get().threshold,
        excludedByPage: new Map<number, Set<number>>(),
        manualByPage: new Map<number, ManualBox[]>(),
      }));
      set((s) => ({ documents: [...s.documents, ...entries] }));
      // O primeiro arquivo adicionado assume a tela principal na hora; os
      // demais (lote / anonimizacao por blocos) processam em segundo plano
      // e aparecem no menu de documentos conforme terminam.
      if (!get().activeDocId) {
        get().selectDocument(entries[0].id);
      }
      void runQueue();
    },

    selectDocument: (id) => {
      const doc = get().documents.find((d) => d.id === id);
      if (!doc) return;
      const prevUrl = get().imageUrl;
      if (prevUrl && prevUrl.startsWith("blob:")) URL.revokeObjectURL(prevUrl);
      const first = doc.pages[0];
      // Enquanto o resultado do servidor nao chega, mostra uma previa local
      // do arquivo (mesma logica do upload antigo) para o spinner de
      // "processando" nao aparecer sobre uma tela vazia.
      const previewUrl = first?.rendered_image_data_url || URL.createObjectURL(doc.file);
      const flatStatus: Status =
        doc.status === "queued"
          ? "uploading"
          : doc.status === "processing"
            ? "processing"
            : doc.status === "error"
              ? "error"
              : "done";
      set({
        activeDocId: id,
        file: doc.file,
        fileName: doc.fileName,
        isSynthetic: doc.isSynthetic,
        threshold: doc.threshold,
        pages: doc.pages,
        currentPage: 0,
        imageUrl: previewUrl,
        imageDimensions: first?.image_dimensions ?? null,
        ocrBlocks: first?.ocr_blocks ?? [],
        entities: first?.entities ?? [],
        deidentifiedText: first?.deidentified_text ?? "",
        originalText: null,
        elapsedMs: doc.elapsedMs,
        // Documento ja concluido: mostra tudo de uma vez, sem reanimar.
        visibleCount: first ? mappedCount(first.entities) : 0,
        currentLabel: null,
        showOriginalText: false,
        status: flatStatus,
        error: doc.error,
        hoveredEntityIndex: null,
        selectedEntityIndex: null,
        excludedEntityIndices: new Set(doc.excludedByPage.get(0) ?? emptyExclusions()),
        manualBoxes: doc.manualByPage.get(0) ?? [],
        drawMode: false,
      });
    },

    reprocessActive: async (opts) => {
      const { file, activeDocId, threshold, isSynthetic } = get();
      if (!file) return;
      const reveal = opts?.reveal ?? get().showOriginalText;
      set({ status: "processing", error: null });
      try {
        const result: RedactResponse = await postRedact(file, {
          threshold,
          reveal,
          isSynthetic,
        });
        const pages = result.pages.map((p) => ({
          ...p,
          entities: sortByPosition(p.entities),
        }));
        const first = pages[0];
        const firstMapped = first ? mappedCount(first.entities) : 0;
        const prevUrl = get().imageUrl;
        if (prevUrl) URL.revokeObjectURL(prevUrl);
        set({
          pages,
          currentPage: 0,
          imageUrl: first?.rendered_image_data_url || null,
          imageDimensions: first?.image_dimensions ?? null,
          ocrBlocks: first?.ocr_blocks ?? [],
          entities: first?.entities ?? [],
          deidentifiedText: first?.deidentified_text ?? "",
          originalText: first?.original_text ?? null,
          elapsedMs: result.elapsed_ms,
          status: firstMapped > 0 ? "animating" : "done",
          visibleCount: 0,
          currentLabel: null,
          excludedEntityIndices: emptyExclusions(),
        });
        if (activeDocId) {
          updateDoc(activeDocId, {
            pages,
            elapsedMs: result.elapsed_ms,
            threshold,
            status: "done",
            error: null,
            excludedByPage: new Map<number, Set<number>>(),
          });
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "erro desconhecido";
        set({ status: "error", error: message });
        if (activeDocId) updateDoc(activeDocId, { status: "error", error: message });
      }
    },

    setPage: (index: number) => {
      const { pages, activeDocId, documents } = get();
      if (index < 0 || index >= pages.length) return;
      const page = pages[index];
      const activeDoc = documents.find((d) => d.id === activeDocId);
      // Troca de pagina nao re-anima: mostra todas as entidades mapeadas.
      set({
        currentPage: index,
        imageUrl: page.rendered_image_data_url || null,
        imageDimensions: page.image_dimensions,
        ocrBlocks: page.ocr_blocks,
        entities: page.entities,
        deidentifiedText: page.deidentified_text,
        originalText: page.original_text ?? null,
        visibleCount: mappedCount(page.entities),
        currentLabel: null,
        status: "done",
        hoveredEntityIndex: null,
        selectedEntityIndex: null,
        excludedEntityIndices: new Set(activeDoc?.excludedByPage.get(index) ?? emptyExclusions()),
        manualBoxes: activeDoc?.manualByPage.get(index) ?? [],
      });
    },

    setShowOriginal: (v: boolean) => set({ showOriginalText: v }),
    setThreshold: (v: number) => set({ threshold: v }),
    setHoveredEntity: (i: number | null) => set({ hoveredEntityIndex: i }),
    setSelectedEntity: (i: number | null) => set({ selectedEntityIndex: i }),
    toggleEntityExcluded: (i: number) => {
      set((s) => {
        const next = new Set(s.excludedEntityIndices);
        if (next.has(i)) next.delete(i);
        else next.add(i);
        return { excludedEntityIndices: next };
      });
      // Persiste na entrada do documento (pagina atual) para sobreviver a
      // troca de documento/pagina pelo menu.
      const { activeDocId, currentPage } = get();
      if (!activeDocId) return;
      updateDoc(activeDocId, {
        excludedByPage: (() => {
          const doc = get().documents.find((d) => d.id === activeDocId);
          const map = new Map(doc?.excludedByPage ?? []);
          map.set(currentPage, new Set(get().excludedEntityIndices));
          return map;
        })(),
      });
    },

    setDrawMode: (v: boolean) => set({ drawMode: v }),

    addManualBox: (bbox: BBox, label = "MANUAL") => {
      const box: ManualBox = { id: `manual-${Math.random().toString(36).slice(2, 9)}`, bbox, label };
      set((s) => ({ manualBoxes: [...s.manualBoxes, box] }));
      const { activeDocId, currentPage } = get();
      if (!activeDocId) return;
      const doc = get().documents.find((d) => d.id === activeDocId);
      const map = new Map(doc?.manualByPage ?? []);
      map.set(currentPage, get().manualBoxes);
      updateDoc(activeDocId, { manualByPage: map });
    },

    removeManualBox: (id: string) => {
      set((s) => ({ manualBoxes: s.manualBoxes.filter((b) => b.id !== id) }));
      const { activeDocId, currentPage } = get();
      if (!activeDocId) return;
      const doc = get().documents.find((d) => d.id === activeDocId);
      const map = new Map(doc?.manualByPage ?? []);
      map.set(currentPage, get().manualBoxes);
      updateDoc(activeDocId, { manualByPage: map });
    },

    bumpVisible: () => {
      const { visibleCount, entities } = get();
      const next = Math.min(visibleCount + 1, mappedCount(entities));
      const currentLabel = next > 0 ? entities[next - 1].label : null;
      set({ visibleCount: next, currentLabel });
    },
    finishAnimation: () => set({ status: "done", currentLabel: null }),
  };
});
