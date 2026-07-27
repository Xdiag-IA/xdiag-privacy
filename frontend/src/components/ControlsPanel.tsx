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
import { useRedactionStore } from "../stores/redactionStore";

export function ControlsPanel() {
  const toast = useToast();
  const showOriginal = useRedactionStore((s) => s.showOriginalText);
  const setShowOriginal = useRedactionStore((s) => s.setShowOriginal);
  const threshold = useRedactionStore((s) => s.threshold);
  const setThreshold = useRedactionStore((s) => s.setThreshold);
  const reset = useRedactionStore((s) => s.reset);
  const reupload = useRedactionStore((s) => s.uploadFile);
  const file = useRedactionStore((s) => s.file);
  const status = useRedactionStore((s) => s.status);
  const entities = useRedactionStore((s) => s.entities);
  const dims = useRedactionStore((s) => s.imageDimensions);
  const imageUrl = useRedactionStore((s) => s.imageUrl);
  const fileName = useRedactionStore((s) => s.fileName);
  const deidentifiedText = useRedactionStore((s) => s.deidentifiedText);
  const isSynthetic = useRedactionStore((s) => s.isSynthetic);

  const [confirmingReveal, setConfirmingReveal] = useState(false);

  const onReveal = useCallback(
    (next: boolean) => {
      if (next && !confirmingReveal) {
        setConfirmingReveal(true);
        toast({
          title: "Confirme exibir texto original",
          description:
            "Esta acao expoe dados sensiveis na interface. Use somente em ambiente controlado.",
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
        void reupload(file, { isSynthetic });
      }
    },
    [confirmingReveal, setShowOriginal, file, reupload, toast, isSynthetic],
  );

  const onThresholdCommit = useCallback(
    (v: number) => {
      setThreshold(v);
      if (file) void reupload(file, { isSynthetic });
    },
    [setThreshold, file, reupload, isSynthetic],
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
    for (const e of entities) {
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
    canvas.toBlob((blob) => {
      if (!blob) return;
      triggerDownload(blob, replaceExt(fileName, "anonimizado.png"));
    }, "image/png");
  }, [imageUrl, dims, entities, fileName]);

  const exportText = useCallback(() => {
    const blob = new Blob([deidentifiedText], { type: "text/plain;charset=utf-8" });
    triggerDownload(blob, replaceExt(fileName, "anonimizado.txt"));
  }, [deidentifiedText, fileName]);

  const exportsDisabled = status !== "done" && status !== "animating";

  return (
    <Box px={5} py={4}>
      <Stack spacing={4}>
        <Stack spacing={2}>
          <Text
            textTransform="uppercase"
            fontSize="xs"
            color="slate.500"
            letterSpacing="0.08em"
          >
            Controles
          </Text>

          <HStack justify="space-between">
            <Box>
              <Text fontSize="sm" color="slate.100" fontWeight={500}>
                Mostrar texto original
              </Text>
              <Text fontSize="xs" color="slate.500">
                Apenas para auditoria, com confirmacao.
              </Text>
            </Box>
            <Switch
              colorScheme="redaction"
              isChecked={showOriginal}
              onChange={(e) => onReveal(e.target.checked)}
            />
          </HStack>

          <Box>
            <HStack justify="space-between" mb={1}>
              <Text fontSize="sm" color="slate.100" fontWeight={500}>
                Limite de confianca
              </Text>
              <Text fontFamily="mono" fontSize="sm" color="redaction.300">
                {threshold.toFixed(2)}
              </Text>
            </HStack>
            <Slider
              colorScheme="redaction"
              min={0}
              max={1}
              step={0.05}
              value={threshold}
              onChange={(v) => setThreshold(v)}
              onChangeEnd={onThresholdCommit}
            >
              <SliderTrack bg="slate.800">
                <SliderFilledTrack />
              </SliderTrack>
              <SliderThumb />
            </Slider>
            <Text fontSize="xs" color="slate.500" mt={1}>
              Entidades com score abaixo deste valor sao descartadas.
            </Text>
          </Box>
        </Stack>

        <Divider borderColor="slate.800" />

        <Stack spacing={2}>
          <Text
            textTransform="uppercase"
            fontSize="xs"
            color="slate.500"
            letterSpacing="0.08em"
          >
            Exportar
          </Text>
          <HStack>
            <Tooltip label="PNG com regioes preenchidas em preto" hasArrow>
              <Button
                size="sm"
                onClick={exportImage}
                isDisabled={exportsDisabled}
              >
                Imagem anonimizada
              </Button>
            </Tooltip>
            <Tooltip label="TXT com placeholders por entidade" hasArrow>
              <Button
                size="sm"
                variant="outline"
                colorScheme="redaction"
                onClick={exportText}
                isDisabled={exportsDisabled || !deidentifiedText}
              >
                Texto anonimizado
              </Button>
            </Tooltip>
          </HStack>
          <Button size="sm" variant="ghost" colorScheme="gray" onClick={reset}>
            Trocar documento
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

function replaceExt(name: string, suffix: string): string {
  if (!name) return suffix;
  const dot = name.lastIndexOf(".");
  const base = dot > 0 ? name.slice(0, dot) : name;
  return `${base}.${suffix}`;
}
