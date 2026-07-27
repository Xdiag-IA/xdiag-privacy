"use strict";

/**
 * Preparo da primeira execucao: baixa e instala o runtime Python.
 *
 * Por que isto existe em vez de vir dentro do instalador: o NSIS e um
 * executavel de 32 bits e falha ao mapear o proprio payload acima de ~2 GB
 * ("File: failed creating mmap"). Com o runtime de 1,6 GB embutido, o
 * instalador nao compila. Entao o instalador leva 79 MB e o blob grande vem
 * por aqui, uma vez so.
 *
 * O que este modulo garante:
 *   - retomada por Range, para queda de conexao nao jogar fora 600 MB
 *   - verificacao de SHA256 antes de extrair, para nao instalar lixo
 *   - extracao com o tar.exe do proprio Windows, sem carregar descompactador
 *   - atomicidade: extrai para uma pasta temporaria e so entao renomeia
 */

const { execFile } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const http = require("node:http");
const https = require("node:https");
const path = require("node:path");

const MAX_TENTATIVAS = 5;

function humano(bytes) {
  if (bytes >= 1024 ** 3) return (bytes / 1024 ** 3).toFixed(2) + " GB";
  if (bytes >= 1024 ** 2) return (bytes / 1024 ** 2).toFixed(0) + " MB";
  return (bytes / 1024).toFixed(0) + " KB";
}

/** GET seguindo redirecionamento, que o GitHub Releases sempre usa. */
function pedir(url, headers, saltos = 0) {
  return new Promise((resolve, reject) => {
    if (saltos > 6) return reject(new Error("redirecionamentos demais"));
    // Escolhe pelo protocolo em vez de assumir https: alem de permitir o
    // teste local, atende clinica que prefira espelhar o runtime num
    // servidor interno em vez de baixar do GitHub.
    const cliente = new URL(url).protocol === "http:" ? http : https;
    const req = cliente.get(url, { headers }, (res) => {
      const { statusCode, headers: h } = res;
      if (statusCode >= 300 && statusCode < 400 && h.location) {
        res.resume();
        // O host muda no redirecionamento (github.com -> objects.githubusercontent.com),
        // entao o Range precisa ir junto, senao a retomada recomeca do zero.
        return resolve(pedir(new URL(h.location, url).toString(), headers, saltos + 1));
      }
      if (statusCode !== 200 && statusCode !== 206) {
        res.resume();
        return reject(new Error(`HTTP ${statusCode} ao baixar`));
      }
      resolve(res);
    });
    req.on("error", reject);
    req.setTimeout(60_000, () => {
      req.destroy(new Error("tempo esgotado na conexao"));
    });
  });
}

/**
 * Baixa com retomada. Se o arquivo parcial existir, continua de onde parou.
 */
async function baixar(url, destino, aoProgredir) {
  for (let tentativa = 1; tentativa <= MAX_TENTATIVAS; tentativa++) {
    let jaTem = 0;
    try {
      jaTem = (await fsp.stat(destino)).size;
    } catch {
      jaTem = 0;
    }

    const headers = { "User-Agent": "XdiagPrivacy-Setup" };
    if (jaTem > 0) headers.Range = `bytes=${jaTem}-`;

    try {
      const res = await pedir(url, headers);

      // 200 com Range pedido significa que o servidor ignorou a retomada:
      // recomeca do zero para nao concatenar arquivo corrompido.
      const retomando = res.statusCode === 206 && jaTem > 0;
      if (!retomando && jaTem > 0) {
        await fsp.rm(destino, { force: true });
        jaTem = 0;
      }

      const total = Number(res.headers["content-length"] || 0) + jaTem;
      let recebido = jaTem;

      await new Promise((resolve, reject) => {
        const saida = fs.createWriteStream(destino, { flags: retomando ? "a" : "w" });
        res.on("data", (chunk) => {
          recebido += chunk.length;
          if (aoProgredir) aoProgredir(recebido, total);
        });
        res.on("error", reject);
        saida.on("error", reject);
        saida.on("finish", resolve);
        res.pipe(saida);
      });

      return;
    } catch (err) {
      if (tentativa === MAX_TENTATIVAS) throw err;
      // Espera crescente. O arquivo parcial fica no disco de proposito: a
      // proxima tentativa continua dele.
      await new Promise((r) => setTimeout(r, 1500 * tentativa));
    }
  }
}

async function sha256(arquivo, aoProgredir) {
  const total = (await fsp.stat(arquivo)).size;
  let lido = 0;
  const hash = crypto.createHash("sha256");
  await new Promise((resolve, reject) => {
    const fluxo = fs.createReadStream(arquivo);
    fluxo.on("data", (c) => {
      lido += c.length;
      hash.update(c);
      if (aoProgredir) aoProgredir(lido, total);
    });
    fluxo.on("error", reject);
    fluxo.on("end", resolve);
  });
  return hash.digest("hex");
}

/**
 * Caminho absoluto do bsdtar do Windows (10 1803 ou mais novo).
 *
 * Chamar "tar.exe" solto resolveria pelo PATH, e quem tem Git instalado tem o
 * GNU tar do Git na frente do System32. O GNU tar interpreta "C:\..." como
 * host remoto e falha com "Cannot connect to C: resolve failed". O bsdtar da
 * Microsoft entende unidade normalmente. Absoluto elimina a loteria de PATH.
 */
function tarDoWindows() {
  const systemRoot = process.env.SystemRoot || process.env.SYSTEMROOT || "C:\\Windows";
  const candidato = path.join(systemRoot, "System32", "tar.exe");
  return fs.existsSync(candidato) ? candidato : "tar.exe";
}

/** Extrai o zip usando o bsdtar do proprio Windows, sem carregar binario. */
function extrair(zip, destino) {
  return new Promise((resolve, reject) => {
    execFile(
      tarDoWindows(),
      ["-x", "-f", path.resolve(zip), "-C", path.resolve(destino)],
      { windowsHide: true, maxBuffer: 1024 * 1024 },
      (err, _out, stderr) => {
        if (err) return reject(new Error(`falha ao extrair: ${stderr || err.message}`));
        resolve();
      },
    );
  });
}

/**
 * Garante que o runtime esta instalado em `destinoFinal`.
 *
 * @param {object} opts
 * @param {string} opts.url          endereco do zip do runtime
 * @param {string} opts.sha256       hash esperado, minusculo
 * @param {string} opts.destinoFinal pasta onde deve existir python/python.exe
 * @param {string} opts.pastaTemp    onde guardar o download parcial
 * @param {(fase: string, pct: number|null, detalhe: string) => void} opts.aoStatus
 */
async function garantirRuntime({ url, sha256: esperado, destinoFinal, pastaTemp, aoStatus }) {
  const python = path.join(destinoFinal, "python", "python.exe");
  if (fs.existsSync(python)) return { baixou: false };

  await fsp.mkdir(pastaTemp, { recursive: true });
  const zip = path.join(pastaTemp, "runtime.zip");

  let ultimo = 0;
  await baixar(url, zip, (recebido, total) => {
    const agora = Date.now();
    // Atualiza no maximo 8 vezes por segundo: o IPC nao precisa de mais que
    // isso e a barra fica igual.
    if (agora - ultimo < 125) return;
    ultimo = agora;
    const pct = total ? (recebido / total) * 100 : null;
    aoStatus("baixando", pct, `${humano(recebido)} de ${humano(total)}`);
  });

  aoStatus("verificando", null, "Conferindo a integridade do arquivo");
  const obtido = await sha256(zip, (lido, total) => {
    aoStatus("verificando", (lido / total) * 100, "Conferindo a integridade do arquivo");
  });

  if (esperado && obtido !== esperado.toLowerCase()) {
    // Apaga: manter arquivo corrompido faria a retomada continuar de um
    // download que ja nasceu errado.
    await fsp.rm(zip, { force: true });
    throw new Error(
      "O arquivo baixado nao corresponde ao esperado e foi descartado. " +
        "Isso costuma ser download interrompido ou interferencia de proxy. Tente de novo.",
    );
  }

  aoStatus("instalando", null, "Descompactando, isso leva alguns minutos");
  // Extrai para pasta temporaria e so entao renomeia: se faltar energia no
  // meio, nao sobra uma instalacao pela metade que passaria no teste de
  // "python.exe existe".
  const parcial = path.join(pastaTemp, "runtime-parcial");
  await fsp.rm(parcial, { recursive: true, force: true });
  await fsp.mkdir(parcial, { recursive: true });
  await extrair(zip, parcial);

  if (!fs.existsSync(path.join(parcial, "python", "python.exe"))) {
    throw new Error("o pacote extraido nao contem python/python.exe");
  }

  await fsp.rm(destinoFinal, { recursive: true, force: true });
  await fsp.mkdir(path.dirname(destinoFinal), { recursive: true });
  await fsp.rename(parcial, destinoFinal);

  await fsp.rm(zip, { force: true });
  return { baixou: true };
}

module.exports = { garantirRuntime, humano };
