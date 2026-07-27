import {
  Box,
  Flex,
  HStack,
  Tag,
  TagLabel,
  Text,
  Tooltip,
} from "@chakra-ui/react";
import { mappedCount, unmappedCount, useRedactionStore } from "../stores/redactionStore";
import { labelColor, labelFriendly } from "../labels";

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <path d="M14 3v6h6" />
    </svg>
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

  const total = mappedCount(entities);
  const unmapped = unmappedCount(entities);

  return (
    <Box
      position="sticky"
      top={0}
      zIndex={10}
      bg="slate.900"
      borderBottom="1px solid"
      borderColor="slate.800"
      px={5}
      py={4}
    >
      <Flex align="center" justify="space-between" gap={3}>
        <HStack spacing={2} minW={0} flex={1}>
          <Box color="slate.300">
            <FileIcon />
          </Box>
          <Tooltip label={fileName || "nenhum arquivo"} hasArrow>
            <Text
              fontWeight={600}
              fontSize="sm"
              noOfLines={1}
              color="slate.100"
            >
              {fileName || "Nenhum arquivo"}
            </Text>
          </Tooltip>
          {isSynthetic && (
            <Tag size="sm" variant="subtle" colorScheme="redaction" borderRadius="full">
              SYNTHETIC
            </Tag>
          )}
        </HStack>
      </Flex>

      <HStack mt={3} spacing={2} flexWrap="wrap">
        <Tag
          size="md"
          borderRadius="full"
          variant="solid"
          bg="slate.800"
          color="slate.50"
          border="1px solid"
          borderColor="slate.700"
        >
          <Box
            w="8px"
            h="8px"
            borderRadius="full"
            bg={visible >= total && total > 0 ? "green.400" : "redaction.500"}
            mr={2}
          />
          <TagLabel fontFamily="mono" fontSize="sm">
            {visible} / {total} redacted
          </TagLabel>
        </Tag>

        {unmapped > 0 && (
          <Tag size="md" colorScheme="red" variant="solid" borderRadius="full">
            <TagLabel fontSize="sm">
              {unmapped} nao {unmapped === 1 ? "mapeada" : "mapeadas"}
            </TagLabel>
          </Tag>
        )}

        {currentLabel ? (
          <Tag
            size="md"
            borderRadius="full"
            border="1px solid"
            bg={`${labelColor(currentLabel)}22`}
            borderColor={labelColor(currentLabel)}
            color="white"
          >
            <Box
              w="8px"
              h="8px"
              borderRadius="full"
              bg={labelColor(currentLabel)}
              mr={2}
            />
            <TagLabel fontSize="sm">
              {labelFriendly(currentLabel).toLowerCase()}
            </TagLabel>
          </Tag>
        ) : (
          status === "done" &&
          total > 0 && (
            <Tag size="md" colorScheme="green" variant="subtle" borderRadius="full">
              <TagLabel fontSize="sm">redacao completa</TagLabel>
            </Tag>
          )
        )}

        {elapsedMs > 0 && (
          <Tag size="md" variant="subtle" colorScheme="gray" borderRadius="full">
            <TagLabel fontFamily="mono" fontSize="xs">
              {(elapsedMs / 1000).toFixed(2)}s
            </TagLabel>
          </Tag>
        )}
      </HStack>
    </Box>
  );
}
