"use strict";

/**
 * Processo principal do Xdiag Privacy Desktop.
 *
 * Responsabilidades, nesta ordem:
 *   1. escolher uma porta livre no loopback
 *   2. abrir a splash na hora, para a janela nao demorar a aparecer
 *   3. subir o backend Python empacotado como processo filho
 *   4. esperar /api/health responder (a primeira subida carrega ~2 GB)
 *   5. carregar a interface, servida pelo proprio backend
 *   6. matar a arvore de processos ao sair
 */

const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn, execFile } = require("node:child_process");
const http = require("node:http");
const net = require("node:net");
const path = require("node:path");
const fs = require("node:fs");
const { garantirRuntime } = require("./setup");
const manifest = require("./runtime-manifest.json");

// Segundo o quanto o modelo demora para carregar do disco: medido em 71s com
// cache quente, mais o download de ~2,1 GB na primeira vez. O teto e generoso
// de proposito; quem decide desistir e o usuario, nao um timeout apertado.
const HEALTH_TIMEOUT_MS = 30 * 60 * 1000;
const HEALTH_INTERVAL_MS = 700;

const isDev = !app.isPackaged;

/** Marcos do boot no stdout. E o que sobra para diagnosticar quando o
 *  aplicativo do usuario nao abre e ele so consegue dizer "nao funciona". */
function log(...args) {
  console.log("[xdiag]", ...args);
}

let backend = null;
let splash = null;
let main = null;
let quitting = false;

// --- Caminhos ---------------------------------------------------------------

/**
 * Em desenvolvimento tudo mora no repositorio; empacotado, em resources/.
 * Manter os dois caminhos aqui e nao espalhados evita o classico "funciona no
 * dev e quebra no instalador".
 */
function resolvePaths() {
  const root = isDev
    ? path.resolve(__dirname, "..", "..")
    : process.resourcesPath;

  // O runtime Python NAO viaja dentro do instalador. Sao 1,6 GB, e o NSIS e
  // um processo de 32 bits: acima de ~2 GB de payload ele falha no mmap do
  // proprio pacote ("failed creating mmap"). Instalador com tudo embutido
  // simplesmente nao compila. Entao o runtime e baixado na primeira execucao
  // e vive na pasta de dados do usuario, fora da instalacao.
  const runtime = isDev
    ? path.join(__dirname, "..", "build", "runtime")
    : path.join(app.getPath("userData"), "runtime");

  const web = isDev
    ? path.join(root, "frontend", "dist")
    : path.join(root, "web");

  // O codigo do backend, ao contrario do runtime, viaja no instalador: e
  // pequeno e precisa casar com a versao do app. Isso tambem deixa a
  // atualizacao leve, porque o blob grande so muda quando a versao do Python
  // ou das dependencias muda.
  //
  // Em desenvolvimento vem direto de backend/, nunca da copia dentro de
  // build/runtime: aquela copia existe so para o smoke test e envelhece em
  // silencio. Ja custou um debug de SPA que nao subia e de modelo do OCR indo
  // parar na pasta errada.
  // Mesmo caminho relativo nos dois casos: no repositorio e backend/ na raiz,
  // e empacotado o electron-builder copia para resources/backend.
  const appDir = path.join(root, "backend");

  return {
    python: path.join(runtime, "python", "python.exe"),
    runtime,
    appDir,
    web,
    // Mesmo caminho relativo nos dois casos: no repositorio e samples/ na
    // raiz, e empacotado o electron-builder copia para resources/samples.
    samples: path.join(root, "samples"),
    // Dados do usuario ficam FORA da pasta de instalacao: modelo baixado,
    // cache. Assim atualizar o app nao apaga 2 GB de modelo, e a instalacao
    // por usuario nao precisa de permissao de escrita em Program Files.
    data: path.join(app.getPath("userData"), "data"),
  };
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

// --- Backend ----------------------------------------------------------------

function startBackend(paths, port) {
  fs.mkdirSync(paths.data, { recursive: true });
  const cache = path.join(paths.data, "cache");
  fs.mkdirSync(cache, { recursive: true });

  const env = {
    ...process.env,
    // Loopback, nunca 0.0.0.0. O default do backend serve o container; num
    // app de mesa ele publicaria a API de anonimizacao de prontuario para a
    // rede inteira da clinica.
    XDIAG_HOST: "127.0.0.1",
    XDIAG_PORT: String(port),
    XDIAG_CACHE_DIR: cache,
    XDIAG_SAMPLES_DIR: paths.samples,
    XDIAG_WEB_DIR: paths.web,
    XDIAG_OCR_MODEL_DIR: path.join(cache, "paddleocr"),
    HF_HOME: path.join(cache, "huggingface"),
    TRANSFORMERS_CACHE: path.join(cache, "huggingface"),
    XDIAG_EAGER_LOAD: "1",
    PYTHONUNBUFFERED: "1",
    PYTHONDONTWRITEBYTECODE: "1",
  };

  const child = spawn(
    paths.python,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port), "--log-level", "info"],
    { cwd: paths.appDir, env, windowsHide: true },
  );

  child.stdout.on("data", (b) => process.stdout.write(`[backend] ${b}`));
  child.stderr.on("data", (b) => process.stderr.write(`[backend] ${b}`));

  return child;
}

/**
 * Mata a ARVORE do processo. uvicorn sozinho ja pode ter filhos, e o Paddle
 * abre workers. Filho orfao trava a porta e segura mais de 1 GB de RAM: e o
 * bug classico de shell Electron mal encerrado.
 */
function killBackend() {
  if (!backend || backend.killed) return;
  const pid = backend.pid;
  backend = null;
  if (process.platform === "win32") {
    execFile("taskkill", ["/pid", String(pid), "/T", "/F"], () => {});
  } else {
    try {
      process.kill(-pid, "SIGTERM");
    } catch {
      /* ja morreu */
    }
  }
}

function pingHealth(port) {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port, path: "/api/health", timeout: 2000 },
      (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      },
    );
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForBackend(port) {
  const deadline = Date.now() + HEALTH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (backend === null) throw new Error("o backend encerrou antes de responder");
    if (await pingHealth(port)) return;
    await new Promise((r) => setTimeout(r, HEALTH_INTERVAL_MS));
  }
  throw new Error("o backend nao respondeu no tempo esperado");
}

// --- Janelas ----------------------------------------------------------------

function createSplash() {
  const win = new BrowserWindow({
    width: 460,
    height: 320,
    frame: false,
    resizable: false,
    center: true,
    show: true,
    backgroundColor: "#020617",
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  win.loadFile(path.join(__dirname, "splash.html"));
  return win;
}

function createMain(port) {
  const win = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    backgroundColor: "#020617",
    title: "Xdiag Privacy",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // A interface nao precisa de nada do Node. Ela conversa com o backend
      // por HTTP na mesma origem, igual no navegador.
      preload: undefined,
    },
  });

  win.removeMenu();
  win.loadURL(`http://127.0.0.1:${port}/`);
  win.once("ready-to-show", () => {
    win.show();
    if (splash && !splash.isDestroyed()) splash.destroy();
    splash = null;
  });

  // Link externo abre no navegador do sistema, nunca dentro do app.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
    });

  return win;
}

/**
 * @param {string} text
 * @param {number|null} pct porcentagem; null deixa a barra indeterminada
 */
function setSplashStatus(text, pct = null) {
  if (pct === null) log("status:", text.replace(/\n/g, " | "));
  if (splash && !splash.isDestroyed()) {
    splash.webContents
      .executeJavaScript(
        `window.setStatus && window.setStatus(${JSON.stringify(text)}, ${
          pct === null ? "null" : Math.max(0, Math.min(100, pct))
        })`,
      )
      .catch(() => {});
  }
}

/**
 * Traduz a falha em algo que quem esta instalando consiga agir.
 *
 * "HTTP 404 ao baixar" nao diz nada para um medico na frente da tela. Cada
 * causa provavel tem um proximo passo diferente, e e o proximo passo que a
 * mensagem precisa entregar.
 */
function explicarFalha(err) {
  const msg = (err && err.message) || String(err);
  const status = err && err.statusCode;

  if (status === 404) {
    return {
      titulo: "Componente não encontrado no servidor",
      texto:
        "O aplicativo precisa baixar um componente na primeira execução, mas ele não " +
        "está disponível no endereço esperado.\n\n" +
        "Isso normalmente significa que esta versão do instalador é mais nova que a " +
        "publicada. Baixe o instalador mais recente em:\n" +
        "github.com/Xdiag-IA/xdiag-privacy/releases",
    };
  }
  if (status === 403) {
    return {
      titulo: "Download bloqueado",
      texto:
        "O servidor recusou o download. Em rede de empresa ou de clínica isso " +
        "costuma ser o proxy ou o firewall bloqueando o acesso ao GitHub.\n\n" +
        "Peça liberação para github.com e objects.githubusercontent.com, ou instale " +
        "de uma rede sem restrição.",
    };
  }
  if (/não corresponde ao esperado|nao corresponde ao esperado/i.test(msg)) {
    return {
      titulo: "O arquivo baixado veio corrompido",
      texto:
        "A verificação de integridade falhou e o arquivo foi descartado, para não " +
        "instalar nada adulterado.\n\nIsso costuma ser download interrompido ou " +
        "proxy que altera o conteúdo. Tente de novo.",
    };
  }
  if (/ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT|tempo esgotado/i.test(msg)) {
    return {
      titulo: "Sem conexão com a internet",
      texto:
        "Não foi possível alcançar o servidor para baixar os componentes da primeira " +
        "execução.\n\nVerifique a conexão e tente de novo. O que já foi baixado é " +
        "aproveitado, o download continua de onde parou.",
    };
  }
  if (/ENOSPC|espaço|espaco/i.test(msg)) {
    return {
      titulo: "Espaço insuficiente em disco",
      texto:
        "A instalação precisa de cerca de 6 GB livres: 1,3 GB de componentes e 2,1 GB " +
        "de modelos, mais espaço temporário.\n\nLibere espaço e tente de novo.",
    };
  }
  return {
    titulo: "Não foi possível iniciar",
    texto: msg,
  };
}

// --- Ciclo de vida ----------------------------------------------------------

// Duas instancias significariam dois backends, dois modelos na RAM e briga de
// porta. A segunda apenas traz a primeira para a frente.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (main) {
      if (main.isMinimized()) main.restore();
      main.focus();
    }
  });

  app.whenReady().then(async () => {
    const paths = resolvePaths();

    splash = createSplash();

    try {
      // Primeira execucao: o instalador tem 79 MB e nao traz o runtime. Ele e
      // baixado aqui, uma vez, com retomada e conferencia de hash.
      if (!fs.existsSync(paths.python)) {
        if (isDev) {
          throw new Error(
            "Runtime nao encontrado em " + paths.python +
              "\n\nEm desenvolvimento, rode antes: desktop\\scripts\\build-runtime.ps1",
          );
        }
        if (!manifest.sha256) {
          throw new Error(
            "Este build saiu sem o hash do runtime em runtime-manifest.json, " +
              "entao o download foi bloqueado por seguranca.",
          );
        }
        log("runtime ausente, baixando de", manifest.url);
        await garantirRuntime({
          url: manifest.url,
          sha256: manifest.sha256,
          destinoFinal: paths.runtime,
          pastaTemp: path.join(app.getPath("userData"), "download"),
          aoStatus: (fase, pct, detalhe) => {
            const titulos = {
              baixando: "Baixando os componentes",
              verificando: "Verificando a integridade",
              instalando: "Instalando",
            };
            setSplashStatus(`${titulos[fase] || fase}\n${detalhe}`, pct);
          },
        });
        log("runtime instalado em", paths.runtime);
      }

      const port = await findFreePort();
      log("runtime:", paths.python);
      log("spa:", paths.web);
      log("dados:", paths.data);
      log("porta:", port);
      setSplashStatus("Iniciando o motor local...");

      backend = startBackend(paths, port);
      backend.on("exit", (code) => {
        const wasRunning = backend !== null;
        backend = null;
        if (!quitting && wasRunning) {
          dialog.showErrorBox(
            "O motor local encerrou",
            `O processo do backend terminou com código ${code}.\n\n` +
              "Feche e abra o aplicativo novamente. Se persistir, reinstale.",
          );
          app.quit();
        }
      });

      setSplashStatus("Carregando os modelos de OCR e de detecção...");
      await waitForBackend(port);

      setSplashStatus("Pronto");
      main = createMain(port);
      main.webContents.once("did-finish-load", () =>
        log("interface carregada de http://127.0.0.1:" + port + "/"),
      );
      main.webContents.on("did-fail-load", (_e, code, desc) =>
        log("FALHA ao carregar a interface:", code, desc),
      );
    } catch (err) {
      killBackend();
      const { titulo, texto } = explicarFalha(err);
      const r = await dialog.showMessageBox({
        type: "error",
        title: "Xdiag Privacy",
        message: titulo,
        detail: texto,
        buttons: ["Tentar de novo", "Fechar"],
        defaultId: 0,
        cancelId: 1,
        noLink: true,
      });
      if (r.response === 0) {
        // O download parcial fica no disco, entao a nova tentativa continua de
        // onde parou em vez de recomecar os 406 MB.
        app.relaunch();
      }
      app.quit();
    }
  });

  app.on("before-quit", () => {
    quitting = true;
    killBackend();
  });

  app.on("window-all-closed", () => {
    app.quit();
  });

  // Rede de seguranca: se o processo morrer por caminho nao previsto, ainda
  // assim nao deixa o Python orfao.
  process.on("exit", killBackend);
  process.on("SIGINT", () => {
    killBackend();
    process.exit(0);
  });
}
