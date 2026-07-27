import {
  Box,
  Button,
  Divider,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
  DrawerOverlay,
  HStack,
  Input,
  Slider,
  SliderFilledTrack,
  SliderThumb,
  SliderTrack,
  Stack,
  Text,
  Tooltip,
  useDisclosure,
  useToast,
} from "@chakra-ui/react";
import { useCallback, useEffect, useState } from "react";
import { loadDirHandle } from "../lib/dirHandleStore";
import {
  buildFilename,
  DEFAULT_FILENAME_TEMPLATE,
  type ExportFormat,
  useSettingsStore,
} from "../stores/settingsStore";
import { TRANSITION } from "../theme";

function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.9">
      <circle cx="12" cy="12" r="3.2" />
      <path
        d="M19.4 13.5a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V19a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.55-1H4.6a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.55-1 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H10.6a1.7 1.7 0 0 0 1-1.55V4.6a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.09c.24.7.82 1.24 1.55 1.42H19.4Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Titulo de secao, mesmo padrao visual do ControlsPanel. */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <HStack spacing={3} align="center">
      <Text
        textTransform="uppercase"
        fontSize="2xs"
        color="slate.500"
        letterSpacing="0.14em"
        fontWeight={600}
        whiteSpace="nowrap"
      >
        {children}
      </Text>
      <Box flex={1} h="1px" bg="line.subtle" />
    </HStack>
  );
}

const FORMAT_OPTIONS: { value: ExportFormat; label: string }[] = [
  { value: "png", label: "Imagem" },
  { value: "txt", label: "Texto" },
  { value: "both", label: "Ambos" },
];

export function SettingsDrawer() {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  const defaultThreshold = useSettingsStore((s) => s.defaultThreshold);
  const setDefaultThreshold = useSettingsStore((s) => s.setDefaultThreshold);
  const defaultExportFormat = useSettingsStore((s) => s.defaultExportFormat);
  const setDefaultExportFormat = useSettingsStore((s) => s.setDefaultExportFormat);
  const filenameTemplate = useSettingsStore((s) => s.filenameTemplate);
  const setFilenameTemplate = useSettingsStore((s) => s.setFilenameTemplate);
  const outputDirName = useSettingsStore((s) => s.outputDirName);
  const fsAccessSupported = useSettingsStore((s) => s.fsAccessSupported);
  const chooseOutputDir = useSettingsStore((s) => s.chooseOutputDir);
  const clearOutputDir = useSettingsStore((s) => s.clearOutputDir);

  const [needsReconnect, setNeedsReconnect] = useState(false);
  // Id estavel so para a preview nao trocar de valor a cada re-render.
  const [previewId] = useState(() => Math.random().toString(36).slice(2, 8));

  const refreshPermission = useCallback(async () => {
    if (!fsAccessSupported) return;
    const handle = await loadDirHandle();
    if (!handle) {
      setNeedsReconnect(false);
      return;
    }
    const state = await handle.queryPermission({ mode: "readwrite" });
    setNeedsReconnect(state !== "granted");
  }, [fsAccessSupported]);

  useEffect(() => {
    if (isOpen) void refreshPermission();
  }, [isOpen, refreshPermission]);

  const onChooseDir = useCallback(async () => {
    try {
      await chooseOutputDir();
      setNeedsReconnect(false);
    } catch {
      // usuario cancelou o seletor de pasta; nao e um erro a reportar
    }
  }, [chooseOutputDir]);

  const onReconnect = useCallback(async () => {
    const handle = await loadDirHandle();
    if (!handle) return;
    const state = await handle.requestPermission({ mode: "readwrite" });
    if (state === "granted") {
      setNeedsReconnect(false);
      toast({ title: "Pasta reconectada", status: "success", duration: 2500 });
    }
  }, [toast]);

  const onClear = useCallback(async () => {
    await clearOutputDir();
    setNeedsReconnect(false);
  }, [clearOutputDir]);

  const preview = buildFilename(filenameTemplate || DEFAULT_FILENAME_TEMPLATE, "laudo_joao_silva", "png", previewId);
  const usesOriginalName = filenameTemplate.includes("{base}");

  return (
    <>
      <Tooltip label="Configurações" hasArrow openDelay={300}>
        <Box
          as="button"
          role="button"
          aria-label="Configurações"
          onClick={onOpen}
          w="34px"
          h="34px"
          borderRadius="10px"
          border="1px solid"
          borderColor="line.subtle"
          bg="surface.raised"
          color="slate.300"
          display="flex"
          alignItems="center"
          justifyContent="center"
          cursor="pointer"
          transition={TRANSITION}
          _hover={{ borderColor: "line.brand", color: "brand.200", transform: "translateY(-1px)" }}
          _active={{ transform: "translateY(0)" }}
        >
          <GearIcon />
        </Box>
      </Tooltip>

      <Drawer isOpen={isOpen} placement="right" onClose={onClose} size="sm">
        <DrawerOverlay />
        <DrawerContent bg="surface.overlay" backdropFilter="blur(16px)">
          <DrawerCloseButton />
          <DrawerHeader borderBottom="1px solid" borderColor="line.subtle" fontSize="md">
            Configurações
          </DrawerHeader>
          <DrawerBody py={5}>
            <Stack spacing={6}>
              <Stack spacing={3}>
                <SectionLabel>Pasta de saída</SectionLabel>
                {!fsAccessSupported ? (
                  <Text fontSize="xs" color="slate.500" lineHeight={1.6}>
                    Este navegador não suporta escolher uma pasta de saída fixa. Os
                    arquivos exportados continuam indo para a pasta de downloads
                    padrão.
                  </Text>
                ) : (
                  <>
                    <Text fontSize="sm" color="slate.200">
                      {outputDirName ? outputDirName : "Nenhuma, downloads vão para a pasta padrão do navegador"}
                    </Text>
                    <HStack spacing={2.5}>
                      <Button size="sm" variant="surface" onClick={onChooseDir}>
                        Escolher pasta
                      </Button>
                      {outputDirName && (
                        <Button size="sm" variant="ghost" onClick={onClear}>
                          Remover
                        </Button>
                      )}
                    </HStack>
                    {needsReconnect && (
                      <Box>
                        <Text fontSize="2xs" color="#fcd34d" mb={2} lineHeight={1.6}>
                          A permissão de escrita nessa pasta expirou. Reconecte para
                          continuar salvando ali.
                        </Text>
                        <Button size="sm" onClick={onReconnect}>
                          Reconectar pasta
                        </Button>
                      </Box>
                    )}
                  </>
                )}
              </Stack>

              <Divider />

              <Stack spacing={3}>
                <SectionLabel>Limite de confiança padrão</SectionLabel>
                <HStack justify="space-between" mb={-1}>
                  <Text fontSize="13px" color="slate.100" fontWeight={600}>
                    Novos documentos
                  </Text>
                  <Box
                    px={2}
                    py={0.5}
                    borderRadius="6px"
                    bg="rgba(34, 211, 238, 0.1)"
                    border="1px solid"
                    borderColor="line.brand"
                  >
                    <Text fontFamily="mono" fontSize="xs" color="brand.200" fontWeight={600}>
                      {defaultThreshold.toFixed(2)}
                    </Text>
                  </Box>
                </HStack>
                <Slider
                  min={0}
                  max={1}
                  step={0.05}
                  value={defaultThreshold}
                  onChange={setDefaultThreshold}
                  aria-label="Limite de confiança padrão"
                >
                  <SliderTrack h="5px" borderRadius="full">
                    <SliderFilledTrack />
                  </SliderTrack>
                  <SliderThumb boxSize="15px" />
                </Slider>
                <Text fontSize="2xs" color="slate.500" lineHeight={1.6}>
                  Aplica-se a documentos novos. Um documento já aberto usa o
                  limite ajustado no painel de controles dele.
                </Text>
              </Stack>

              <Divider />

              <Stack spacing={3}>
                <SectionLabel>Formato de export padrão</SectionLabel>
                <HStack spacing={2}>
                  {FORMAT_OPTIONS.map((opt) => (
                    <Button
                      key={opt.value}
                      size="sm"
                      flex={1}
                      variant={defaultExportFormat === opt.value ? "solid" : "outline"}
                      onClick={() => setDefaultExportFormat(opt.value)}
                    >
                      {opt.label}
                    </Button>
                  ))}
                </HStack>
                <Text fontSize="2xs" color="slate.500" lineHeight={1.6}>
                  Destaca o botão correspondente no painel de export. Os dois
                  formatos continuam disponíveis.
                </Text>
              </Stack>

              <Divider />

              <Stack spacing={2}>
                <SectionLabel>Nome do arquivo exportado</SectionLabel>
                <Input
                  size="sm"
                  value={filenameTemplate}
                  onChange={(e) => setFilenameTemplate(e.target.value)}
                  placeholder={DEFAULT_FILENAME_TEMPLATE}
                  fontFamily="mono"
                  fontSize="xs"
                />
                <Text fontSize="2xs" color="slate.500" lineHeight={1.6}>
                  Tokens disponíveis: <b>{"{id}"}</b> (código aleatório, sem
                  dado pessoal), <b>{"{date}"}</b> (aaaa-mm-dd), <b>{"{ext}"}</b>{" "}
                  (png/txt) e <b>{"{base}"}</b> (nome original do arquivo
                  enviado).
                </Text>
                <Text fontSize="2xs" color="brand.200" fontFamily="mono">
                  {preview}
                </Text>
                {usesOriginalName && (
                  <Box
                    px={2.5}
                    py={2}
                    borderRadius="8px"
                    bg="rgba(244, 63, 94, 0.08)"
                    border="1px solid"
                    borderColor="rgba(244, 63, 94, 0.28)"
                  >
                    <Text fontSize="2xs" color="#fda4af" lineHeight={1.6}>
                      <b>Atenção:</b> {"{base}"} reaproveita o nome do arquivo
                      enviado. Se o arquivo original já vier com o nome do
                      paciente (ex.: laudo_joao_silva.pdf), o arquivo
                      exportado sai com esse mesmo nome mesmo com o conteúdo
                      anonimizado. Prefira {"{id}"} e {"{date}"} se o nome do
                      arquivo também precisa ficar sem dado pessoal.
                    </Text>
                  </Box>
                )}
              </Stack>
            </Stack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </>
  );
}
