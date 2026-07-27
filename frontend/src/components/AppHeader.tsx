import { Box, Flex, HStack, Text, Tag, TagLabel, TagLeftIcon } from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { getHealth } from "../api/client";
import type { HealthResponse } from "../api/types";

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5l-8-3z" />
    </svg>
  );
}

function XdiagLogo() {
  return (
    <HStack spacing={3}>
      <Box
        w="36px"
        h="36px"
        borderRadius="8px"
        bg="slate.900"
        border="1px solid"
        borderColor="redaction.700"
        position="relative"
        display="flex"
        alignItems="center"
        justifyContent="center"
      >
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
          <path d="M5 7 L12 17 L19 7" stroke="#dc2626" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="12" cy="20" r="1.4" fill="#f8fafc" />
        </svg>
      </Box>
      <Box lineHeight="1.1">
        <Text fontSize="md" fontWeight={700} color="slate.50" letterSpacing="-0.01em">
          Xdiag.Redact
        </Text>
        <Text fontSize="xs" color="slate.400">
          Privacy Filter Tracking
        </Text>
      </Box>
    </HStack>
  );
}

export function AppHeader() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const h = await getHealth();
        if (!cancelled) {
          setHealth(h);
          setHealthError(null);
        }
      } catch (e) {
        if (!cancelled) setHealthError(e instanceof Error ? e.message : "offline");
      }
    };
    tick();
    const interval = window.setInterval(tick, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const healthy = !!health && !healthError;

  return (
    <Flex
      as="header"
      h="64px"
      px={6}
      align="center"
      justify="space-between"
      bg="slate.900"
      borderBottom="1px solid"
      borderColor="slate.800"
      position="sticky"
      top={0}
      zIndex={20}
    >
      <XdiagLogo />
      <HStack spacing={3}>
        <Tag size="sm" variant="subtle" colorScheme="redaction" borderRadius="full">
          <TagLeftIcon as={ShieldIcon} boxSize="12px" />
          <TagLabel>Local first, LGPD by design</TagLabel>
        </Tag>
        <Tag
          size="sm"
          variant="subtle"
          colorScheme={healthy ? "green" : "orange"}
          borderRadius="full"
        >
          <Box
            w="8px"
            h="8px"
            borderRadius="full"
            bg={healthy ? "green.400" : "orange.400"}
            mr={2}
          />
          <TagLabel>
            {healthy
              ? `API ok, ${health!.device}, ${health!.mock_mode ? "mock" : health!.pii}`
              : "API offline"}
          </TagLabel>
        </Tag>
      </HStack>
    </Flex>
  );
}
