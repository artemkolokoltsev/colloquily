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
