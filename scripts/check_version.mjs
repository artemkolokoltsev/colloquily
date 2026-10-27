import fs from 'node:fs';
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
const tauri = JSON.parse(fs.readFileSync('src-tauri/tauri.conf.json', 'utf8'));
const cargo = fs.readFileSync('src-tauri/Cargo.toml', 'utf8').match(/^version\s*=\s*"([^"]+)"/m)?.[1];
const lock = JSON.parse(fs.readFileSync('package-lock.json', 'utf8'));
const cargoLock = fs.readFileSync('src-tauri/Cargo.lock', 'utf8').match(/name = "colloquily"\r?\nversion = "([^"]+)"/)?.[1];
const backend = fs.readFileSync('backend/main.py', 'utf8').match(/FastAPI\([^\n]*version="([^"]+)"/)?.[1];
const settings = fs.readFileSync('frontend/src/features/Settings.tsx', 'utf8').match(/\[version, setVersion\] = useState\("([^"]+)"\)/)?.[1];
const versions = { package: pkg.version, tauri: tauri.version, cargo, packageLock: lock.version, packageLockRoot: lock.packages?.['']?.version, cargoLock, backend, settings };
for (const [source, version] of Object.entries(versions)) {
  if (version !== pkg.version) throw new Error(`Application versions disagree: ${source} is ${version}, expected ${pkg.version}`);
}
const tag = process.env.GITHUB_REF_TYPE === 'tag' ? process.env.GITHUB_REF_NAME : undefined;
if (tag && tag !== `v${tauri.version}` && !new RegExp(`^v${tauri.version.replaceAll('.', '\\.')}-rc\\.[1-9][0-9]*$`).test(tag)) throw new Error('Release tag does not match application version');
console.log(`Version metadata agrees: ${tauri.version}`);
