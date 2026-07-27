// Persiste um FileSystemDirectoryHandle entre sessoes. O handle nao e
// serializavel em JSON (localStorage), so o IndexedDB consegue guardar o
// objeto real; por isso este modulo fica separado do settingsStore.
const DB_NAME = "xdiag-fs-handles";
const STORE_NAME = "handles";
const OUTPUT_DIR_KEY = "outputDir";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE_NAME);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, mode);
      const req = fn(tx.objectStore(STORE_NAME));
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  } finally {
    db.close();
  }
}

export async function saveDirHandle(handle: FileSystemDirectoryHandle): Promise<void> {
  await withStore("readwrite", (store) => store.put(handle, OUTPUT_DIR_KEY));
}

export async function loadDirHandle(): Promise<FileSystemDirectoryHandle | null> {
  const handle = await withStore<FileSystemDirectoryHandle | undefined>("readonly", (store) =>
    store.get(OUTPUT_DIR_KEY),
  );
  return handle ?? null;
}

export async function clearDirHandle(): Promise<void> {
  await withStore("readwrite", (store) => store.delete(OUTPUT_DIR_KEY));
}
