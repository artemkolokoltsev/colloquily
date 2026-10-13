import fs from "node:fs";
const publicKey = process.argv[2];
if (!publicKey || publicKey.includes("PRIVATE")) throw new Error("A public updater key is required");
const path = new URL("../src-tauri/tauri.conf.json", import.meta.url);
const config = JSON.parse(fs.readFileSync(path, "utf8"));
config.plugins.updater.pubkey = publicKey;
fs.writeFileSync(path, `${JSON.stringify(config, null, 2)}\n`);
