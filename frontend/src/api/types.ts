// Mirrors backend/app/models.py. Keep both files in sync when the contract
// changes. Comments here document any frontend specific assumptions.

export type Point = [number, number];
export type BBox = [Point, Point, Point, Point]; // TL, TR, BR, BL

export interface ImageDimensions {
  w: number;
  h: number;
}

export interface OCRBlock {
  text: string;
  bbox: BBox;
  confidence: number;
  char_start: number;
  char_end: number;
}

export interface Entity {
  label: string;
  text: string;
  score: number;
  char_span: [number, number];
  bboxes: BBox[];
  redacted: string;
  // Detectada no texto mas sem regiao na imagem; bloqueia o export.
  unmapped: boolean;
}

export interface Stats {
  total_entities: number;
  by_label: Record<string, number>;
  unmapped: number;
}

export interface PageResult {
  page_index: number;
  image_dimensions: ImageDimensions;
  ocr_blocks: OCRBlock[];
  entities: Entity[];
  deidentified_text: string;
  original_text?: string | null;
  rendered_image_data_url: string;
}

export interface RedactResponse {
  pages: PageResult[];
  page_count: number;
  stats: Stats;
  is_synthetic: boolean;
  elapsed_ms: number;
}

export interface HealthResponse {
  status: string;
  ocr: string;
  pii: string;
  device: string;
  version: string;
  mock_mode: boolean;
}

export interface LabelInfo {
  label: string;
  color: string;
  description?: string;
  placeholder: string;
}

export interface LabelsResponse {
  labels: LabelInfo[];
}
