import { extendTheme, type ThemeConfig } from "@chakra-ui/react";

const config: ThemeConfig = {
  initialColorMode: "dark",
  useSystemColorMode: false,
};

/**
 * Xdiag Privacy design tokens.
 *
 * A paleta segue a identidade da Xdiag (xdiag.com.br): base slate quase preta,
 * ciano como cor primaria e violeta como acento. Vermelho, ambar e verde ficam
 * reservados para SEMANTICA (risco, atencao, sucesso), nunca para marca. Antes
 * o vermelho era ao mesmo tempo cor de marca e cor de alerta, o que anulava o
 * sinal de perigo justamente na tela onde ele mais importa.
 */

// Curva de easing usada em toda a interface. Saida rapida, chegada suave.
export const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";
export const TRANSITION = `all 200ms ${EASE}`;

export const BRAND = {
  cyan: "#22d3ee",
  cyanDeep: "#06b6d4",
  cyanLight: "#67e8f9",
  violet: "#a78bfa",
  ink: "#020617",
} as const;

export const theme = extendTheme({
  config,
  fonts: {
    heading: `'Inter Variable', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`,
    body: `'Inter Variable', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`,
    mono: `'JetBrains Mono', 'Fira Code', 'Cascadia Code', Menlo, Consolas, monospace`,
  },
  fontSizes: {
    "2xs": "0.6875rem",
  },
  radii: {
    sm: "6px",
    md: "10px",
    lg: "14px",
    xl: "18px",
    "2xl": "24px",
  },
  shadows: {
    hairline: "inset 0 1px 0 0 rgba(255, 255, 255, 0.04)",
    card: "0 1px 0 0 rgba(255, 255, 255, 0.04) inset, 0 18px 40px -24px rgba(2, 6, 23, 0.95)",
    raised: "0 1px 0 0 rgba(255, 255, 255, 0.05) inset, 0 24px 60px -28px rgba(2, 6, 23, 1)",
    glow: "0 0 0 1px rgba(34, 211, 238, 0.28), 0 16px 44px -18px rgba(34, 211, 238, 0.45)",
    glowSoft: "0 12px 40px -20px rgba(34, 211, 238, 0.55)",
    focus: "0 0 0 3px rgba(34, 211, 238, 0.32)",
    danger: "0 0 0 3px rgba(244, 63, 94, 0.28)",
  },
  colors: {
    // Ciano da marca Xdiag. E a cor primaria de acao e de foco.
    brand: {
      50: "#ecfeff",
      100: "#cffafe",
      200: "#a5f3fc",
      300: "#67e8f9",
      400: "#22d3ee",
      500: "#06b6d4",
      600: "#0891b2",
      700: "#0e7490",
      800: "#155e75",
      900: "#164e63",
    },
    // Violeta de apoio, usado em destaques secundarios e no gradiente ambiente.
    accent: {
      50: "#f5f3ff",
      100: "#ede9fe",
      200: "#ddd6fe",
      300: "#c4b5fd",
      400: "#a78bfa",
      500: "#8b5cf6",
      600: "#7c3aed",
      700: "#6d28d9",
      800: "#5b21b6",
      900: "#4c1d95",
    },
    // Vermelho semantico: risco real (entidade nao mapeada, erro, exposicao).
    risk: {
      50: "#fff1f2",
      100: "#ffe4e6",
      200: "#fecdd3",
      300: "#fda4af",
      400: "#fb7185",
      500: "#f43f5e",
      600: "#e11d48",
      700: "#be123c",
      800: "#9f1239",
      900: "#881337",
    },
    slate: {
      50: "#f8fafc",
      100: "#f1f5f9",
      200: "#e2e8f0",
      300: "#cbd5e1",
      400: "#94a3b8",
      500: "#64748b",
      600: "#475569",
      700: "#334155",
      800: "#1e293b",
      900: "#0f172a",
      950: "#020617",
    },
    // Superficies do app. Painel e elevado sao translucidos: com o gradiente
    // ambiente atras, dao a sensacao de vidro sem custar nada em performance.
    surface: {
      canvas: "#020617",
      sunken: "#040a16",
      panel: "rgba(15, 23, 42, 0.72)",
      raised: "rgba(23, 33, 54, 0.78)",
      overlay: "rgba(10, 16, 28, 0.94)",
      hover: "rgba(148, 163, 184, 0.08)",
      active: "rgba(34, 211, 238, 0.1)",
    },
    line: {
      subtle: "rgba(148, 163, 184, 0.12)",
      medium: "rgba(148, 163, 184, 0.2)",
      strong: "rgba(148, 163, 184, 0.32)",
      brand: "rgba(34, 211, 238, 0.32)",
    },
  },
  styles: {
    global: {
      "html, body, #root": {
        height: "100%",
      },
      body: {
        bg: "surface.canvas",
        color: "slate.300",
        fontFeatureSettings: '"cv11", "ss01", "tnum"',
        WebkitFontSmoothing: "antialiased",
        textRendering: "optimizeLegibility",
        overflow: "hidden",
      },
      // Luz ambiente da marca: dois halos (ciano e violeta) fixos atras de tudo.
      // E o mesmo recurso do site da Xdiag e e o que tira o ar de "fundo chapado".
      "body::before": {
        content: '""',
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
        background:
          "radial-gradient(68% 46% at 78% -6%, rgba(6, 182, 212, 0.16), transparent 62%), radial-gradient(52% 40% at 6% 104%, rgba(139, 92, 246, 0.13), transparent 60%)",
      },
      "#root": {
        position: "relative",
        zIndex: 1,
      },
      "::selection": {
        background: "rgba(34, 211, 238, 0.28)",
        color: "#f8fafc",
      },
      "::-webkit-scrollbar": { width: "10px", height: "10px" },
      "::-webkit-scrollbar-track": { background: "transparent" },
      "::-webkit-scrollbar-thumb": {
        background: "rgba(148, 163, 184, 0.18)",
        borderRadius: "999px",
        border: "2px solid transparent",
        backgroundClip: "content-box",
      },
      "::-webkit-scrollbar-thumb:hover": {
        background: "rgba(34, 211, 238, 0.34)",
        backgroundClip: "content-box",
      },
      "*": { scrollbarColor: "rgba(148, 163, 184, 0.28) transparent" },
      // Quem pediu menos animacao ao sistema recebe menos animacao.
      "@media (prefers-reduced-motion: reduce)": {
        "*, *::before, *::after": {
          animationDuration: "0.01ms !important",
          animationIterationCount: "1 !important",
          transitionDuration: "0.01ms !important",
        },
      },
    },
  },
  components: {
    Button: {
      baseStyle: {
        fontWeight: 600,
        borderRadius: "10px",
        letterSpacing: "-0.005em",
        transition: `${TRANSITION}`,
        _focusVisible: { boxShadow: "focus" },
        _disabled: { opacity: 0.42, cursor: "not-allowed", boxShadow: "none" },
      },
      defaultProps: { colorScheme: "brand" },
      variants: {
        // Botao primario: gradiente ciano com halo. Levanta 1px no hover.
        solid: (props: { colorScheme: string }) =>
          props.colorScheme === "brand"
            ? {
                bgGradient: "linear(to-b, brand.300, brand.500)",
                color: "#04121c",
                boxShadow: "0 10px 26px -14px rgba(34, 211, 238, 0.85)",
                _hover: {
                  bgGradient: "linear(to-b, brand.200, brand.400)",
                  transform: "translateY(-1px)",
                  boxShadow: "0 16px 34px -14px rgba(34, 211, 238, 0.95)",
                  _disabled: { transform: "none" },
                },
                _active: { transform: "translateY(0)", bgGradient: "linear(to-b, brand.400, brand.600)" },
              }
            : {
                // Definir variants.solid substitui a variante padrao do Chakra
                // por inteiro, entao qualquer outro colorScheme precisa de um
                // fallback explicito aqui, senao sai sem estilo nenhum.
                bg: `${props.colorScheme}.500`,
                color: "white",
                _hover: { bg: `${props.colorScheme}.400`, transform: "translateY(-1px)", _disabled: { transform: "none" } },
                _active: { bg: `${props.colorScheme}.600`, transform: "translateY(0)" },
              },
        outline: {
          borderColor: "line.medium",
          color: "slate.200",
          bg: "transparent",
          _hover: {
            bg: "surface.hover",
            borderColor: "line.brand",
            color: "slate.50",
            transform: "translateY(-1px)",
            _disabled: { transform: "none" },
          },
          _active: { transform: "translateY(0)", bg: "surface.active" },
        },
        ghost: {
          color: "slate.300",
          _hover: { bg: "surface.hover", color: "slate.50" },
          _active: { bg: "surface.active" },
        },
        // Botao de superficie: usado nas acoes que nao sao a acao principal
        // mas precisam de mais presenca que um ghost.
        surface: {
          bg: "surface.raised",
          color: "slate.100",
          border: "1px solid",
          borderColor: "line.subtle",
          boxShadow: "hairline",
          _hover: {
            bg: "rgba(30, 41, 59, 0.9)",
            borderColor: "line.medium",
            transform: "translateY(-1px)",
            _disabled: { transform: "none" },
          },
          _active: { transform: "translateY(0)" },
        },
      },
    },
    Tag: {
      baseStyle: {
        container: {
          borderRadius: "full",
          fontWeight: 500,
          letterSpacing: "0.01em",
        },
      },
    },
    Tooltip: {
      baseStyle: {
        bg: "surface.overlay",
        color: "slate.100",
        border: "1px solid",
        borderColor: "line.medium",
        borderRadius: "8px",
        fontSize: "xs",
        px: 2.5,
        py: 1.5,
        boxShadow: "raised",
        maxW: "300px",
        backdropFilter: "blur(12px)",
      },
    },
    Menu: {
      baseStyle: {
        list: {
          bg: "surface.overlay",
          borderColor: "line.medium",
          borderRadius: "14px",
          boxShadow: "raised",
          backdropFilter: "blur(16px)",
          py: 2,
        },
        item: {
          bg: "transparent",
          borderRadius: "8px",
          mx: 2,
          px: 2.5,
          w: "auto",
          transition: TRANSITION,
          _hover: { bg: "surface.hover" },
          _focus: { bg: "surface.hover" },
        },
      },
    },
    Divider: {
      baseStyle: { borderColor: "line.subtle", opacity: 1 },
    },
    Switch: {
      defaultProps: { colorScheme: "brand" },
      baseStyle: {
        track: {
          bg: "rgba(148, 163, 184, 0.2)",
          _checked: { bg: "brand.400" },
        },
      },
    },
    Slider: {
      defaultProps: { colorScheme: "brand" },
      baseStyle: {
        track: { bg: "rgba(148, 163, 184, 0.16)", borderRadius: "full" },
        filledTrack: { bgGradient: "linear(to-r, brand.500, brand.300)" },
        thumb: {
          bg: "slate.50",
          boxShadow: "0 0 0 3px rgba(34, 211, 238, 0.28), 0 4px 12px -4px rgba(2, 6, 23, 0.9)",
          _focusVisible: { boxShadow: "0 0 0 4px rgba(34, 211, 238, 0.45)" },
        },
      },
    },
    Accordion: {
      baseStyle: {
        container: { border: "none" },
        button: { borderRadius: "10px", transition: TRANSITION },
        panel: { pb: 2 },
      },
    },
    Alert: {
      baseStyle: {
        container: { borderRadius: "12px" },
      },
    },
    Heading: {
      baseStyle: { letterSpacing: "-0.02em", color: "slate.50" },
    },
  },
});
