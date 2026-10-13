import fs from "node:fs";
import ts from "typescript";

const source = fs.readFileSync(new URL("../frontend/src/i18n.ts", import.meta.url), "utf8");
const file = ts.createSourceFile("i18n.ts", source, ts.ScriptTarget.Latest, true);

function initializer(name) {
  for (const statement of file.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (declaration.name.getText(file) === name) return declaration.initializer;
    }
  }
  throw new Error(`Translation object ${name} was not found`);
}

function keys(node, prefix = "", result = []) {
  if (ts.isAsExpression(node)) return keys(node.expression, prefix, result);
  if (!ts.isObjectLiteralExpression(node)) return result;
  for (const property of node.properties) {
    if (!ts.isPropertyAssignment(property)) continue;
    const name = property.name.getText(file).replace(/^['"]|['"]$/g, "");
    const path = prefix ? `${prefix}.${name}` : name;
    if (ts.isObjectLiteralExpression(property.initializer)) keys(property.initializer, path, result);
    else result.push(path);
  }
  return result;
}

const en = new Set(keys(initializer("en")));
const de = new Set(keys(initializer("de")));
const missingDe = [...en].filter((key) => !de.has(key));
const missingEn = [...de].filter((key) => !en.has(key));
if (missingDe.length || missingEn.length) {
  throw new Error(`Translation keys differ. Missing de: ${missingDe.join(", ")}; missing en: ${missingEn.join(", ")}`);
}
console.log(`Translation catalogs match (${en.size} leaf keys per locale).`);
function compare(left, right, name) {
  const a = Object.keys(left).sort(); const b = Object.keys(right).sort();
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${name}: locale keys differ`);
  for (const key of a) {
    const placeholders = value => [...value.matchAll(/{{\s*(\w+)\s*}}/g)].map(match => match[1]).sort();
    if (JSON.stringify(placeholders(left[key])) !== JSON.stringify(placeholders(right[key]))) throw new Error(`${name}.${key}: interpolation differs`);
  }
  console.log(`${name}: ${a.length} keys and interpolation variables match.`);
}
const readJson = name => JSON.parse(fs.readFileSync(new URL(`../frontend/src/locales/${name}.json`, import.meta.url), 'utf8'));
compare(readJson('ui-en'), readJson('ui-de'), 'feature screens');
for (const name of ['release', 'dynamic']) { const resource = readJson(name); compare(resource.en, resource.de, name); }
