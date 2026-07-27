import { Box, Button, Center, HStack, Spinner, Text, VStack } from "@chakra-ui/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRedactionStore } from "../stores/redactionStore";
import type { ManualBox } from "../stores/redactionStore";
import type { BBox, Entity } from "../api/types";
import { LABEL_COLORS, LABEL_FAMILY, withAlpha } from "../labels";
import { TRANSITION } from "../theme";

// Menor lado aceito para um retangulo desenhado a mao, em pixels da pagina
// (nao da tela). Evita criar uma area manual a partir de um clique acidental.
const MIN_MANUAL_BOX_SIDE = 8;

// Tolerancia, em pixels da pagina, para considerar um quadrilatero do OCR
// alinhado aos eixos. Dentro dela vale a pena desenhar um retangulo de cantos
// arredondados em vez de um poligono de cantos vivos: e o mesmo dado, mas
// visualmente muito mais limpo sobre o documento.
const AXIS_ALIGN_TOLERANCE = 0.75;

function bboxToPolygonPoints(bbox: BBox): string {
  return bbox.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
}

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Retorna o retangulo equivalente se o quadrilatero for alinhado aos eixos. */
function axisAlignedRect(bbox: BBox): Rect | null {
  const [p0, p1, p2, p3] = bbox;
  const near = (a: number, b: number) => Math.abs(a - b) <= AXIS_ALIGN_TOLERANCE;
  if (!near(p0[1], p1[1]) || !near(p2[1], p3[1])) return null;
  if (!near(p0[0], p3[0]) || !near(p1[0], p2[0])) return null;
  const x = Math.min(p0[0], p3[0]);
  const y = Math.min(p0[1], p1[1]);
  const width = Math.max(p1[0], p2[0]) - x;
  const height = Math.max(p2[1], p3[1]) - y;
  if (width <= 0 || height <= 0) return null;
  return { x, y, width, height };
}

function rectToBBox(x1: number, y1: number, x2: number, y2: number): BBox {
  const left = Math.min(x1, x2);
  const right = Math.max(x1, x2);
  const top = Math.min(y1, y2);
  const bottom = Math.max(y1, y2);
  return [
    [left, top],
    [right, top],
    [right, bottom],
    [left, bottom],
  ];
}

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m14.5 4.5 5 5L8 21H3v-5z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m13 6 5 5" strokeLinecap="round" />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
      <path d="m14.5 5-7 7 7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
      <path d="m9.5 5 7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface RedactionPolygonProps {
  entity: Entity;
  index: number;
  hovered: boolean;
  highlighted: boolean;
  fadeIn: boolean;
}

function RedactionPolygon({ entity, index, hovered, highlighted, fadeIn }: RedactionPolygonProps) {
  const color = LABEL_COLORS[entity.label.toUpperCase()] ?? LABEL_FAMILY.OUTRO;
  const active = hovered || highlighted;
  const fill = withAlpha(color, active ? 0.44 : 0.26);
  const setHover = useRedactionStore((s) => s.setHoveredEntity);

  return (
    <g
      style={{
        opacity: fadeIn ? 1 : 0,
        transform: fadeIn ? "scale(1)" : "scale(0.94)",
        transformBox: "fill-box",
        transformOrigin: "center",
        transition:
          "opacity 220ms cubic-bezier(0.22, 1, 0.36, 1), transform 260ms cubic-bezier(0.22, 1, 0.36, 1)",
      }}
      onMouseEnter={() => setHover(index)}
      onMouseLeave={() => setHover(null)}
    >
      {entity.bboxes.map((bbox, i) => {
        const rect = axisAlignedRect(bbox);
        const common = {
          fill,
          stroke: color,
          strokeOpacity: active ? 1 : 0.8,
          strokeWidth: active ? 2.5 : 1.4,
          style: { transition: "fill 160ms ease, stroke-width 160ms ease" },
        };
        return rect ? (
          <rect
            key={i}
            x={rect.x}
            y={rect.y}
            width={rect.width}
            height={rect.height}
            rx={Math.min(3, rect.height / 3)}
            {...common}
          />
        ) : (
          <polygon key={i} points={bboxToPolygonPoints(bbox)} {...common} />
        );
      })}
    </g>
  );
}

export function DocumentViewer() {
  const imageUrl = useRedactionStore((s) => s.imageUrl);
  const dims = useRedactionStore((s) => s.imageDimensions);
  const entities = useRedactionStore((s) => s.entities);
  const visibleCount = useRedactionStore((s) => s.visibleCount);
  const hoveredIndex = useRedactionStore((s) => s.hoveredEntityIndex);
  const selectedIndex = useRedactionStore((s) => s.selectedEntityIndex);
  const excludedIndices = useRedactionStore((s) => s.excludedEntityIndices);
  const isSynthetic = useRedactionStore((s) => s.isSynthetic);
  const status = useRedactionStore((s) => s.status);
  const pageCount = useRedactionStore((s) => s.pages.length);
  const currentPage = useRedactionStore((s) => s.currentPage);
  const setPage = useRedactionStore((s) => s.setPage);
  const manualBoxes = useRedactionStore((s) => s.manualBoxes);
  const drawMode = useRedactionStore((s) => s.drawMode);
  const setDrawMode = useRedactionStore((s) => s.setDrawMode);
  const addManualBox = useRedactionStore((s) => s.addManualBox);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  // Estado usado so para desenhar o preview do arrasto; a logica de arrastar
  // em si vive em refs (ver useEffect abaixo) para nao depender de handlers
  // presos ao SVG, que cancelavam a marcacao assim que o cursor saia da area
  // por um pixel (arrasto rapido real quase sempre sai da area em algum
  // momento).
  const [dragPreview, setDragPreview] = useState<{
    start: { x: number; y: number };
    current: { x: number; y: number };
  } | null>(null);
  const draggingRef = useRef(false);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const dragCurrentRef = useRef<{ x: number; y: number } | null>(null);
  const dimsRef = useRef(dims);
  dimsRef.current = dims;

  const toSvgPoint = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return null;
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const loc = pt.matrixTransform(ctm.inverse());
    return { x: loc.x, y: loc.y };
  }, []);

  const onSvgMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!drawMode) return;
      e.preventDefault();
      const p = toSvgPoint(e.clientX, e.clientY);
      if (!p) return;
      draggingRef.current = true;
      dragStartRef.current = p;
      dragCurrentRef.current = p;
      setDragPreview({ start: p, current: p });
    },
    [drawMode, toSvgPoint],
  );

  // Rastreia o arrasto em window, nao no svg: um arrasto real do mouse
  // costuma sair da area do elemento em algum momento, e so encerrar no
  // mouseup (em qualquer lugar da pagina) e o comportamento esperado de uma
  // ferramenta de selecao por retangulo.
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!draggingRef.current) return;
      const p = toSvgPoint(e.clientX, e.clientY);
      if (!p) return;
      dragCurrentRef.current = p;
      setDragPreview({ start: dragStartRef.current!, current: p });
    }
    function onUp(e: MouseEvent) {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      const start = dragStartRef.current;
      // Calcula a posicao final a partir do proprio evento mouseup, em vez
      // de depender so do ultimo mousemove: alguns drivers de automacao (e
      // gestos de arrasto sinteticos) disparam so mousedown + mouseup, sem
      // mousemove intermediario, e nesse caso o ref so seria atualizado
      // aqui.
      const current = toSvgPoint(e.clientX, e.clientY) ?? dragCurrentRef.current;
      const dims = dimsRef.current;
      if (start && current && dims) {
        const w = Math.abs(current.x - start.x);
        const h = Math.abs(current.y - start.y);
        if (w >= MIN_MANUAL_BOX_SIDE && h >= MIN_MANUAL_BOX_SIDE) {
          const clampedX1 = Math.max(0, Math.min(dims.w, start.x));
          const clampedY1 = Math.max(0, Math.min(dims.h, start.y));
          const clampedX2 = Math.max(0, Math.min(dims.w, current.x));
          const clampedY2 = Math.max(0, Math.min(dims.h, current.y));
          addManualBox(rectToBBox(clampedX1, clampedY1, clampedX2, clampedY2));
        }
      }
      dragStartRef.current = null;
      dragCurrentRef.current = null;
      setDragPreview(null);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [toSvgPoint, addManualBox]);

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const ro = new ResizeObserver(() => setContainerWidth(el.clientWidth));
    ro.observe(el);
    setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const scale = useMemo(() => {
    if (!dims || !containerWidth) return 1;
    const padX = 32;
    return Math.min(1, (containerWidth - padX) / dims.w);
  }, [dims, containerWidth]);

  const renderedW = dims ? dims.w * scale : 0;
  const renderedH = dims ? dims.h * scale : 0;
  const ready = (status === "animating" || status === "done") && !!dims;

  return (
    <Box
      ref={containerRef}
      h="100%"
      w="100%"
      overflow="auto"
      bg="transparent"
      p={5}
      position="relative"
    >
      {!imageUrl && (
        <Center h="100%" color="slate.600">
          <Text fontSize="sm">Aguardando documento...</Text>
        </Center>
      )}

      {imageUrl && status === "uploading" && <Working label="Subindo arquivo" />}

      {imageUrl && status === "processing" && (
        <Working label="OCR e detecção de PII em execução localmente" big />
      )}

      {imageUrl && ready && (
        <HStack justify="center" mb={4} spacing={3} flexWrap="wrap">
          <Button
            size="sm"
            variant={drawMode ? "solid" : "surface"}
            leftIcon={<PencilIcon />}
            onClick={() => setDrawMode(!drawMode)}
            {...(drawMode
              ? {
                  bgGradient: "linear(to-b, #fbbf24, #d97706)",
                  color: "#1c1207",
                  boxShadow: "0 10px 26px -14px rgba(245, 158, 11, 0.9)",
                  _hover: { bgGradient: "linear(to-b, #fcd34d, #f59e0b)", transform: "translateY(-1px)" },
                }
              : { color: "#fcd34d" })}
          >
            {drawMode ? "Cancelar marcação" : "Marcar área manual"}
          </Button>
          {drawMode && (
            <Text fontSize="xs" color="#fcd34d" fontWeight={500}>
              Clique e arraste sobre o documento para marcar uma área que o
              modelo não detectou.
            </Text>
          )}
        </HStack>
      )}

      {pageCount > 1 && ready && (
        <HStack justify="center" mb={4} spacing={2}>
          <Button
            size="xs"
            variant="surface"
            leftIcon={<ChevronLeftIcon />}
            onClick={() => setPage(currentPage - 1)}
            isDisabled={currentPage === 0}
          >
            Anterior
          </Button>
          <Box
            px={3}
            h="26px"
            display="flex"
            alignItems="center"
            borderRadius="full"
            bg="surface.raised"
            border="1px solid"
            borderColor="line.subtle"
          >
            <Text fontSize="2xs" color="slate.300" fontFamily="mono">
              {currentPage + 1} / {pageCount}
            </Text>
          </Box>
          <Button
            size="xs"
            variant="surface"
            rightIcon={<ChevronRightIcon />}
            onClick={() => setPage(currentPage + 1)}
            isDisabled={currentPage >= pageCount - 1}
          >
            Próxima
          </Button>
        </HStack>
      )}

      {imageUrl && ready && (
        <Center pb={4}>
          <Box
            position="relative"
            width={`${renderedW}px`}
            height={`${renderedH}px`}
            boxShadow="0 0 0 1px rgba(148, 163, 184, 0.16), 0 30px 70px -30px rgba(0, 0, 0, 0.9)"
            borderRadius="10px"
            overflow="hidden"
            bg="white"
            transition={TRANSITION}
          >
            <img
              src={imageUrl}
              alt="documento"
              draggable={false}
              style={{
                display: "block",
                width: "100%",
                height: "100%",
                pointerEvents: "none",
                userSelect: "none",
              }}
            />
            <svg
              ref={svgRef}
              viewBox={`0 0 ${dims!.w} ${dims!.h}`}
              preserveAspectRatio="none"
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                pointerEvents: "auto",
                cursor: drawMode ? "crosshair" : "default",
              }}
              onMouseDown={onSvgMouseDown}
            >
              {entities.map((e, i) =>
                excludedIndices.has(i) ? null : (
                  <RedactionPolygon
                    key={`${e.char_span[0]}-${e.char_span[1]}-${i}`}
                    entity={e}
                    index={i}
                    hovered={hoveredIndex === i}
                    highlighted={selectedIndex === i}
                    fadeIn={i < visibleCount}
                  />
                ),
              )}
              {manualBoxes.map((b) => (
                <ManualPolygon key={b.id} box={b} />
              ))}
              {dragPreview && (
                <rect
                  x={Math.min(dragPreview.start.x, dragPreview.current.x)}
                  y={Math.min(dragPreview.start.y, dragPreview.current.y)}
                  width={Math.abs(dragPreview.current.x - dragPreview.start.x)}
                  height={Math.abs(dragPreview.current.y - dragPreview.start.y)}
                  rx={3}
                  fill={withAlpha(LABEL_FAMILY.MANUAL, 0.24)}
                  stroke={LABEL_FAMILY.MANUAL}
                  strokeDasharray="6 4"
                  strokeWidth={2}
                />
              )}
            </svg>

            {isSynthetic && <SyntheticWatermark width={renderedW} height={renderedH} />}
          </Box>
        </Center>
      )}
    </Box>
  );
}

/** Estado de espera com a cor da marca, usado no upload e no processamento. */
function Working({ label, big }: { label: string; big?: boolean }) {
  return (
    <Center h="100%" color="slate.300">
      <VStack spacing={4}>
        <Box position="relative" display="flex" alignItems="center" justifyContent="center">
          <Box
            position="absolute"
            w={big ? "76px" : "56px"}
            h={big ? "76px" : "56px"}
            borderRadius="full"
            bg="rgba(34, 211, 238, 0.12)"
            filter="blur(14px)"
          />
          <Spinner
            color="brand.300"
            emptyColor="rgba(148, 163, 184, 0.14)"
            thickness={big ? "3px" : "2.5px"}
            size={big ? "lg" : "md"}
            speed="0.7s"
          />
        </Box>
        <Text fontSize="sm" color="slate.400" textAlign="center" maxW="320px">
          {label}
        </Text>
      </VStack>
    </Center>
  );
}

function ManualPolygon({ box }: { box: ManualBox }) {
  const rect = axisAlignedRect(box.bbox);
  const props = {
    fill: withAlpha(LABEL_FAMILY.MANUAL, 0.3),
    stroke: LABEL_FAMILY.MANUAL,
    strokeDasharray: "6 4",
    strokeWidth: 2,
  };
  return rect ? (
    <rect x={rect.x} y={rect.y} width={rect.width} height={rect.height} rx={3} {...props} />
  ) : (
    <polygon points={bboxToPolygonPoints(box.bbox)} {...props} />
  );
}

function SyntheticWatermark({ width, height }: { width: number; height: number }) {
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
    >
      <g
        transform={`translate(${width / 2}, ${height / 2}) rotate(-30)`}
        style={{ opacity: 0.14 }}
      >
        <text
          x="0"
          y="0"
          textAnchor="middle"
          dominantBaseline="middle"
          fill={LABEL_FAMILY.MANUAL}
          fontSize={Math.max(width / 6, 80)}
          fontFamily="Inter, sans-serif"
          fontWeight={800}
          letterSpacing="0.08em"
        >
          SYNTHETIC
        </text>
      </g>
    </svg>
  );
}
