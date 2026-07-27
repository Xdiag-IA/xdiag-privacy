import React from "react";
import ReactDOM from "react-dom/client";
import { ChakraProvider, ColorModeScript } from "@chakra-ui/react";
// Inter empacotada no bundle. A fonte da marca Xdiag sem nenhuma chamada
// externa em runtime, que quebraria a premissa local first do produto.
import "@fontsource-variable/inter";
import { theme } from "./theme";
import App from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("missing #root element");

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <ColorModeScript initialColorMode={theme.config.initialColorMode} />
    <ChakraProvider theme={theme}>
      <App />
    </ChakraProvider>
  </React.StrictMode>,
);
