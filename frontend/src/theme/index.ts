import { extendTheme, type ThemeConfig } from "@chakra-ui/react";

const config: ThemeConfig = {
  initialColorMode: "dark",
  useSystemColorMode: false,
};

// Xdiag palette: clinical neutrals with redaction red as accent.
export const theme = extendTheme({
  config,
  fonts: {
    heading: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`,
    body: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`,
    mono: `'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace`,
  },
  colors: {
    redaction: {
      50: "#fef2f2",
      100: "#fee2e2",
      200: "#fecaca",
      300: "#fca5a5",
      400: "#f87171",
      500: "#ef4444",
      600: "#dc2626",
      700: "#b91c1c",
      800: "#991b1b",
      900: "#7f1d1d",
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
  },
  styles: {
    global: {
      "html, body, #root": {
        height: "100%",
        bg: "slate.950",
        color: "slate.100",
      },
      body: {
        fontFeatureSettings: '"cv11", "ss01"',
      },
      "::selection": {
        background: "redaction.600",
        color: "white",
      },
    },
  },
  components: {
    Button: {
      defaultProps: {
        colorScheme: "redaction",
      },
    },
  },
});
