import { Box, Flex, HStack, Text, Tooltip } from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { getHealth } from "../api/client";
import type { HealthResponse } from "../api/types";
import { useRedactionStore } from "../stores/redactionStore";
import { DocumentsMenu } from "./DocumentsMenu";
import { SettingsDrawer } from "./SettingsDrawer";
import { BrandLockup } from "./BrandMark";
import { TRANSITION } from "../theme";

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5l-8-3z" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * Pilula de status. Um unico componente para todos os indicadores do
 * cabecalho, para que espacamento, altura e peso tipografico nao divirjam.
 */
function Pill({
  children,
  tone = "neutral",
  icon,
  dot,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "brand" | "ok" | "warn";
  icon?: React.ReactNode;
  dot?: boolean;
}) {
  const tones = {
    neutral: { bg: "rgba(148, 163, 184, 0.08)", border: "line.subtle", color: "slate.400", dot: "#94a3b8" },
    brand: { bg: "rgba(34, 211, 238, 0.09)", border: "line.brand", color: "brand.200", dot: "#22d3ee" },
    ok: { bg: "rgba(52, 211, 153, 0.1)", border: "rgba(52, 211, 153, 0.28)", color: "#6ee7b7", dot: "#34d399" },
    warn: { bg: "rgba(251, 191, 36, 0.1)", border: "rgba(251, 191, 36, 0.3)", color: "#fcd34d", dot: "#fbbf24" },
  }[tone];

  return (
    <HStack
      spacing={2}
      h="30px"
      px={3}
      borderRadius="full"
      bg={tones.bg}
      border="1px solid"
      borderColor={tones.border}
      color={tones.color}
      fontSize="2xs"
      fontWeight={500}
      letterSpacing="0.01em"
      whiteSpace="nowrap"
      transition={TRANSITION}
    >
      {dot && (
        <Box w="6px" h="6px" borderRadius="full" bg={tones.dot} boxShadow={`0 0 8px ${tones.dot}`} flexShrink={0} />
      )}
      {icon}
      <Text as="span">{children}</Text>
    </HStack>
  );
}

export function AppHeader() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const reset = useRedactionStore((s) => s.reset);

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
      h="66px"
      px={{ base: 4, md: 6 }}
      align="center"
      justify="space-between"
      gap={4}
      bg="rgba(2, 6, 23, 0.72)"
      backdropFilter="blur(18px)"
      borderBottom="1px solid"
      borderColor="line.subtle"
      position="sticky"
      top={0}
      zIndex={20}
      flexShrink={0}
      // Fio ciano sob a borda: separa o cabecalho do conteudo sem uma linha dura.
      _after={{
        content: '""',
        position: "absolute",
        left: 0,
        right: 0,
        bottom: "-1px",
        height: "1px",
        background:
          "linear-gradient(90deg, transparent, rgba(34, 211, 238, 0.4), rgba(167, 139, 250, 0.22), transparent)",
        pointerEvents: "none",
      }}
    >
      <Tooltip label="Voltar ao menu principal" hasArrow openDelay={400}>
        <Box
          as="button"
          onClick={reset}
          aria-label="Menu principal"
          borderRadius="12px"
          px={1}
          transition={TRANSITION}
          _hover={{ transform: "translateY(-1px)" }}
          _focusVisible={{ boxShadow: "focus", outline: "none" }}
        >
          <BrandLockup />
        </Box>
      </Tooltip>

      <HStack spacing={2.5}>
        <Pill tone="brand" icon={<ShieldIcon />}>
          Local first, LGPD by design
        </Pill>
        <Tooltip
          label={
            healthy
              ? `Backend respondendo em ${health!.device}. Modelo: ${health!.mock_mode ? "mock" : health!.pii}`
              : "Nenhuma resposta do backend local. Verifique se os containers estão no ar."
          }
          hasArrow
        >
          <Box>
            <Pill tone={healthy ? "ok" : "warn"} dot>
              {healthy
                ? `API ok, ${health!.device}, ${health!.mock_mode ? "mock" : health!.pii}`
                : "API offline"}
            </Pill>
          </Box>
        </Tooltip>
        <DocumentsMenu />
        <SettingsDrawer />
      </HStack>
    </Flex>
  );
}
