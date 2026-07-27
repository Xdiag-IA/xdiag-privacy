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

const ACCEPTED = "image/png,image/jpeg,image/jpg,image/webp,application/pdf";

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3v12m0-12 4 4m-4-4-4 4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" strokeLinecap="round" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5l-8-3z" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CpuIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="5" y="5" width="14" height="14" rx="2" />
      <rect x="9" y="9" width="6" height="6" rx="1" />
      <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" strokeLinecap="round" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

interface FeatureProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function Feature({ icon, title, description }: FeatureProps) {
  return (
    <Box
      p={5}
      borderRadius="14px"
      bg="slate.900"
      border="1px solid"
      borderColor="slate.800"
      h="100%"
    >
      <HStack mb={3} spacing={3}>
        <Center
          w="40px"
          h="40px"
          borderRadius="10px"
          bg="redaction.900"
          color="redaction.300"
          border="1px solid"
          borderColor="redaction.800"
        >
          {icon}
        </Center>
        <Heading as="h3" size="sm" color="slate.50" fontWeight={600}>
          {title}
        </Heading>
      </HStack>
      <Text fontSize="sm" color="slate.400" lineHeight={1.6}>
        {description}
      </Text>
    </Box>
  );
}

export function UploadZone() {
  const upload = useRedactionStore((s) => s.uploadFile);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void upload(file);
    },
    [upload],
  );

  const onPick = () => inputRef.current?.click();

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    e.target.value = "";
  };

  return (
    <Center w="100%" minH="100%" px={6} py={10}>
      <Stack spacing={12} maxW="880px" w="100%" align="stretch">
        <VStack spacing={3} textAlign="center">
          <Heading
            as="h1"
            size="xl"
            color="slate.50"
            fontWeight={700}
            letterSpacing="-0.02em"
          >
            Anonimizacao visual de documentos medicos
          </Heading>
          <Text color="slate.400" fontSize="md" maxW="640px">
            Detecta e oculta automaticamente dados pessoais em laudos, fichas, prescricoes
            e prontuarios brasileiros. 100 por cento local, LGPD por arquitetura.
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
          cursor="pointer"
          borderRadius="20px"
          border="2px dashed"
          borderColor={dragOver ? "redaction.500" : "slate.700"}
          bg={dragOver ? "redaction.900" : "slate.900"}
          transition="all 200ms ease"
          p={12}
          textAlign="center"
          role="button"
          aria-label="Area de upload"
          _hover={{ borderColor: "redaction.500", bg: "slate.900" }}
        >
          <VStack spacing={5}>
            <Center
              w="72px"
              h="72px"
              borderRadius="full"
              bg="slate.800"
              color="redaction.400"
              border="1px solid"
              borderColor="redaction.800"
            >
              <UploadIcon />
            </Center>
            <VStack spacing={2}>
              <Heading size="md" color="slate.100">
                Arraste um documento aqui
              </Heading>
              <Text color="slate.400" fontSize="sm">
                PNG, JPG, WEBP ou PDF (primeira pagina). Limite de 20 MB.
              </Text>
            </VStack>
            <Button
              size="lg"
              colorScheme="redaction"
              onClick={(e) => {
                e.stopPropagation();
                onPick();
              }}
              px={8}
              fontWeight={600}
            >
              Selecionar arquivo
            </Button>
          </VStack>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            onChange={onChange}
            hidden
          />
        </Box>

        <VStack spacing={5} align="stretch">
          <Box textAlign="center">
            <Text
              fontSize="xs"
              color="slate.500"
              textTransform="uppercase"
              letterSpacing="0.12em"
              fontWeight={600}
            >
              Como funciona
            </Text>
          </Box>
          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
            <Feature
              icon={<ShieldIcon />}
              title="100 por cento local"
              description="Tudo roda no seu computador, dentro de containers Docker. Nenhuma chamada externa em runtime, nenhum dado sai da maquina. LGPD por arquitetura."
            />
            <Feature
              icon={<CpuIcon />}
              title="OCR e IA especializada"
              description="PaddleOCR le o documento em portugues e o modelo OpenMed identifica nome, CPF, CNPJ, RG, telefone, email, endereco, data de nascimento, idade, CRM e prontuario."
            />
            <Feature
              icon={<EyeIcon />}
              title="Auditoria visual"
              description="Cada entidade detectada aparece com retangulo colorido sobre o documento original. Voce ve e revisa antes de exportar a versao anonimizada."
            />
          </SimpleGrid>
          <Box
            mt={2}
            p={4}
            borderRadius="12px"
            bg="slate.900"
            border="1px solid"
            borderColor="slate.800"
          >
            <Text fontSize="xs" color="slate.500" lineHeight={1.7}>
              <strong style={{ color: "#cbd5e1" }}>Aviso LGPD: </strong>
              esta ferramenta auxilia o tratamento de dados pessoais sensiveis e nao
              substitui DPO, encarregado, politica de privacidade nem revisao juridica.
              O operador permanece responsavel pelo uso legitimo, retencao, registro
              de operacoes (Art. 37 da LGPD) e descarte seguro.
            </Text>
          </Box>
        </VStack>
      </Stack>
    </Center>
  );
}
