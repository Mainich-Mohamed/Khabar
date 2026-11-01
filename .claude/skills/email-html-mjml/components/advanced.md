# MJML Advanced Components Reference

## mj-hero
Full-width banner section with background image support. Behaves like `mj-section` with a single `mj-column`, but generates VML for Outlook background image support.

Two modes:
- `fixed-height` (**the default**): uses the `height` attribute, which itself defaults to `0px`
- `fluid-height`: expands based on content — **must be set explicitly**

⚠️ **Always set `mode` and `height`.** The default is `fixed-height` with `height="0px"`, so a hero with no `mode` compiles clean at exit `0` and renders as a **zero-height, invisible hero** (`<td ... style="height:0px;" height="0">`). Verified identical in MJML 4 and 5.

| Attribute | Accepts | Default |
|-----------|---------|---------|
| mode | fluid-height / fixed-height | **fixed-height** |
| height | px / % | 0px (required for fixed-height) |
| background-url | URL | null |
| background-color | CSS color | #ffffff |
| background-width | px / % | parent width (mandatory) |
| background-height | px / % | — (mandatory) |
| background-position | CSS keyword | center center |
| border-radius | string | — |
| vertical-align | top/middle/bottom | top |
| inner-background-color | CSS color | — |
| inner-padding | px / % | — |
| padding | px / % | 0px |

**Required attributes**: `background-width` and `background-height` — use the image's exact pixel dimensions. "Required" is a rendering requirement, **not** a validator one: a hero without them compiles clean at exit `0` even under `--config.validationLevel=strict`. The cost is silent Outlook degradation — the generated `<v:image>` loses its `height`, so the hero collapses in Outlook while looking correct everywhere else.

**MJML 5 change**: `inner-padding` now applies consistently across all clients (previously it only affected Outlook's inner table). Re-check hero spacing visually if migrating a v4 template that relied on the old Outlook-only behavior.

**Fallback**: Always set `background-color` for clients that don't support background images.

**Outlook**: Background images in `mj-hero` work in Outlook (VML generated). Use keyword positions only (top, center, bottom) — pixel values ignored by Outlook.

```xml
<!-- Fixed height hero -->
<mj-hero
  mode="fixed-height"
  height="400px"
  background-url="https://cdn.example.com/hero.jpg"
  background-width="600px"
  background-height="400px"
  background-color="#1a1a2e"
  padding="80px 0">
  <mj-text align="center" color="#ffffff" font-size="36px" font-weight="bold"
    font-family="Arial, sans-serif" line-height="44px">
    Summer Sale — Up to 50% Off
  </mj-text>
  <mj-button href="https://example.com/sale" align="center"
    background-color="#E63946" color="#ffffff">
    Shop the Sale
  </mj-button>
</mj-hero>
```

```xml
<!-- Fluid height hero -->
<mj-hero
  mode="fluid-height"
  background-url="https://cdn.example.com/banner.jpg"
  background-width="600px"
  background-height="300px"
  background-color="#2a3448"
  padding="60px 0">
  <mj-text align="center" color="#ffffff" font-size="28px">
    New Arrivals
  </mj-text>
</mj-hero>
```

---

## mj-raw
Outputs raw HTML/text without MJML processing. Use for:
- Template engine tags (Handlebars, Liquid, Jinja)
- Custom HTML not achievable with MJML components
- Content before `<!doctype html>` (with `position="file-start"`)

| Attribute | Accepts | Description |
|-----------|---------|-------------|
| position | "file-start" | Places content before doctype |

**In mj-body**: inserted as-is in the email body.
**In mj-head**: content added at end of HTML `<head>`.
**Outside mj-head/mj-body + position="file-start"**: added before doctype.

```xml
<!-- Protecting template tags from minifier -->
<mj-raw>
  <!-- htmlmin:ignore --> {% if user.first_name %} <!-- htmlmin:ignore -->
</mj-raw>
<mj-text>Hello {{ user.first_name }}!</mj-text>
<mj-raw>
  {% else %}
</mj-raw>
<mj-text>Hello there!</mj-text>
<mj-raw>
  {% endif %}
</mj-raw>
```

**Minify warning**: The `<` character causes parse errors with minify. Wrap in `<!-- htmlmin:ignore -->` tags or use `&lt;`.

---

## mj-include
Includes an external `.mjml`, `.css`, or `.html` file at compile time.

| Attribute | Accepts | Description |
|-----------|---------|-------------|
| path | string | Relative path to file |
| type | css / html | Specify for non-mjml files |
| css-inline | "inline" | Inline the CSS (type="css" only) |

**MJML 5: disabled by default.** `<mj-include>` tags are silently ignored — with just a console warning, no error — unless includes are explicitly enabled. This is a deliberate security change to prevent path traversal / arbitrary file reads via crafted include paths.

Enable includes:
- CLI: `--config.allowIncludes true`
- Node API: `ignoreIncludes: false`

Scope where includes may resolve from (in addition to the source file's own directory):
- CLI: `--config.includePath './partials'` (or a JSON array of paths: `'["../_common","../vendor"]'`)
- Node API: `includePath: ['/project/templates/_common']`

Absolute paths, UNC paths, Windows drive letters, null bytes, and symlinks that escape the allowed directories are rejected.

**Path bases differ**: the `path` attribute resolves relative to the *template file*, while a relative `--config.includePath` resolves relative to the *current working directory*. Denied includes are dropped silently (exit `0`, stderr warning only) — see `compilation.md`.

```xml
<!-- Include MJML partial -->
<mj-include path="./partials/header.mjml" />

<!-- Include CSS into head -->
<mj-include path="./styles/base.css" type="css" />
<mj-include path="./styles/inline.css" type="css" css-inline="inline" />

<!-- Include raw HTML -->
<mj-include path="./partials/footer.html" type="html" />
```

```bash
npx mjml template.mjml -o dist/template.html \
  --config.allowIncludes true \
  --config.includePath './partials'
```

**Tip**: Wrap partials in `<mjml><mj-body>` tags for preview in editors, then include via path in the main template.

Use `--config.filePath` CLI flag to set a base path for includes independent of the compiled file's location.
