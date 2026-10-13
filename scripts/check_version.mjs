import fs from 'node:fs';
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
const tauri = JSON.parse(fs.readFileSync('src-tauri/tauri.conf.json', 'utf8'));
const cargo = fs.readFileSync('src-tauri/Cargo.toml', 'utf8').match(/^version\s*=\s*"([^"]+)"/m)?.[1];
if (pkg.version !== tauri.version || cargo !== tauri.version) throw new Error('Application versions disagree');
const tag = process.env.GITHUB_REF_TYPE === 'tag' ? process.env.GITHUB_REF_NAME : undefined;
if (tag && tag !== `v${tauri.version}` && !new RegExp(`^v${tauri.version.replaceAll('.', '\\.')}-rc\\.[1-9][0-9]*$`).test(tag)) throw new Error('Release tag does not match application version');
console.log(`Version metadata agrees: ${tauri.version}`);
