import {
  Box,
  Button,
  Divider,
  HStack,
  Slider,
  SliderFilledTrack,
  SliderThumb,
  SliderTrack,
  Stack,
  Switch,
  Text,
  Tooltip,
  useToast,
} from "@chakra-ui/react";
import { useCallback, useState } from "react";
import {
  fullDeidentifiedText,
  unmappedCountAll,
  useRedactionStore,
} from "../stores/redactionStore";
import { buildFilename, getWritableOutputDir, useSettingsStore } from "../stores/settingsStore";

function ImageIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.9">
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <circle cx="8.5" cy="9.5" r="1.6" />
      <path d="m4 17 4.5-4.5 3.5 3.5 3-3L20 17" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TextFileIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.9">
      <path d="M14 3H6.5A2.5 2.5 0 0 0 4 5.5v13A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5V9z" strokeLinejoin="round" />
      <path d="M14 3v6h6M8.5 13h7M8.5 16.5h4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Titulo de secao do painel. */
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

export function ControlsPanel() {
  const toast = useToast();
  const showOriginal = useRedactionStore((s) => s.showOriginalText);
  const setShowOriginal = useRedactionStore((s) => s.setShowOriginal);
  const threshold = useRedactionStore((s) => s.threshold);
  const setThreshold = useRedactionStore((s) => s.setThreshold);
  const reset = useRedactionStore((s) => s.reset);
  const reprocessActive = useRedactionStore((s) => s.reprocessActive);
  const file = useRedactionStore((s) => s.file);
  const status = useRedactionStore((s) => s.status);
  const entities = useRedactionStore((s) => s.entities);
  const dims = useRedactionStore((s) => s.imageDimensions);
  const imageUrl = useRedactionStore((s) => s.imageUrl);
  const fileName = useRedactionStore((s) => s.fileName);
  const pages = useRedactionStore((s) => s.pages);
  const excludedIndices = useRedactionStore((s) => s.excludedEntityIndices);
  const manualBoxes = useRedactionStore((s) => s.manualBoxes);

  const filenameTemplate = useSettingsStore((s) => s.filenameTemplate);
  const defaultExportFormat = useSettingsStore((s) => s.defaultExportFormat);

  const [confirmingReveal, setConfirmingReveal] = useState(false);

  const saveOrDownload = useCallback(
    async (blob: Blob, filename: string) => {
      const dir = await getWritableOutputDir();
      if (dir) {
        try {
          const fileHandle = await dir.getFileHandle(filename, { create: true });
          const writable = await fileHandle.createWritable();
          await writable.write(blob);
          await writable.close();
          toast({
            title: "Arquivo salvo",
            description: `${dir.name}/${filename}`,
            status: "success",
            duration: 3000,
          });
          return;
        } catch {
          // escrita na pasta configurada falhou (removida, sem espaco etc);
          // cai para o download normal do navegador em vez de travar o export.
        }
      }
      triggerDownload(blob, filename);
    },
    [toast],
  );

  const onReveal = useCallback(
    (next: boolean) => {
      if (next && !confirmingReveal) {
        setConfirmingReveal(true);
        toast({
          title: "Confirme exibir texto original",
          description:
            "Esta ação expõe dados sensíveis na interface. Use somente em ambiente controlado.",
          status: "warning",
          duration: 4000,
          isClosable: true,
        });
        return;
      }
      setShowOriginal(next);
      setConfirmingReveal(false);
      if (file && next) {
        // re run with reveal=true so the API returns original text
        void reprocessActive({ reveal: true });
      }
    },
    [confirmingReveal, setShowOriginal, file, reprocessActive, toast],
  );

  const onThresholdCommit = useCallback(
    (v: number) => {
      setThreshold(v);
      if (file) void reprocessActive();
    },
    [setThreshold, file, reprocessActive],
  );

  const exportImage = useCallback(async () => {
    if (!imageUrl || !dims) return;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = imageUrl;
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("falha ao carregar imagem"));
    });
    const canvas = document.createElement("canvas");
    canvas.width = dims.w;
    canvas.height = dims.h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(img, 0, 0, dims.w, dims.h);
    ctx.fillStyle = "#000000";
    for (let i = 0; i < entities.length; i++) {
      if (excludedIndices.has(i)) continue;
      const e = entities[i];
      for (const bbox of e.bboxes) {
        ctx.beginPath();
        ctx.moveTo(bbox[0][0], bbox[0][1]);
        ctx.lineTo(bbox[1][0], bbox[1][1]);
        ctx.lineTo(bbox[2][0], bbox[2][1]);
        ctx.lineTo(bbox[3][0], bbox[3][1]);
        ctx.closePath();
        ctx.fill();
      }
    }
    // Areas marcadas manualmente (falso negativo do modelo) tambem viram
    // retangulo preto solido no export, igual as detectadas automaticamente.
    for (const box of manualBoxes) {
      const bbox = box.bbox;
      ctx.beginPath();
      ctx.moveTo(bbox[0][0], bbox[0][1]);
      ctx.lineTo(bbox[1][0], bbox[1][1]);
      ctx.lineTo(bbox[2][0], bbox[2][1]);
      ctx.lineTo(bbox[3][0], bbox[3][1]);
      ctx.closePath();
      ctx.fill();
    }
    canvas.toBlob((blob) => {
      if (!blob) return;
      void saveOrDownload(blob, buildFilename(filenameTemplate, baseName(fileName), "png"));
    }, "image/png");
  }, [imageUrl, dims, entities, fileName, excludedIndices, manualBoxes, saveOrDownload, filenameTemplate]);

  const deidentifiedText = fullDeidentifiedText(pages);

  const exportText = useCallback(() => {
    const blob = new Blob([deidentifiedText], { type: "text/plain;charset=utf-8" });
    void saveOrDownload(blob, buildFilename(filenameTemplate, baseName(fileName), "txt"));
  }, [deidentifiedText, fileName, saveOrDownload, filenameTemplate]);

  // Bloqueio fail-closed: com qualquer entidade sem regiao mapeada (em
  // QUALQUER pagina), o arquivo exportado exporia o dado.
  const unmapped = unmappedCountAll(pages);
  const multiPage = pages.length > 1;
  const exportsDisabled =
    (status !== "done" && status !== "animating") || unmapped > 0;
  // Export de imagem multipagina so sera possivel via export no servidor;
  // exportar pagina a pagina no navegador convida a esquecer paginas.
  const imageExportDisabled = exportsDisabled || multiPage;
  const unmappedHint =
    unmapped > 0
      ? `Existem ${unmapped} entidades sem área mapeada na imagem. Revise-as antes de exportar.`
      : multiPage
        ? "Documento com várias páginas: o export de imagem será feito pelo servidor no próximo bloco. Use o export de texto."
        : null;

  return (
    <Box px={5} py={4}>
      <Stack spacing={5}>
        <Stack spacing={3.5}>
          <SectionLabel>Controles</SectionLabel>

          <HStack justify="space-between" align="flex-start" gap={4}>
            <Box minW={0}>
              <Text fontSize="13px" color="slate.100" fontWeight={600}>
                Mostrar texto original
              </Text>
              <Text fontSize="2xs" color="slate.500" mt={0.5} lineHeight={1.5}>
                Apenas para auditoria, com confirmação.
              </Text>
            </Box>
            <Switch
              isChecked={showOriginal}
              onChange={(e) => onReveal(e.target.checked)}
              flexShrink={0}
              mt={0.5}
            />
          </HStack>

          <Box>
            <HStack justify="space-between" mb={2}>
              <Text fontSize="13px" color="slate.100" fontWeight={600}>
                Limite de confiança
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
                  {threshold.toFixed(2)}
                </Text>
              </Box>
            </HStack>
            <Slider
              min={0}
              max={1}
              step={0.05}
              value={threshold}
              onChange={(v) => setThreshold(v)}
              onChangeEnd={onThresholdCommit}
              aria-label="Limite de confiança"
            >
              <SliderTrack h="5px" borderRadius="full">
                <SliderFilledTrack />
              </SliderTrack>
              <SliderThumb boxSize="15px" />
            </Slider>
            <Text fontSize="2xs" color="slate.500" mt={2} lineHeight={1.6}>
              Aplica-se apenas às detecções do modelo sem validação. CPF, CNPJ
              e CNS validados e números suspeitos são tarjados sempre.
            </Text>
          </Box>
        </Stack>

        <Divider />

        <Stack spacing={3}>
          <SectionLabel>Exportar anonimizado</SectionLabel>
          <HStack spacing={2.5}>
            <Tooltip
              label={unmappedHint ?? "PNG com regiões preenchidas em preto"}
              hasArrow
            >
              <Box flex={1}>
                <Button
                  size="sm"
                  w="100%"
                  variant={defaultExportFormat === "txt" ? "outline" : "solid"}
                  leftIcon={<ImageIcon />}
                  onClick={exportImage}
                  isDisabled={imageExportDisabled}
                >
                  Imagem
                </Button>
              </Box>
            </Tooltip>
            <Tooltip
              label={
                unmappedHint ??
                (excludedIndices.size > 0
                  ? "TXT com placeholders por entidade. Itens marcados como 'não anonimizar' ainda aparecem redigidos aqui; a exceção manual vale só para a imagem."
                  : "TXT com placeholders por entidade")
              }
              hasArrow
            >
              <Box flex={1}>
                <Button
                  size="sm"
                  w="100%"
                  variant={defaultExportFormat === "txt" ? "solid" : "outline"}
                  leftIcon={<TextFileIcon />}
                  onClick={exportText}
                  isDisabled={exportsDisabled || !deidentifiedText}
                >
                  Texto
                </Button>
              </Box>
            </Tooltip>
          </HStack>
          {excludedIndices.size > 0 && (
            <Text fontSize="2xs" color="#fcd34d" lineHeight={1.6}>
              {excludedIndices.size}{" "}
              {excludedIndices.size === 1
                ? "entidade marcada para não ser anonimizada"
                : "entidades marcadas para não serem anonimizadas"}{" "}
              (aplica-se à imagem exportada).
            </Text>
          )}
          {manualBoxes.length > 0 && (
            <Text fontSize="2xs" color="#fcd34d" lineHeight={1.6}>
              {manualBoxes.length}{" "}
              {manualBoxes.length === 1
                ? "área adicionada manualmente será tarjada"
                : "áreas adicionadas manualmente serão tarjadas"}{" "}
              na imagem exportada.
            </Text>
          )}
          <Button size="sm" variant="ghost" onClick={reset} fontWeight={500}>
            Voltar ao menu principal
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function baseName(name: string): string {
  if (!name) return "";
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}
