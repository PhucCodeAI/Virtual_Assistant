function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

interface Token {
  type: string;
  value: string;
}

const RULES: [string, RegExp][] = [
  ['comment', /^(\/\/|#)[^\n]*/],

  ['string', /^(?:f?("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|`(?:[^`\\]|\\.)*`)/],

  ['keyword', /^(?:import|from|as|return|async|await|yield|raise|try|except|finally|if|elif|else|for|while|with|break|continue|catch|throw)\b/],

  ['definition', /^(?:def|class|lambda|function|const|let|var)\b/],

  ['constant', /^(?:None|True|False|true|false|null|undefined|self|this)\b/],

  ['type', /^(?:str|int|float|bool|list|dict|set|tuple|Dict|Any|Optional|List|Union|Callable|Promise|Array|Record|string|number|boolean|void)\b/],

  ['number', /^\b\d+(?:\.\d+)?\b/],

  ['function', /^[a-zA-Z_]\w*(?=\s*\()/],

  ['operator', /^(?:=>|->|===|!==|==|!=|<=|>=|[=+\-*/%&|^!<>])/],

  ['ident', /^[a-zA-Z_]\w*/],

  ['space', /^\s+/],

  ['other', /^./]
];

function tokenize(code: string): Token[] {
  const tokens: Token[] = [];
  let remaining = code;

  while (remaining.length > 0) {
    let matched = false;
    for (const [type, regex] of RULES) {
      const match = remaining.match(regex);
      if (match) {
        tokens.push({ type, value: match[0] });
        remaining = remaining.slice(match[0].length);
        matched = true;
        break;
      }
    }
    if (!matched) {
      tokens.push({ type: 'other', value: remaining[0] });
      remaining = remaining.slice(1);
    }
  }
  return tokens;
}

function styleToken(token: Token): string {
  const escaped = escapeHtml(token.value);
  switch (token.type) {
    case 'comment':
      return `<span style="color:#6a9955;font-style:italic;">${escaped}</span>`;
    case 'string':
      return `<span style="color:#ce9178;">${escaped}</span>`;
    case 'keyword':
      return `<span style="color:#c586c0;font-weight:600;">${escaped}</span>`;
    case 'definition':
      return `<span style="color:#569cd6;font-weight:600;">${escaped}</span>`;
    case 'constant':
      return `<span style="color:#569cd6;">${escaped}</span>`;
    case 'type':
      return `<span style="color:#4ec9b0;">${escaped}</span>`;
    case 'function':
      return `<span style="color:#dcdcaa;">${escaped}</span>`;
    case 'number':
      return `<span style="color:#b5cea8;">${escaped}</span>`;
    case 'operator':
      return `<span style="color:#d4d4d8;">${escaped}</span>`;
    case 'ident':
      return `<span style="color:#9cdcfe;">${escaped}</span>`;
    default:
      return escaped;
  }
}

export function highlightCode(code: string): string {
  const tokens = tokenize(code);
  return tokens.map(styleToken).join('');
}