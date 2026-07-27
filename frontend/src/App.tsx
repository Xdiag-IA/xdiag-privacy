import { Box, Flex, Grid, HStack, Text } from "@chakra-ui/react";
import { AppHeader } from "./components/AppHeader";
import { UploadZone } from "./components/UploadZone";
import { DocumentViewer } from "./components/DocumentViewer";
import { RedactionHeader } from "./components/RedactionHeader";
import { EntityList } from "./components/EntityList";
import { ControlsPanel } from "./components/ControlsPanel";
import { ProgressTracker } from "./components/ProgressTracker";
import { unmappedCountAll, useRedactionStore } from "./stores/redactionStore";

function AlertIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3.2 1.8 20.8h20.4z" strokeLinejoin="round" />
      <path d="M12 9.6v4.6M12 17.6h.01" strokeLinecap="round" />
    </svg>
  );
}

/**
 * Aviso de risco. Substitui o Alert padrao do Chakra para acompanhar o resto
 * da interface: vidro escuro, fio vermelho a esquerda e halo suave. Vermelho
 * aqui e sempre risco real, nunca decoracao.
 */
function RiskNotice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box
      m={4}
      mb={0}
      p={4}
      pl={5}
      borderRadius="14px"
      bg="rgba(244, 63, 94, 0.08)"
      border="1px solid"
      borderColor="rgba(244, 63, 94, 0.35)"
      boxShadow="0 18px 44px -32px rgba(244, 63, 94, 0.9)"
      position="relative"
      overflow="hidden"
      _before={{
        content: '""',
        position: "absolute",
        left: 0,
        top: 0,
        bottom: 0,
        width: "2px",
        bg: "#f43f5e",
      }}
    >
      <HStack spacing={2.5} mb={1.5} color="#fda4af">
        <AlertIcon />
        <Text fontWeight={700} fontSize="13px" letterSpacing="-0.01em">
          {title}
        </Text>
      </HStack>
      <Text fontSize="xs" color="slate.400" lineHeight={1.65}>
        {children}
      </Text>
    </Box>
  );
}

export default function App() {
  const file = useRedactionStore((s) => s.file);
  const status = useRedactionStore((s) => s.status);
  const error = useRedactionStore((s) => s.error);
  const unmapped = useRedactionStore((s) => unmappedCountAll(s.pages));

  return (
    <Flex direction="column" h="100vh" w="100%" overflow="hidden">
      <AppHeader />
      <ProgressTracker />

      {!file && status === "idle" && (
        <Box flex={1} overflow="auto" minH={0}>
          <UploadZone />
        </Box>
      )}

      {file && (
        <Grid
          flex={1}
          templateColumns={{ base: "1fr", md: "minmax(0, 6fr) minmax(380px, 4fr)" }}
          minH={0}
        >
          <Box minH={0} borderRight="1px solid" borderColor="line.subtle" position="relative">
            <DocumentViewer />
          </Box>

          <Flex
            direction="column"
            minH={0}
            bg="rgba(8, 14, 28, 0.6)"
            backdropFilter="blur(20px)"
          >
            <RedactionHeader />
            <Box flex={1} overflowY="auto" minH={0}>
              {unmapped > 0 && !error && (
                <RiskNotice
                  title={`${unmapped} ${
                    unmapped === 1
                      ? "entidade detectada no texto não foi localizada na imagem"
                      : "entidades detectadas no texto não foram localizadas na imagem"
                  }`}
                >
                  O export está bloqueado: o dado existe no documento mas nenhuma
                  região foi mapeada para tarja. Reprocesse com outro limite de
                  confiança ou revise o documento antes de exportar.
                </RiskNotice>
              )}
              {error ? (
                <RiskNotice title="Falha no processamento">{error}</RiskNotice>
              ) : (
                <EntityList />
              )}
            </Box>
            <Box borderTop="1px solid" borderColor="line.subtle" bg="rgba(2, 6, 23, 0.65)" flexShrink={0}>
              <ControlsPanel />
            </Box>
          </Flex>
        </Grid>
      )}
    </Flex>
  );
}
