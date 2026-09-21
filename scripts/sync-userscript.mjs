import { createHash } from 'node:crypto';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const lockPath = resolve(repositoryRoot, 'upstream.json');
const lock = JSON.parse(await readFile(lockPath, 'utf8'));
const sourceArgumentIndex = process.argv.indexOf('--source');
const source = resolve(
  repositoryRoot,
  sourceArgumentIndex >= 0
    ? process.argv[sourceArgumentIndex + 1]
    : process.env.WHATSAPP_WEB_PLUS_SOURCE
      ?? '../whatsapp-web-plus/whatsapp_web_plus.user.js'
);
const destinationDirectory = resolve(
  repositoryRoot,
  'addon/globalPlugins/whatsappWebPlusCompanion/resources'
);
const destination = resolve(destinationDirectory, lock.asset);
const bytes = await readFile(source);
const text = bytes.toString('utf8');
const version = text.match(/^\/\/ @version\s+(.+)$/m)?.[1];
const sha256 = createHash('sha256').update(bytes).digest('hex');

if (lock.schemaVersion !== 2 || lock.signedManifestSchemaVersion !== 2) {
  throw new Error('Upstream lock does not use the signed update manifest protocol');
}
if (!Number.isSafeInteger(lock.releaseSequence) || lock.releaseSequence <= 0) {
  throw new Error('Upstream lock has an invalid release sequence');
}
if (!/^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$/.test(lock.keyId)) {
  throw new Error('Upstream lock has an invalid signing key ID');
}

if (!version) throw new Error('Generated userscript has no @version');
if (version !== lock.version) {
  throw new Error(`Userscript version ${version} does not match upstream lock ${lock.version}`);
}
if (sha256 !== lock.sha256) {
  throw new Error(`Userscript SHA-256 ${sha256} does not match upstream lock ${lock.sha256}`);
}

await mkdir(destinationDirectory, { recursive: true });
await copyFile(source, destination);
const metadata = {
  version,
  sha256,
  bytes: bytes.length,
  upstream: lock.source,
  releaseSequence: lock.releaseSequence,
  keyId: lock.keyId
};
await writeFile(
  resolve(destinationDirectory, 'bundle.json'),
  `${JSON.stringify(metadata, null, 2)}\n`,
  'utf8'
);
console.log(`Embedded bundle ${version} ${sha256} ${bytes.length} bytes from ${source}`);
