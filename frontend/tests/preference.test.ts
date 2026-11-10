import { test } from "node:test";
import assert from "node:assert/strict";
import { startupLanguage } from "../lib/i18n/preference.ts";
test("saved languages bypass onboarding; detected languages require confirmation", () => {
  assert.deepEqual(startupLanguage("ur", ["en-US"]), { language: "ur", needsConfirmation: false });
  assert.deepEqual(startupLanguage(null, ["hi-IN"]), { language: "hi", needsConfirmation: true });
  assert.deepEqual(startupLanguage("invalid", ["fr-FR", "kn-IN"]), { language: "kn", needsConfirmation: true });
  assert.deepEqual(startupLanguage(null, ["ta_IN"]), { language: "ta", needsConfirmation: true });
  assert.deepEqual(startupLanguage(null, ["fr"]), { language: "en", needsConfirmation: true });
  assert.deepEqual(startupLanguage(null, []), { language: "en", needsConfirmation: true });
});
