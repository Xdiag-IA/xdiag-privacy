import { create } from "zustand";
import { postRedact } from "../api/client";
import type { Entity, OCRBlock, RedactResponse } from "../api/types";

export type Status =
  | "idle"
  | "uploading"
  | "processing"
  | "animating"
  | "done"
  | "error";

interface RedactionState {
  // input
  file: File | null;
  fileName: string;
  isSynthetic: boolean;
  imageUrl: string | null;

  // results
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

  // lifecycle
  status: Status;
  error: string | null;

  // actions
  uploadFile: (file: File, opts?: { isSynthetic?: boolean }) => Promise<void>;
  reset: () => void;
  setShowOriginal: (v: boolean) => void;
  setThreshold: (v: number) => void;
  setHoveredEntity: (i: number | null) => void;
  setSelectedEntity: (i: number | null) => void;
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
    const ay = a.bboxes[0]?.[0]?.[1] ?? 0;
    const by = b.bboxes[0]?.[0]?.[1] ?? 0;
    if (Math.abs(ay - by) > 6) return ay - by;
    const ax = a.bboxes[0]?.[0]?.[0] ?? 0;
    const bx = b.bboxes[0]?.[0]?.[0] ?? 0;
    return ax - bx;
  });
}

const initial = {
  file: null,
  fileName: "",
  isSynthetic: false,
  imageUrl: null,
  imageDimensions: null,
  ocrBlocks: [] as OCRBlock[],
  entities: [] as Entity[],
  deidentifiedText: "",
  originalText: null as string | null,
  elapsedMs: 0,
  visibleCount: 0,
  currentLabel: null as string | null,
  showOriginalText: false,
  threshold: 0.5,
  hoveredEntityIndex: null as number | null,
  selectedEntityIndex: null as number | null,
  status: "idle" as Status,
  error: null as string | null,
};

export const useRedactionStore = create<RedactionState>((set, get) => ({
  ...initial,

  reset: () => {
    const { imageUrl } = get();
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    set({ ...initial });
  },

  uploadFile: async (file, opts) => {
    const { imageUrl: prev } = get();
    if (prev) URL.revokeObjectURL(prev);

    const isSynthetic = opts?.isSynthetic ?? looksSynthetic(file.name);
    const newUrl = URL.createObjectURL(file);

    set({
      file,
      fileName: file.name,
      isSynthetic,
      imageUrl: newUrl,
      status: "uploading",
      error: null,
      ocrBlocks: [],
      entities: [],
      deidentifiedText: "",
      originalText: null,
      elapsedMs: 0,
      visibleCount: 0,
      currentLabel: null,
      hoveredEntityIndex: null,
      selectedEntityIndex: null,
    });

    try {
      set({ status: "processing" });
      const result: RedactResponse = await postRedact(file, {
        threshold: get().threshold,
        reveal: get().showOriginalText,
        isSynthetic,
      });

      const sorted = sortByPosition(result.entities);
      // Prefer the canonical PNG rendered by the backend (handles PDFs and
      // ensures bbox coordinates align with the displayed pixels). Fall back
      // to the original blob URL only if the API did not return one.
      const next = get();
      let nextImageUrl = next.imageUrl;
      if (result.rendered_image_data_url) {
        if (next.imageUrl) URL.revokeObjectURL(next.imageUrl);
        nextImageUrl = result.rendered_image_data_url;
      }
      set({
        imageUrl: nextImageUrl,
        imageDimensions: result.image_dimensions,
        ocrBlocks: result.ocr_blocks,
        entities: sorted,
        deidentifiedText: result.deidentified_text,
        originalText: result.original_text ?? null,
        elapsedMs: result.elapsed_ms,
        status: sorted.length > 0 ? "animating" : "done",
        visibleCount: 0,
        currentLabel: null,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "erro desconhecido";
      set({ status: "error", error: message });
    }
  },

  setShowOriginal: (v) => set({ showOriginalText: v }),
  setThreshold: (v) => set({ threshold: v }),
  setHoveredEntity: (i) => set({ hoveredEntityIndex: i }),
  setSelectedEntity: (i) => set({ selectedEntityIndex: i }),

  bumpVisible: () => {
    const { visibleCount, entities } = get();
    const next = Math.min(visibleCount + 1, entities.length);
    const currentLabel = next > 0 ? entities[next - 1].label : null;
    set({ visibleCount: next, currentLabel });
  },
  finishAnimation: () => set({ status: "done", currentLabel: null }),
}));
