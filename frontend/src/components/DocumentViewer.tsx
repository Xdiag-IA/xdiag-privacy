import { Box, Center, Spinner, Text, VStack } from "@chakra-ui/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRedactionStore } from "../stores/redactionStore";
import type { BBox, Entity } from "../api/types";
import { LABEL_COLORS } from "../labels";

function bboxToPolygonPoints(bbox: BBox): string {
  return bbox.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
}

function fillFromColor(hex: string, alpha = 0.25): string {
  const v = hex.replace("#", "");
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

interface RedactionPolygonProps {
  entity: Entity;
  index: number;
  hovered: boolean;
  highlighted: boolean;
  fadeIn: boolean;
}

function RedactionPolygon({ entity, index, hovered, highlighted, fadeIn }: RedactionPolygonProps) {
  const color = LABEL_COLORS[entity.label.toUpperCase()] ?? "#dc2626";
  const fill = fillFromColor(color, hovered || highlighted ? 0.45 : 0.28);
  const stroke = color;
  const setHover = useRedactionStore((s) => s.setHoveredEntity);

  return (
    <g
      style={{
        opacity: fadeIn ? 1 : 0,
        transition: "opacity 200ms ease, fill 160ms ease",
      }}
      onMouseEnter={() => setHover(index)}
      onMouseLeave={() => setHover(null)}
    >
      {entity.bboxes.map((bbox, i) => (
        <polygon
          key={i}
          points={bboxToPolygonPoints(bbox)}
          fill={fill}
          stroke={stroke}
          strokeOpacity={hovered || highlighted ? 1 : 0.85}
          strokeWidth={hovered || highlighted ? 2.5 : 1.5}
        />
      ))}
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
  const isSynthetic = useRedactionStore((s) => s.isSynthetic);
  const status = useRedactionStore((s) => s.status);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);

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

  return (
    <Box
      ref={containerRef}
      h="100%"
      w="100%"
      overflow="auto"
      bg="slate.950"
      p={4}
      position="relative"
    >
      {!imageUrl && (
        <Center h="100%" color="slate.500">
          <Text>Aguardando documento...</Text>
        </Center>
      )}

      {imageUrl && status === "uploading" && (
        <Center h="100%" color="slate.300">
          <VStack>
            <Spinner color="redaction.500" />
            <Text fontSize="sm">Subindo arquivo</Text>
          </VStack>
        </Center>
      )}

      {imageUrl && status === "processing" && (
        <Center h="100%" color="slate.300">
          <VStack>
            <Spinner color="redaction.500" size="lg" />
            <Text fontSize="sm">OCR + deteccao de PII em execucao localmente</Text>
          </VStack>
        </Center>
      )}

      {imageUrl && (status === "animating" || status === "done") && dims && (
        <Center>
          <Box
            position="relative"
            width={`${renderedW}px`}
            height={`${renderedH}px`}
            boxShadow="0 12px 40px rgba(0,0,0,0.6)"
            borderRadius="6px"
            overflow="hidden"
            bg="white"
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
              viewBox={`0 0 ${dims.w} ${dims.h}`}
              preserveAspectRatio="none"
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                pointerEvents: "auto",
              }}
            >
              {entities.map((e, i) => (
                <RedactionPolygon
                  key={`${e.char_span[0]}-${e.char_span[1]}-${i}`}
                  entity={e}
                  index={i}
                  hovered={hoveredIndex === i}
                  highlighted={selectedIndex === i}
                  fadeIn={i < visibleCount}
                />
              ))}
            </svg>

            {isSynthetic && <SyntheticWatermark width={renderedW} height={renderedH} />}
          </Box>
        </Center>
      )}
    </Box>
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
        style={{ opacity: 0.12 }}
      >
        <text
          x="0"
          y="0"
          textAnchor="middle"
          dominantBaseline="middle"
          fill="#dc2626"
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
