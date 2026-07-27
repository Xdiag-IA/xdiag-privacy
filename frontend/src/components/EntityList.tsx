import {
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
  Box,
  HStack,
  Stack,
  Tag,
  TagLabel,
  Text,
} from "@chakra-ui/react";
import { useMemo } from "react";
import { useRedactionStore } from "../stores/redactionStore";
import { labelColor, labelFriendly, maskText } from "../labels";
import type { Entity } from "../api/types";

interface Group {
  label: string;
  items: { entity: Entity; index: number }[];
}

function groupByLabel(entities: Entity[]): Group[] {
  const map = new Map<string, Group>();
  entities.forEach((e, idx) => {
    const key = e.label.toUpperCase();
    if (!map.has(key)) map.set(key, { label: key, items: [] });
    map.get(key)!.items.push({ entity: e, index: idx });
  });
  return [...map.values()].sort((a, b) => b.items.length - a.items.length);
}

export function EntityList() {
  const entities = useRedactionStore((s) => s.entities);
  const visible = useRedactionStore((s) => s.visibleCount);
  const showOriginal = useRedactionStore((s) => s.showOriginalText);
  const setHover = useRedactionStore((s) => s.setHoveredEntity);
  const setSelected = useRedactionStore((s) => s.setSelectedEntity);
  const hoveredIndex = useRedactionStore((s) => s.hoveredEntityIndex);
  const selectedIndex = useRedactionStore((s) => s.selectedEntityIndex);

  const groups = useMemo(() => groupByLabel(entities), [entities]);

  if (!entities.length) {
    return (
      <Box p={5} color="slate.500" fontSize="sm">
        Nenhuma entidade detectada ainda. Faca upload de um documento para comecar.
      </Box>
    );
  }

  const visibleSet = new Set(
    entities.slice(0, visible).map((e) => `${e.char_span[0]}-${e.char_span[1]}`),
  );

  return (
    <Accordion allowMultiple defaultIndex={groups.map((_, i) => i)} px={2} pt={2}>
      {groups.map((g) => {
        const color = labelColor(g.label);
        const visibleCount = g.items.filter((it) =>
          visibleSet.has(`${it.entity.char_span[0]}-${it.entity.char_span[1]}`),
        ).length;
        return (
          <AccordionItem key={g.label} border="none" mb={2}>
            <AccordionButton
              borderRadius="8px"
              _hover={{ bg: "slate.800" }}
              px={3}
              py={2}
            >
              <HStack flex="1" justify="space-between">
                <HStack>
                  <Box w="10px" h="10px" borderRadius="full" bg={color} />
                  <Text fontSize="sm" fontWeight={600} color="slate.100">
                    {labelFriendly(g.label)}
                  </Text>
                </HStack>
                <Tag size="sm" variant="subtle" borderRadius="full">
                  <TagLabel fontFamily="mono" fontSize="xs">
                    {visibleCount} / {g.items.length}
                  </TagLabel>
                </Tag>
              </HStack>
              <AccordionIcon />
            </AccordionButton>
            <AccordionPanel pb={2} pt={1} px={2}>
              <Stack spacing={1.5}>
                {g.items.map(({ entity, index }) => {
                  const id = `${entity.char_span[0]}-${entity.char_span[1]}`;
                  const shown = visibleSet.has(id);
                  const isHover = hoveredIndex === index;
                  const isSelected = selectedIndex === index;
                  return (
                    <HStack
                      key={`${id}-${index}`}
                      px={3}
                      py={2}
                      borderRadius="8px"
                      bg={isSelected ? "slate.800" : isHover ? "slate.800" : "transparent"}
                      borderLeft="3px solid"
                      borderColor={shown ? color : "slate.800"}
                      opacity={shown ? 1 : 0.4}
                      transition="all 160ms ease"
                      onMouseEnter={() => setHover(index)}
                      onMouseLeave={() => setHover(null)}
                      onClick={() =>
                        setSelected(isSelected ? null : index)
                      }
                      cursor="pointer"
                      role="button"
                      aria-pressed={isSelected}
                    >
                      <Box flex={1} minW={0}>
                        <Text
                          fontSize="sm"
                          fontFamily="mono"
                          color="slate.100"
                          noOfLines={1}
                          title={showOriginal ? entity.text : undefined}
                        >
                          {showOriginal ? entity.text : maskText(entity.text)}
                        </Text>
                        <Text fontSize="xs" color="slate.500" mt={0.5}>
                          {entity.redacted} (score {entity.score.toFixed(2)})
                        </Text>
                      </Box>
                    </HStack>
                  );
                })}
              </Stack>
            </AccordionPanel>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}
