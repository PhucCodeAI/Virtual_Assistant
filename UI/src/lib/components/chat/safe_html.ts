// src/lib/components/chat/safe_html.ts
//
// Whitelist sanitizer cho output của formatInline() và highlightCode().
//
// Ngữ cảnh bảo mật:
//   - formatInline() escape <>& TRƯỚC khi inject tag của chính nó.
//   - highlightCode() escape <>& TRƯỚC khi wrap span (xem highlighter.ts
//     dòng 3-5). Nhưng vẫn cần sanitizer vì highlighter dùng inline `style`
//     attribute — nếu ai đó sửa highlighter và quên escape, sanitizer chặn.
//
// Whitelist:
//   - Tag: markdown subset + span cho syntax highlighter.
//   - Attr: `class` (không giới hạn value) + `style` với whitelist
//     property cụ thể (color hex, font-style, font-weight).
//
// KHÔNG dùng làm sanitizer general-purpose. Nếu sau này cho phép user
// paste HTML thô → thay bằng DOMPurify.

const ALLOWED_TAGS = new Set<string>([
  // Markdown inline output
  "hr", "h1", "h2", "h3",
  "div", "span",
  "strong", "em", "code",
  "br", "li", "pre",
  // Syntax highlighter output (mọi span đều dùng tag này)
  "mark", "b", "i",
]);

// Bước 1: match mọi tag mở/đóng để strip tag lạ.
const TAG_RE = /<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g;

// Bước 2: parse từng attribute trong tag mở.
const OPEN_TAG_RE = /<([a-zA-Z][a-zA-Z0-9]*)([^>]*)>/g;
const ATTR_RE = /([a-zA-Z][a-zA-Z0-9-]*)(?:="([^"]*)")?/g;

// Whitelist cho `style` — mỗi segment (split bằng ;) phải match 1 trong các
// pattern sau. Bất kỳ segment nào fail → toàn bộ style bị strip.
const SAFE_STYLE_SEGMENTS: RegExp[] = [
  /^\s*color:\s*#[0-9a-fA-F]{3,8}\s*$/,
  /^\s*font-style:\s*(italic|normal)\s*$/,
  /^\s*font-weight:\s*(bold|normal|[1-9]00)\s*$/,
];

function isSafeStyleValue(value: string): boolean {
  const segments = value.split(";").filter((s) => s.trim().length > 0);
  if (segments.length === 0) return false;
  return segments.every((seg) =>
    SAFE_STYLE_SEGMENTS.some((re) => re.test(seg)),
  );
}

/**
 * Lọc HTML:
 *   1. Strip tag không nằm trong whitelist.
 *   2. Trên tag được phép, giữ `class` và `style` (nếu style value pass
 *      whitelist pattern). Mọi attr khác (onclick, onerror, href, src,
 *      data-*, ...) đều bị strip.
 */
export function sanitizeHtml(html: string): string {
  // Bước 1.
  const stripped = html.replace(TAG_RE, (match, tagName: string) => {
    return ALLOWED_TAGS.has(tagName.toLowerCase()) ? match : "";
  });

  // Bước 2.
  return stripped.replace(
    OPEN_TAG_RE,
    (match, tagName: string, attrsRaw: string) => {
      if (!attrsRaw.trim()) return match;

      const safeAttrs: string[] = [];
      const attrRe = new RegExp(ATTR_RE.source, "g");
      let m: RegExpExecArray | null;

      while ((m = attrRe.exec(attrsRaw)) !== null) {
        const name = m[1];
        const value = m[2];
        if (value === undefined) continue;

        if (name === "class") {
          safeAttrs.push(`class="${value}"`);
        } else if (name === "style" && isSafeStyleValue(value)) {
          safeAttrs.push(`style="${value}"`);
        }
        // mọi attr khác → bỏ
      }

      const selfClose = attrsRaw.trimEnd().endsWith("/") ? " /" : "";
      const attrsStr = safeAttrs.length > 0 ? " " + safeAttrs.join(" ") : "";
      return `<${tagName}${attrsStr}${selfClose}>`;
    },
  );
}