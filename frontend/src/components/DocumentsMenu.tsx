import {
  Badge,
  Box,
  Divider,
  HStack,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Spinner,
  Text,
  Tooltip,
} from "@chakra-ui/react";
import { useRef } from "react";
import { useRedactionStore } from "../stores/redactionStore";
import type { DocEntry } from "../stores/redactionStore";
import { TRANSITION } from "../theme";

const ACCEPTED = "image/png,image/jpeg,image/jpg,image/webp,application/pdf";

function GridIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.9">
      <rect x="3.5" y="3.5" width="7" height="7" rx="2" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="2" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="2" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="2" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
      <path d="M12 5v14M5 12h14" strokeLinecap="round" />
    </svg>
  );
}

function StatusDot({ status }: { status: DocEntry["status"] }) {
  if (status === "processing") return <Spinner size="xs" color="brand.300" flexShrink={0} />;
  const color =
    status === "done" ? "#34d399" : status === "error" ? "#f43f5e" : "#64748b";
  return (
    <Box
      w="7px"
      h="7px"
      borderRadius="full"
      bg={color}
      boxShadow={`0 0 8px ${color}`}
      flexShrink={0}
    />
  );
}

export function DocumentsMenu() {
  const documents = useRedactionStore((s) => s.documents);
  const activeDocId = useRedactionStore((s) => s.activeDocId);
  const selectDocument = useRedactionStore((s) => s.selectDocument);
  const addFiles = useRedactionStore((s) => s.addFiles);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) addFiles(files);
    e.target.value = "";
  };

  return (
    <>
      <Menu placement="bottom-end">
        <Tooltip label="Documentos desta sessão" hasArrow openDelay={300}>
          <MenuButton
            as={Box}
            role="button"
            aria-label="Documentos"
            position="relative"
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
            <GridIcon />
            {documents.length > 0 && (
              <Badge
                position="absolute"
                top="-5px"
                right="-5px"
                fontSize="9px"
                px={1.5}
                minW="17px"
                textAlign="center"
                borderRadius="full"
                bg="brand.400"
                color="#04121c"
                fontWeight={700}
                boxShadow="0 4px 12px -4px rgba(34, 211, 238, 0.8)"
              >
                {documents.length}
              </Badge>
            )}
          </MenuButton>
        </Tooltip>
        <MenuList minW="300px">
          <Text
            px={4}
            pb={2}
            fontSize="2xs"
            color="slate.500"
            textTransform="uppercase"
            letterSpacing="0.12em"
            fontWeight={600}
          >
            Documentos desta sessão
          </Text>
          {documents.length === 0 && (
            <Text px={4} py={2} fontSize="sm" color="slate.500">
              Nenhum documento ainda.
            </Text>
          )}
          {documents.map((doc) => {
            const active = doc.id === activeDocId;
            return (
              <MenuItem
                key={doc.id}
                onClick={() => selectDocument(doc.id)}
                bg={active ? "surface.active" : "transparent"}
                borderLeft="2px solid"
                borderColor={active ? "brand.400" : "transparent"}
              >
                <HStack spacing={2.5} w="100%" minW={0}>
                  <StatusDot status={doc.status} />
                  <Text
                    fontSize="sm"
                    color={active ? "slate.50" : "slate.200"}
                    fontWeight={active ? 600 : 400}
                    noOfLines={1}
                    flex={1}
                  >
                    {doc.fileName}
                  </Text>
                  {doc.status === "done" && (
                    <Text fontSize="2xs" color="slate.500" fontFamily="mono">
                      {doc.pages.reduce((a, p) => a + p.entities.length, 0)}
                    </Text>
                  )}
                </HStack>
              </MenuItem>
            );
          })}
          <Divider borderColor="line.subtle" my={2} />
          <MenuItem onClick={() => inputRef.current?.click()}>
            <HStack spacing={2.5} color="brand.300">
              <PlusIcon />
              <Text fontSize="sm" fontWeight={600}>
                Adicionar documento(s)
              </Text>
            </HStack>
          </MenuItem>
        </MenuList>
      </Menu>
      <input ref={inputRef} type="file" accept={ACCEPTED} onChange={onChange} multiple hidden />
    </>
  );
}
