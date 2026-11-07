import { createHash, createPublicKey, verify } from 'node:crypto';
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

const signedBytes = await readFile(resolve(dirname(source), 'update-manifest.json'));
const signature = await readFile(resolve(dirname(source), 'update-manifest.json.sig'), 'utf8');
const signed = JSON.parse(signedBytes);
const trust = JSON.parse(await readFile(resolve(destinationDirectory, 'update-public-keys.json'), 'utf8'));
const key = trust.keys.find((entry) => entry.keyId === signed.keyId && ['active', 'transition'].includes(entry.status));
if (!key || signed.downloadUrl !== lock.source ||
    ['version', 'sha256', 'bytes', 'releaseSequence', 'keyId'].some((field) => signed[field] !== lock[field]) ||
    (key.minimumReleaseSequence && signed.releaseSequence < key.minimumReleaseSequence) ||
    (key.maximumReleaseSequence && signed.releaseSequence > key.maximumReleaseSequence)) {
  throw new Error('Signed manifest does not match upstream lock or trust policy');
}
const rawKey = Buffer.from(key.publicKey, 'base64');
if (rawKey.length !== 32 || createHash('sha256').update(rawKey).digest('hex') !== key.fingerprint) {
  throw new Error('Invalid signing key fingerprint');
}
const publicKey = createPublicKey({key: Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), rawKey]), format: 'der', type: 'spki'});
if (!verify(null, signedBytes, publicKey, Buffer.from(signature.trim(), 'base64'))) {
  throw new Error('Invalid userscript signature');
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

await writeFile(resolve(destinationDirectory, 'update-manifest.json'), signedBytes);
await writeFile(resolve(destinationDirectory, 'update-manifest.json.sig'), signature, 'utf8');
