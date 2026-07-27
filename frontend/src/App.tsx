import { Alert, AlertIcon, Box, Flex, Grid, Text } from "@chakra-ui/react";
import { AppHeader } from "./components/AppHeader";
import { UploadZone } from "./components/UploadZone";
import { DocumentViewer } from "./components/DocumentViewer";
import { RedactionHeader } from "./components/RedactionHeader";
import { EntityList } from "./components/EntityList";
import { ControlsPanel } from "./components/ControlsPanel";
import { ProgressTracker } from "./components/ProgressTracker";
import { unmappedCount, useRedactionStore } from "./stores/redactionStore";

export default function App() {
  const file = useRedactionStore((s) => s.file);
  const status = useRedactionStore((s) => s.status);
  const error = useRedactionStore((s) => s.error);
  const unmapped = useRedactionStore((s) => unmappedCount(s.entities));

  return (
    <Flex direction="column" h="100vh" w="100vw" bg="slate.950">
      <AppHeader />
      <ProgressTracker />

      {!file && status === "idle" && (
        <Box flex={1} overflow="auto">
          <UploadZone />
        </Box>
      )}

      {file && (
        <Grid
          flex={1}
          templateColumns={{ base: "1fr", md: "minmax(0, 6fr) minmax(360px, 4fr)" }}
          h="100%"
          minH={0}
        >
          <Box minH={0} borderRight="1px solid" borderColor="slate.800">
            <DocumentViewer />
          </Box>
          <Flex direction="column" minH={0} bg="slate.900">
            <RedactionHeader />
            <Box flex={1} overflowY="auto">
              {unmapped > 0 && !error && (
                <Box p={4} pb={0}>
                  <Alert status="error" variant="left-accent" borderRadius="md">
                    <AlertIcon />
                    <Box>
                      <Text fontWeight={600} fontSize="sm">
                        {unmapped}{" "}
                        {unmapped === 1
                          ? "entidade detectada no texto nao foi localizada na imagem"
                          : "entidades detectadas no texto nao foram localizadas na imagem"}
                      </Text>
                      <Text fontSize="xs" mt={1}>
                        O export esta bloqueado: o dado existe no documento mas
                        nenhuma regiao foi mapeada para tarja. Reprocesse com
                        outro limite de confianca ou revise o documento antes
                        de exportar.
                      </Text>
                    </Box>
                  </Alert>
                </Box>
              )}
              {error ? (
                <Box p={4}>
                  <Alert status="error" variant="left-accent" borderRadius="md">
                    <AlertIcon />
                    <Box>
                      <Text fontWeight={600} fontSize="sm">
                        Falha no processamento
                      </Text>
                      <Text fontSize="xs" mt={1}>
                        {error}
                      </Text>
                    </Box>
                  </Alert>
                </Box>
              ) : (
                <EntityList />
              )}
            </Box>
            <Box
              borderTop="1px solid"
              borderColor="slate.800"
              bg="slate.950"
            >
              <ControlsPanel />
            </Box>
          </Flex>
        </Grid>
      )}
    </Flex>
  );
}
