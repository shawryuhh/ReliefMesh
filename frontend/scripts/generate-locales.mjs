import { readFileSync, writeFileSync } from 'node:fs';
const root = new URL('../lib/i18n/', import.meta.url);
const rows = readFileSync(new URL('locales/catalog.tsv', root), 'utf8').trim().split('\n').map(line => line.split('|'));
const mappings = JSON.parse(readFileSync(new URL('./locale-keys.json', import.meta.url), 'utf8'));
const keys = [...readFileSync(new URL('en.ts', root), 'utf8').matchAll(/"([\w.]+)":/g)].map(match => match[1]);
if (keys.length !== Object.keys(mappings).length || keys.some(key => !mappings[key])) throw new Error('Update scripts/locale-keys.json for every English key.');
for (const row of rows) if (row.length !== 13) throw new Error(`Invalid translation row: ${row[0]}`);
rows[0].slice(1).forEach((language, i) => {
 const vocabulary = Object.fromEntries(rows.slice(1).map(row => [row[0].trim(), row[i+1]]));
 const strings = Object.fromEntries(keys.map(key => [key, mappings[key].split('+').map(token => {
  if (token.startsWith('@')) return token.slice(1);
  if (!vocabulary[token]) throw new Error(`Missing ${language} token: ${token}`);
  return vocabulary[token];
 }).join(' · ')]));
 writeFileSync(new URL(`locales/${language}.json`, root), JSON.stringify(strings, null, 2)+'\n');
});
console.log(`Generated ${rows[0].length-1} dictionaries with ${keys.length} keys each.`);
