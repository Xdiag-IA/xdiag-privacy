import {
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionPanel,
  AccordionItem,
  Box,
  HStack,
  IconButton,
  Stack,
  Text,
  Tooltip,
} from "@chakra-ui/react";
import { useMemo } from "react";
import { useRedactionStore } from "../stores/redactionStore";
import type { ManualBox } from "../stores/redactionStore";
import { labelColor, labelFriendly, maskText, withAlpha } from "../labels";
import type { Entity } from "../api/types";
import { TRANSITION } from "../theme";

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.9">
      <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m-9 0 1 14a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-14" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.9">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.9">
      <path d="M3 3l18 18" strokeLinecap="round" />
      <path d="M10.6 5.2A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a15.2 15.2 0 0 1-3.1 3.9M6.5 6.5C3.7 8.3 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 4.2-.95" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Contador pequeno usado nos cabecalhos de grupo e das secoes de alerta. */
function Count({ children, color, bg }: { children: React.ReactNode; color?: string; bg?: string }) {
  return (
    <Box
      px={2}
      h="20px"
      display="flex"
      alignItems="center"
      borderRadius="full"
      bg={bg ?? "rgba(148, 163, 184, 0.1)"}
      color={color ?? "slate.400"}
      fontSize="2xs"
      fontFamily="mono"
      fontWeight={600}
      flexShrink={0}
    >
      {children}
    </Box>
  );
}

interface Group {
  label: string;
  items: { entity: Entity; index: number }[];
}

function groupByLabel(entities: Entity[]): Group[] {
  const map = new Map<string, Group>();
  entities.forEach((e, idx) => {
    if (e.unmapped) return; // exibidas na secao dedicada acima dos grupos
    const key = e.label.toUpperCase();
    if (!map.has(key)) map.set(key, { label: key, items: [] });
    map.get(key)!.items.push({ entity: e, index: idx });
  });
  return [...map.values()].sort((a, b) => b.items.length - a.items.length);
}

function UnmappedSection({ items }: { items: { entity: Entity; index: number }[] }) {
  const showOriginal = useRedactionStore((s) => s.showOriginalText);
  if (!items.length) return null;
  return (
    <Box
      mx={3}
      mt={3}
      p={3.5}
      borderRadius="14px"
      border="1px solid"
      borderColor="rgba(244, 63, 94, 0.4)"
      bg="rgba(244, 63, 94, 0.07)"
      boxShadow="0 0 0 1px rgba(244, 63, 94, 0.06), 0 18px 40px -30px rgba(244, 63, 94, 0.8)"
    >
      <HStack mb={2.5} justify="space-between">
        <HStack spacing={2}>
          <Box w="6px" h="6px" borderRadius="full" bg="#f43f5e" boxShadow="0 0 10px #f43f5e" />
          <Text fontSize="xs" fontWeight={700} color="#fda4af" letterSpacing="0.02em">
            Não mapeadas
          </Text>
        </HStack>
        <Count color="#fda4af" bg="rgba(244, 63, 94, 0.16)">
          {items.length}
        </Count>
      </HStack>
      <Stack spacing={1.5}>
        {items.map(({ entity, index }) => (
          <Box key={`unmapped-${index}`} px={2.5} py={2} borderRadius="10px" bg="rgba(2, 6, 23, 0.5)">
            <Text fontSize="13px" fontFamily="mono" color="slate.100" noOfLines={1}>
              {showOriginal ? entity.text : maskText(entity.text)}
            </Text>
            <Text fontSize="2xs" color="#fda4af" mt={1} lineHeight={1.5}>
              {labelFriendly(entity.label)}: sem região na imagem, será exposta no export
            </Text>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

function ManualSection({
  boxes,
  onRemove,
}: {
  boxes: ManualBox[];
  onRemove: (id: string) => void;
}) {
  if (!boxes.length) return null;
  return (
    <Box
      mx={3}
      mt={3}
      p={3.5}
      borderRadius="14px"
      border="1px solid"
      borderColor="rgba(245, 158, 11, 0.35)"
      bg="rgba(245, 158, 11, 0.07)"
    >
      <HStack mb={2.5} justify="space-between">
        <HStack spacing={2}>
          <Box w="6px" h="6px" borderRadius="full" bg="#f59e0b" boxShadow="0 0 10px #f59e0b" />
          <Text fontSize="xs" fontWeight={700} color="#fcd34d" letterSpacing="0.02em">
            Adicionadas manualmente
          </Text>
        </HStack>
        <Count color="#fcd34d" bg="rgba(245, 158, 11, 0.16)">
          {boxes.length}
        </Count>
      </HStack>
      <Stack spacing={1.5}>
        {boxes.map((box) => (
          <HStack
            key={box.id}
            px={2.5}
            py={1.5}
            borderRadius="10px"
            bg="rgba(2, 6, 23, 0.5)"
            justify="space-between"
          >
            <Text fontSize="2xs" color="slate.400" lineHeight={1.5}>
              Área marcada à mão, será tarjada na imagem exportada
            </Text>
            <Tooltip label="Remover marcação" hasArrow>
              <IconButton
                aria-label="Remover marcação"
                icon={<TrashIcon />}
                size="xs"
                variant="ghost"
                color="#fcd34d"
                _hover={{ bg: "rgba(245, 158, 11, 0.16)" }}
                onClick={() => onRemove(box.id)}
              />
            </Tooltip>
          </HStack>
        ))}
      </Stack>
    </Box>
  );
}

export function EntityList() {
  const entities = useRedactionStore((s) => s.entities);
  const visible = useRedactionStore((s) => s.visibleCount);
  const showOriginal = useRedactionStore((s) => s.showOriginalText);
  const setHover = useRedactionStore((s) => s.setHoveredEntity);
  const setSelected = useRedactionStore((s) => s.setSelectedEntity);
  const hoveredIndex = useRedactionStore((s) => s.hoveredEntityIndex);
  const selectedIndex = useRedactionStore((s) => s.selectedEntityIndex);
  const excludedIndices = useRedactionStore((s) => s.excludedEntityIndices);
  const toggleExcluded = useRedactionStore((s) => s.toggleEntityExcluded);
  const manualBoxes = useRedactionStore((s) => s.manualBoxes);
  const removeManualBox = useRedactionStore((s) => s.removeManualBox);

  const groups = useMemo(() => groupByLabel(entities), [entities]);
  const unmappedItems = useMemo(
    () =>
      entities
        .map((entity, index) => ({ entity, index }))
        .filter((x) => x.entity.unmapped),
    [entities],
  );

  if (!entities.length && !manualBoxes.length) {
    return (
      <Box p={6} color="slate.500" fontSize="sm" lineHeight={1.7}>
        Nenhuma entidade detectada ainda. Faça upload de um documento para começar.
      </Box>
    );
  }

  const visibleSet = new Set(
    entities.slice(0, visible).map((e) => `${e.char_span[0]}-${e.char_span[1]}`),
  );

  return (
    <>
      <ManualSection boxes={manualBoxes} onRemove={removeManualBox} />
      <UnmappedSection items={unmappedItems} />
      <Accordion allowMultiple defaultIndex={groups.map((_, i) => i)} px={3} pt={3} pb={2}>
        {groups.map((g) => {
          const color = labelColor(g.label);
          const visibleCount = g.items.filter((it) =>
            visibleSet.has(`${it.entity.char_span[0]}-${it.entity.char_span[1]}`),
          ).length;
          return (
            <AccordionItem key={g.label} border="none" mb={1.5}>
              <AccordionButton
                borderRadius="10px"
                px={3}
                py={2.5}
                color="slate.400"
                _hover={{ bg: "surface.hover", color: "slate.200" }}
              >
                <HStack flex="1" justify="space-between" pr={2}>
                  <HStack spacing={2.5} minW={0}>
                    <Box
                      w="9px"
                      h="9px"
                      borderRadius="3px"
                      bg={color}
                      boxShadow={`0 0 10px ${withAlpha(color, 0.7)}`}
                      flexShrink={0}
                    />
                    <Text fontSize="13px" fontWeight={600} color="slate.100" noOfLines={1}>
                      {labelFriendly(g.label)}
                    </Text>
                  </HStack>
                  <Count>
                    {visibleCount} / {g.items.length}
                  </Count>
                </HStack>
                <AccordionIcon boxSize="18px" />
              </AccordionButton>
              <AccordionPanel pb={2} pt={1} px={1}>
                <Stack spacing={1}>
                  {g.items.map(({ entity, index }) => {
                    const id = `${entity.char_span[0]}-${entity.char_span[1]}`;
                    const shown = visibleSet.has(id);
                    const isHover = hoveredIndex === index;
                    const isSelected = selectedIndex === index;
                    const excluded = excludedIndices.has(index);
                    return (
                      <HStack
                        key={`${id}-${index}`}
                        px={3}
                        py={2}
                        borderRadius="10px"
                        bg={
                          isSelected
                            ? withAlpha(color, 0.14)
                            : isHover
                              ? "surface.hover"
                              : "transparent"
                        }
                        borderLeft="2px solid"
                        borderColor={excluded ? "line.medium" : shown ? color : "transparent"}
                        opacity={excluded ? 0.5 : shown ? 1 : 0.42}
                        transform={isHover && !isSelected ? "translateX(2px)" : "translateX(0)"}
                        transition={TRANSITION}
                        onMouseEnter={() => setHover(index)}
                        onMouseLeave={() => setHover(null)}
                        onClick={() => setSelected(isSelected ? null : index)}
                        cursor="pointer"
                        role="button"
                        aria-pressed={isSelected}
                      >
                        <Box flex={1} minW={0}>
                          <Text
                            fontSize="13px"
                            fontFamily="mono"
                            color="slate.100"
                            noOfLines={1}
                            textDecoration={excluded ? "line-through" : undefined}
                            title={showOriginal ? entity.text : undefined}
                          >
                            {showOriginal ? entity.text : maskText(entity.text)}
                          </Text>
                          <Text fontSize="2xs" color={excluded ? "#fcd34d" : "slate.500"} mt={0.5}>
                            {excluded
                              ? "não será anonimizada (marcada manualmente)"
                              : `${entity.redacted} (score ${entity.score.toFixed(2)})`}
                          </Text>
                        </Box>
                        <Tooltip
                          label={excluded ? "Voltar a anonimizar" : "Marcar como não PII (não anonimizar)"}
                          hasArrow
                          openDelay={300}
                        >
                          <IconButton
                            aria-label={excluded ? "Voltar a anonimizar" : "Não anonimizar"}
                            icon={excluded ? <EyeOffIcon /> : <EyeIcon />}
                            size="xs"
                            variant="ghost"
                            color={excluded ? "#fcd34d" : "slate.500"}
                            _hover={{
                              bg: excluded ? "rgba(245, 158, 11, 0.16)" : "surface.hover",
                              color: excluded ? "#fcd34d" : "slate.200",
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleExcluded(index);
                            }}
                          />
                        </Tooltip>
                      </HStack>
                    );
                  })}
                </Stack>
              </AccordionPanel>
            </AccordionItem>
          );
        })}
      </Accordion>
    </>
  );
}
