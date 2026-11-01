# MJML Compilation Reference

---

## Hard Rules

1. **No global install** — Never run `npm install -g mjml`. If missing, suggest `npm install -D mjml`.
2. **Use npx or relative path** — `npx mjml` or `./node_modules/.bin/mjml`. Never assume global `$PATH`.
3. **Verify source first** — Check that the `.mjml` file exists and contains valid XML before compiling.

---

## Environment Check

```bash
node -v          # Must be v20+ (MJML 5 targets Node LTS 20/22/24; 16/18 are unsupported)
cat package.json # Look for "mjml" in dependencies or devDependencies
```

If `mjml` is not in `package.json`: suggest `npm install -D mjml` and wait for user confirmation.

---

## Standard Compilation Command

```bash
npx mjml <source.mjml> -o <output.html> --config.minify=true --config.validationLevel=strict
```

- `--config.minify=true` — **always required**: keeps payload under Gmail's 102KB clip threshold (v5's `cssnano` also minifies CSS, so overall output is smaller than v4's). It does **not** strip whitespace between tags any more — see below
- `--config.validationLevel=strict` — fail fast on syntax errors during development

**If the template uses `<mj-include>`**, minify/validate are not enough — includes are ignored by default in MJML 5:

```bash
npx mjml <source.mjml> -o <output.html> --config.minify=true --config.validationLevel=strict \
  --config.allowIncludes true --config.includePath './partials'
```

Without `--config.allowIncludes true`, MJML silently drops the include and logs a warning instead of failing — check compiled output for missing content before assuming the template is correct. `--config.includePath` allowlists the directory includes may resolve from, in addition to the source file's own directory.

**`--config.validationLevel=strict` does NOT catch this.** A dropped include still exits `0`, still writes the `.html`, and still passes strict validation — the only signal is a warning on stderr. Never treat a clean exit code as proof the include landed. Verify explicitly:

```bash
grep -q "<known-string-from-the-partial>" <output.html> || echo "INCLUDE MISSING"
```

Pick a plain-text string for that grep. With `--config.minify=true`, `htmlnano` rewrites HTML entities (`&middot;` becomes the literal `·`), so grepping for entity markup reports a false failure on a build that actually succeeded.

**The two paths resolve from different bases** — this is the usual reason an allowlisted include still gets denied:

| Path | Resolved relative to |
|------|---------------------|
| `path="..."` on `<mj-include>` | the **template file's** directory |
| `--config.includePath` (relative) | the **current working directory** (since MJML 5.2.2) |

Compiling `src/emails/welcome.mjml` from the repo root, with a partial in `common/`, the include is `path="../../common/shared.mjml"` but the flag is `--config.includePath './common'`. Passing an absolute path avoids the ambiguity entirely. A partial outside the template's own directory that is not allowlisted is denied the same silent way.

---

## Output Pathing

Mirror source structure into `/dist`, or output alongside source:

- `src/emails/welcome.mjml` → `dist/emails/welcome.html`
- `emails/welcome.mjml` → `emails/welcome.html`

Ensure the output directory exists before compiling — MJML will not create it.

---

## Error Recovery

1. Parse error output for line/column number
2. Read the source file at that line
3. Fix the syntax issue
4. Re-attempt compilation once
5. **Judge success by the exit code, never by the file.** A failed compile writes no file at all (the 0-byte case does not occur) — but if a previous good build already sits at that output path, it is left fully intact. So a failed recompile can look exactly like a success: the `.html` is present, non-empty, and stale. Check `$?`

**`CssSyntaxError` with templating tags**: a templating tag inside `<mj-style>` **fails the build** under the mandatory `--config.minify=true` — exit `1`, no HTML written:

```
CssSyntaxError: <css input>:2:56: Unknown word brand.darkColor
```

Sanitization is **not** automatic — `sanitizeStyles` defaults to `false`. Enable it:

```bash
npx mjml <source.mjml> -o <output.html> --config.minify=true --sanitizeStyles
```

- `--config.allowMixedSyntax true` and `--config.templateSyntax` do **not** fix this on their own — verified against 5.4.0, both still throw.
- `--sanitizeStyles` protects `{{ }}` and `[[ ]]` only. Liquid `{% %}` still throws; declare it via `--config.templateSyntax` alongside `--sanitizeStyles`.
- A tag inside `<mj-style inline="inline">` cannot be rescued by any flag — Juice mangles it before PostCSS runs. Move it to a component attribute instead.

The reliable answer is to keep templating tags out of CSS entirely: put them in component attributes or `<mj-raw>`, not in `<mj-style>`.

---

## Implementation Standards

| Standard | Rule |
|----------|------|
| Idempotency | Running twice produces identical output — except `mj-navbar`, `mj-accordion` and `mj-carousel`, which emit a fresh random ID each compile. Do not diff their output to detect real changes |
| Clean Up | Remove partial `.html` if compilation fails |
| Logging | Always log the exact CLI command used (user can audit) |
| Version Pinning | New `package.json` → pin MJML to latest stable major (e.g. `^5.4.0`) |
