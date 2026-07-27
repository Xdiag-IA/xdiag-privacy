import {
  Box,
  Button,
  Center,
  Heading,
  HStack,
  SimpleGrid,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useCallback, useRef, useState } from "react";
import { useRedactionStore } from "../stores/redactionStore";
import { BrandMark } from "./BrandMark";
import { TRANSITION } from "../theme";

const ACCEPTED = "image/png,image/jpeg,image/jpg,image/webp,application/pdf";

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.9">
      <path d="M12 3.5v11m0-11 4.2 4.2M12 3.5 7.8 7.7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 15.5v3a2.5 2.5 0 0 0 2.5 2.5h11a2.5 2.5 0 0 0 2.5-2.5v-3" strokeLinecap="round" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5l-8-3z" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CpuIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="5" y="5" width="14" height="14" rx="3" />
      <rect x="9" y="9" width="6" height="6" rx="1.5" />
      <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" strokeLinecap="round" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

interface FeatureProps {
  icon: React.ReactNode;
  step: string;
  title: string;
  description: string;
}

function Feature({ icon, step, title, description }: FeatureProps) {
  return (
    <Box
      p={5}
      borderRadius="16px"
      bg="surface.panel"
      border="1px solid"
      borderColor="line.subtle"
      boxShadow="card"
      h="100%"
      position="relative"
      overflow="hidden"
      transition={TRANSITION}
      _hover={{
        borderColor: "line.brand",
        transform: "translateY(-3px)",
        boxShadow: "0 1px 0 0 rgba(255,255,255,0.05) inset, 0 26px 50px -28px rgba(2,6,23,1)",
      }}
    >
      {/* Numero do passo, grande e quase invisivel, dando profundidade ao card. */}
      <Text
        position="absolute"
        top="-6px"
        right="10px"
        fontSize="72px"
        fontWeight={800}
        color="whiteAlpha.50"
        lineHeight={1}
        pointerEvents="none"
        userSelect="none"
      >
        {step}
      </Text>
      <HStack mb={3.5} spacing={3} position="relative">
        <Center
          w="38px"
          h="38px"
          borderRadius="11px"
          bg="rgba(34, 211, 238, 0.1)"
          color="brand.300"
          border="1px solid"
          borderColor="line.brand"
          flexShrink={0}
        >
          {icon}
        </Center>
        <Heading as="h3" size="sm" color="slate.50" fontWeight={600} fontSize="15px">
          {title}
        </Heading>
      </HStack>
      <Text fontSize="13px" color="slate.400" lineHeight={1.65} position="relative">
        {description}
      </Text>
    </Box>
  );
}

export function UploadZone() {
  const addFiles = useRedactionStore((s) => s.addFiles);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const files = Array.from(e.dataTransfer.files ?? []);
      if (files.length) addFiles(files);
    },
    [addFiles],
  );

  const onPick = () => inputRef.current?.click();

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) addFiles(files);
    e.target.value = "";
  };

  const onPaste = useCallback(
    (e: React.ClipboardEvent<HTMLDivElement>) => {
      const items = Array.from(e.clipboardData?.items ?? []);
      const files = items
        .filter((it) => it.kind === "file" && it.type.startsWith("image/"))
        .map((it) => it.getAsFile())
        .filter((f): f is File => !!f);
      if (files.length) {
        e.preventDefault();
        addFiles(files);
      }
    },
    [addFiles],
  );

  return (
    <Center w="100%" minH="100%" px={{ base: 5, md: 8 }} py={{ base: 8, md: 14 }}>
      <Stack spacing={{ base: 9, md: 12 }} maxW="900px" w="100%" align="stretch">
        <VStack spacing={4} textAlign="center">
          <BrandMark size={64} mb={1} />
          <Text
            fontSize="2xs"
            color="brand.300"
            textTransform="uppercase"
            letterSpacing="0.16em"
            fontWeight={600}
          >
            Xdiag Privacy
          </Text>
          <Heading
            as="h1"
            fontSize={{ base: "28px", md: "38px" }}
            color="slate.50"
            fontWeight={700}
            letterSpacing="-0.03em"
            lineHeight={1.12}
            maxW="700px"
          >
            Anonimização visual de{" "}
            <Box as="span" bgGradient="linear(to-r, brand.200, brand.400, accent.400)" bgClip="text">
              documentos médicos
            </Box>
          </Heading>
          <Text color="slate.400" fontSize={{ base: "sm", md: "md" }} maxW="620px" lineHeight={1.65}>
            Detecta e oculta automaticamente dados pessoais em laudos, fichas, prescrições
            e prontuários brasileiros. 100 por cento local, LGPD por arquitetura.
          </Text>
        </VStack>

        <Box
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={onPick}
          onPaste={onPaste}
          tabIndex={0}
          cursor="pointer"
          position="relative"
          overflow="hidden"
          borderRadius="24px"
          border="1.5px dashed"
          borderColor={dragOver ? "brand.400" : "line.medium"}
          bg={dragOver ? "rgba(34, 211, 238, 0.06)" : "surface.panel"}
          boxShadow={dragOver ? "glow" : "card"}
          transform={dragOver ? "scale(1.005)" : "scale(1)"}
          transition={TRANSITION}
          px={{ base: 6, md: 10 }}
          py={{ base: 10, md: 14 }}
          textAlign="center"
          role="button"
          aria-label="Área de upload"
          _hover={{ borderColor: "line.brand", bg: "rgba(34, 211, 238, 0.04)" }}
          _focusVisible={{ borderColor: "brand.400", boxShadow: "focus", outline: "none" }}
          sx={{
            // Brilho ciano preso ao topo da area, para ela nao parecer um
            // retangulo vazio quando nao ha nada solto sobre ela.
            "&::before": {
              content: '""',
              position: "absolute",
              inset: 0,
              background:
                "radial-gradient(60% 55% at 50% 0%, rgba(34, 211, 238, 0.1), transparent 70%)",
              opacity: dragOver ? 1 : 0.55,
              transition: "opacity 200ms ease",
              pointerEvents: "none",
            },
          }}
        >
          <VStack spacing={6} position="relative">
            <Center
              w="76px"
              h="76px"
              borderRadius="full"
              bg="rgba(34, 211, 238, 0.08)"
              color="brand.300"
              border="1px solid"
              borderColor="line.brand"
              boxShadow={dragOver ? "0 0 0 8px rgba(34, 211, 238, 0.08)" : "0 0 0 0 rgba(34, 211, 238, 0)"}
              transition={TRANSITION}
            >
              <UploadIcon />
            </Center>
            <VStack spacing={2.5}>
              <Heading size="md" color="slate.50" fontSize="20px" fontWeight={650}>
                {dragOver ? "Solte para anonimizar" : "Arraste um documento aqui"}
              </Heading>
              <Text color="slate.400" fontSize="sm">
                PNG, JPG, WEBP ou PDF de até 20 páginas. Limite de 20 MB.
              </Text>
              <HStack spacing={3} flexWrap="wrap" justify="center">
                <Text color="slate.500" fontSize="xs">
                  Vários arquivos de uma vez
                </Text>
                <Box w="3px" h="3px" borderRadius="full" bg="slate.700" />
                <Text color="slate.500" fontSize="xs">
                  Ou cole uma imagem com Ctrl+V
                </Text>
              </HStack>
            </VStack>
            <Button
              size="lg"
              onClick={(e) => {
                e.stopPropagation();
                onPick();
              }}
              px={9}
              h="48px"
              fontSize="15px"
            >
              Selecionar arquivo
            </Button>
          </VStack>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            onChange={onChange}
            multiple
            hidden
          />
        </Box>

        <VStack spacing={5} align="stretch">
          <HStack spacing={3} align="center">
            <Text
              fontSize="2xs"
              color="slate.500"
              textTransform="uppercase"
              letterSpacing="0.14em"
              fontWeight={600}
              whiteSpace="nowrap"
            >
              Como funciona
            </Text>
            <Box flex={1} h="1px" bg="line.subtle" />
          </HStack>
          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
            <Feature
              step="01"
              icon={<ShieldIcon />}
              title="100 por cento local"
              description="Tudo roda no seu computador, dentro de containers Docker. Nenhuma chamada externa em runtime, nenhum dado sai da máquina. LGPD por arquitetura."
            />
            <Feature
              step="02"
              icon={<CpuIcon />}
              title="OCR e IA especializada"
              description="PaddleOCR lê o documento em português e o modelo OpenMed identifica nome, CPF, CNPJ, RG, telefone, email, endereço, data de nascimento, idade, CRM e prontuário."
            />
            <Feature
              step="03"
              icon={<EyeIcon />}
              title="Auditoria visual"
              description="Cada entidade detectada aparece com retângulo colorido sobre o documento original. Você vê e revisa antes de exportar a versão anonimizada."
            />
          </SimpleGrid>

          <Box
            mt={1}
            p={4}
            pl={5}
            borderRadius="14px"
            bg="surface.panel"
            border="1px solid"
            borderColor="line.subtle"
            position="relative"
            overflow="hidden"
            _before={{
              content: '""',
              position: "absolute",
              left: 0,
              top: "14px",
              bottom: "14px",
              width: "2px",
              borderRadius: "full",
              bgGradient: "linear(to-b, brand.300, accent.400)",
            }}
          >
            <Text fontSize="xs" color="slate.500" lineHeight={1.75}>
              <Box as="strong" color="slate.300" fontWeight={600}>
                Aviso LGPD:{" "}
              </Box>
              esta ferramenta auxilia o tratamento de dados pessoais sensíveis e não
              substitui DPO, encarregado, política de privacidade nem revisão jurídica.
              O operador permanece responsável pelo uso legítimo, retenção, registro
              de operações (Art. 37 da LGPD) e descarte seguro.
            </Text>
          </Box>
        </VStack>
      </Stack>
    </Center>
  );
}
