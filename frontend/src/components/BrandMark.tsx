import { useId } from "react";
import { Box, HStack, Text, type BoxProps } from "@chakra-ui/react";

/**
 * Marca do Xdiag Privacy.
 *
 * A familia Xdiag usa um X construido com tracos angulares e detalhe ciano
 * sobre azul quase preto. Aqui o X e mantido como assinatura da familia e o
 * centro, onde a marca-mae poe a cruz medica, recebe uma TARJA: o gesto que
 * define este produto. Le-se como "o X da Xdiag com o dado coberto", e ainda
 * funciona a 16px, onde qualquer detalhe fino desapareceria.
 *
 * Tres variantes ficam disponiveis para escolha da marca:
 *   x-bar  (padrao) X da familia Xdiag com tarja no cruzamento
 *   shield escudo com linhas de texto, a do meio tarjada
 *   doc    folha de documento com duas linhas tarjadas e selo X
 */

export type MarkVariant = "x-bar" | "shield" | "doc";

/**
 * Variante em uso no produto. Trocar aqui troca a marca no cabecalho e na tela
 * de entrada de uma vez so; o favicon fica em public/favicon.svg e precisa ser
 * trocado junto.
 */
export const MARK_VARIANT: MarkVariant = "x-bar";

export interface BrandMarkProps extends Omit<BoxProps, "children"> {
  size?: number | string;
  variant?: MarkVariant;
  /** Desenha a base arredondada escura atras do simbolo. */
  tile?: boolean;
  /** Halo ciano suave sob a marca. */
  glow?: boolean;
  label?: string;
}

export function BrandMark({
  size = 36,
  variant = MARK_VARIANT,
  tile = true,
  glow = true,
  label = "Xdiag Privacy",
  ...box
}: BrandMarkProps) {
  const uid = useId().replace(/:/g, "");
  const stroke = `s-${uid}`;
  const plate = `p-${uid}`;
  const tileGrad = `t-${uid}`;
  const soft = `g-${uid}`;

  return (
    <Box
      as="span"
      display="inline-flex"
      w={typeof size === "number" ? `${size}px` : size}
      h={typeof size === "number" ? `${size}px` : size}
      flexShrink={0}
      filter={glow ? "drop-shadow(0 4px 14px rgba(34, 211, 238, 0.28))" : undefined}
      {...box}
    >
      <svg viewBox="0 0 64 64" width="100%" height="100%" role="img" aria-label={label}>
        <defs>
          <linearGradient id={stroke} x1="12" y1="10" x2="52" y2="54" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#7dedfb" />
            <stop offset="0.52" stopColor="#22d3ee" />
            <stop offset="1" stopColor="#0891b2" />
          </linearGradient>
          <linearGradient id={plate} x1="8" y1="26" x2="56" y2="39" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#0c1c30" />
            <stop offset="1" stopColor="#050f1d" />
          </linearGradient>
          <linearGradient id={tileGrad} x1="4" y1="0" x2="60" y2="64" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#0d1c30" />
            <stop offset="1" stopColor="#030a16" />
          </linearGradient>
          <radialGradient id={soft} cx="0.5" cy="0.38" r="0.62">
            <stop offset="0" stopColor="#22d3ee" stopOpacity="0.26" />
            <stop offset="1" stopColor="#22d3ee" stopOpacity="0" />
          </radialGradient>
        </defs>

        {tile && (
          <>
            <rect x="0" y="0" width="64" height="64" rx="15" fill={`url(#${tileGrad})`} />
            <rect x="0" y="0" width="64" height="64" rx="15" fill={`url(#${soft})`} />
            <rect
              x="0.75"
              y="0.75"
              width="62.5"
              height="62.5"
              rx="14.25"
              fill="none"
              stroke="#22d3ee"
              strokeOpacity="0.22"
              strokeWidth="1.5"
            />
          </>
        )}

        {variant === "x-bar" && <XBar stroke={stroke} plate={plate} />}
        {variant === "shield" && <Shield stroke={stroke} plate={plate} />}
        {variant === "doc" && <Doc stroke={stroke} plate={plate} />}
      </svg>
    </Box>
  );
}

/** X da familia Xdiag com a tarja cobrindo o cruzamento. */
function XBar({ stroke, plate }: { stroke: string; plate: string }) {
  return (
    <>
      <g
        stroke={`url(#${stroke})`}
        strokeWidth="8.4"
        strokeLinecap="round"
        fill="none"
      >
        <path d="M15.5 14.5 L48.5 49.5" />
        <path d="M48.5 14.5 L15.5 49.5" />
      </g>
      {/* Tarja: chapa opaca por cima do X, com fio ciano para nao virar "buraco". */}
      <rect
        x="9"
        y="26.6"
        width="46"
        height="10.8"
        rx="5.4"
        fill={`url(#${plate})`}
        stroke="#22d3ee"
        strokeOpacity="0.9"
        strokeWidth="1.7"
      />
    </>
  );
}

/** Escudo com tres linhas de texto, a do meio tarjada. */
function Shield({ stroke, plate }: { stroke: string; plate: string }) {
  return (
    <>
      <path
        d="M32 7 L51 13.8 V31.5 C51 43.6 43.2 52.9 32 57 C20.8 52.9 13 43.6 13 31.5 V13.8 Z"
        fill="rgba(34, 211, 238, 0.07)"
        stroke={`url(#${stroke})`}
        strokeWidth="3.2"
        strokeLinejoin="round"
      />
      <rect x="21" y="23.5" width="22" height="3.4" rx="1.7" fill="#94a3b8" fillOpacity="0.55" />
      <rect
        x="18.5"
        y="30.3"
        width="27"
        height="7.6"
        rx="3.8"
        fill={`url(#${plate})`}
        stroke="#22d3ee"
        strokeOpacity="0.9"
        strokeWidth="1.6"
      />
      <rect x="21" y="41.4" width="16" height="3.4" rx="1.7" fill="#94a3b8" fillOpacity="0.55" />
    </>
  );
}

/** Folha de documento com duas linhas tarjadas e o X da Xdiag como selo. */
function Doc({ stroke, plate }: { stroke: string; plate: string }) {
  return (
    <>
      <path
        d="M17 10.5 H36 L47 21.5 V53.5 H17 Z"
        fill="rgba(34, 211, 238, 0.07)"
        stroke={`url(#${stroke})`}
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <path d="M36 10.5 V21.5 H47" fill="none" stroke={`url(#${stroke})`} strokeWidth="3" strokeLinejoin="round" />
      <rect x="23" y="28" width="18" height="3.2" rx="1.6" fill="#94a3b8" fillOpacity="0.5" />
      <rect
        x="22"
        y="34.6"
        width="20"
        height="6.4"
        rx="3.2"
        fill={`url(#${plate})`}
        stroke="#22d3ee"
        strokeOpacity="0.9"
        strokeWidth="1.5"
      />
      <rect x="23" y="44.6" width="13" height="3.2" rx="1.6" fill="#94a3b8" fillOpacity="0.5" />
    </>
  );
}

/**
 * Lockup completo: marca + nome + descritor. Usado no cabecalho.
 */
export function BrandLockup({
  variant = MARK_VARIANT,
  size = 38,
  subtitle = "Anonimização de documentos",
  ...box
}: { variant?: MarkVariant; size?: number; subtitle?: string } & Omit<BoxProps, "children">) {
  return (
    <HStack spacing={3} minW={0} {...(box as object)}>
      <BrandMark size={size} variant={variant} />
      <Box lineHeight="1.15" minW={0}>
        <Text
          fontSize="15px"
          fontWeight={650}
          color="slate.50"
          letterSpacing="-0.015em"
          whiteSpace="nowrap"
        >
          Xdiag{" "}
          <Box as="span" bgGradient="linear(to-r, brand.300, brand.500)" bgClip="text">
            Privacy
          </Box>
        </Text>
        <Text fontSize="2xs" color="slate.500" letterSpacing="0.04em" whiteSpace="nowrap">
          {subtitle}
        </Text>
      </Box>
    </HStack>
  );
}
