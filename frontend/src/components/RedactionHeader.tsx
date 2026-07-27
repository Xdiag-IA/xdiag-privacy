import { Box, Flex, HStack, Text, Tooltip } from "@chakra-ui/react";
import { mappedCount, unmappedCountAll, useRedactionStore } from "../stores/redactionStore";
import { labelColor, labelFriendly, withAlpha } from "../labels";
import { TRANSITION } from "../theme";

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.9">
      <path d="M14 3H6.5A2.5 2.5 0 0 0 4 5.5v13A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5V9z" strokeLinejoin="round" />
      <path d="M14 3v6h6" strokeLinejoin="round" />
    </svg>
  );
}

/** Pilula compacta do rodape do cabecalho de redacao. */
function Chip({
  children,
  color,
  bg,
  borderColor,
  mono,
}: {
  children: React.ReactNode;
  color?: string;
  bg?: string;
  borderColor?: string;
  mono?: boolean;
}) {
  return (
    <HStack
      spacing={1.5}
      h="24px"
      px={2.5}
      borderRadius="full"
      bg={bg ?? "rgba(148, 163, 184, 0.08)"}
      border="1px solid"
      borderColor={borderColor ?? "line.subtle"}
      color={color ?? "slate.400"}
      fontSize="2xs"
      fontFamily={mono ? "mono" : "body"}
      fontWeight={500}
      whiteSpace="nowrap"
      transition={TRANSITION}
    >
      {children}
    </HStack>
  );
}

export function RedactionHeader() {
  const fileName = useRedactionStore((s) => s.fileName);
  const entities = useRedactionStore((s) => s.entities);
  const visible = useRedactionStore((s) => s.visibleCount);
  const currentLabel = useRedactionStore((s) => s.currentLabel);
  const elapsedMs = useRedactionStore((s) => s.elapsedMs);
  const status = useRedactionStore((s) => s.status);
  const isSynthetic = useRedactionStore((s) => s.isSynthetic);
  const pages = useRedactionStore((s) => s.pages);
  const currentPage = useRedactionStore((s) => s.currentPage);

  const total = mappedCount(entities);
  const unmapped = unmappedCountAll(pages);
  const shown = Math.min(visible, total);
  const pct = total > 0 ? (shown / total) * 100 : 0;
  const complete = total > 0 && shown >= total;

  return (
    <Box
      position="sticky"
      top={0}
      zIndex={10}
      bg="rgba(2, 6, 23, 0.7)"
      backdropFilter="blur(16px)"
      borderBottom="1px solid"
      borderColor="line.subtle"
      px={5}
      py={4}
      flexShrink={0}
    >
      <Flex align="center" justify="space-between" gap={3} mb={3}>
        <HStack spacing={2.5} minW={0} flex={1}>
          <Box color="brand.300" flexShrink={0}>
            <FileIcon />
          </Box>
          <Tooltip label={fileName || "nenhum arquivo"} hasArrow openDelay={400}>
            <Text fontWeight={600} fontSize="sm" noOfLines={1} color="slate.50" letterSpacing="-0.01em">
              {fileName || "Nenhum arquivo"}
            </Text>
          </Tooltip>
          {isSynthetic && (
            <Chip
              color="#fcd34d"
              bg="rgba(251, 191, 36, 0.1)"
              borderColor="rgba(251, 191, 36, 0.3)"
              mono
            >
              SYNTHETIC
            </Chip>
          )}
        </HStack>
      </Flex>

      {/* Barra de progresso da redacao. Durante a animacao ela preenche em
          tempo real; ao terminar vira o indicador de "documento coberto". */}
      <Box mb={3}>
        <HStack justify="space-between" mb={1.5}>
          <Text fontSize="2xs" color="slate.500" textTransform="uppercase" letterSpacing="0.12em" fontWeight={600}>
            Tarjas aplicadas
          </Text>
          <Text fontSize="2xs" fontFamily="mono" color={complete ? "#6ee7b7" : "brand.200"}>
            {shown} / {total}
          </Text>
        </HStack>
        <Box h="4px" borderRadius="full" bg="rgba(148, 163, 184, 0.14)" overflow="hidden">
          <Box
            h="100%"
            w={`${pct}%`}
            borderRadius="full"
            bgGradient={
              complete
                ? "linear(to-r, #10b981, #34d399)"
                : "linear(to-r, brand.500, brand.300)"
            }
            boxShadow={complete ? "0 0 12px rgba(52, 211, 153, 0.6)" : "0 0 12px rgba(34, 211, 238, 0.6)"}
            transition="width 220ms cubic-bezier(0.22, 1, 0.36, 1), background 300ms ease"
          />
        </Box>
      </Box>

      <HStack spacing={2} flexWrap="wrap">
        {pages.length > 1 && (
          <Chip mono>
            pág {currentPage + 1}/{pages.length}
          </Chip>
        )}

        {unmapped > 0 && (
          <Chip
            color="#fda4af"
            bg="rgba(244, 63, 94, 0.12)"
            borderColor="rgba(244, 63, 94, 0.35)"
          >
            {unmapped} não {unmapped === 1 ? "mapeada" : "mapeadas"}
          </Chip>
        )}

        {currentLabel ? (
          <Chip
            color="slate.100"
            bg={withAlpha(labelColor(currentLabel), 0.18)}
            borderColor={withAlpha(labelColor(currentLabel), 0.55)}
          >
            <Box
              w="6px"
              h="6px"
              borderRadius="full"
              bg={labelColor(currentLabel)}
              boxShadow={`0 0 8px ${labelColor(currentLabel)}`}
            />
            {labelFriendly(currentLabel).toLowerCase()}
          </Chip>
        ) : (
          status === "done" &&
          total > 0 &&
          unmapped === 0 && (
            <Chip
              color="#6ee7b7"
              bg="rgba(52, 211, 153, 0.1)"
              borderColor="rgba(52, 211, 153, 0.3)"
            >
              <Box w="6px" h="6px" borderRadius="full" bg="#34d399" boxShadow="0 0 8px #34d399" />
              redação completa
            </Chip>
          )
        )}

        {elapsedMs > 0 && <Chip mono>{(elapsedMs / 1000).toFixed(2)}s</Chip>}
      </HStack>
    </Box>
  );
}
