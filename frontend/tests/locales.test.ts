import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { en } from '../lib/i18n/en.ts';
import { languages } from '../lib/i18n/languages.ts';
test('every requested language has all UI keys and keeps AMB-05 unchanged', () => {
 assert.equal(languages.length, 13);
 for (const {code} of languages.filter(l => l.code !== 'en')) {
  const catalog = JSON.parse(readFileSync(new URL(`../lib/i18n/locales/${code}.json`,import.meta.url),'utf8')) as Record<string,string>;
  assert.deepEqual(Object.keys(catalog).sort(),Object.keys(en).sort(),`${code} keys`);
  for (const [key,value] of Object.entries(catalog)) assert.ok(typeof value === 'string' && value.trim(),`${code}.${key}`);
  assert.ok(catalog['demo.replace'].includes('AMB-05'));
  assert.notEqual(catalog['actions.approve'], en['actions.approve']);
 }
 assert.equal(languages.find(l=>l.code==='ur')?.dir,'rtl');
});
