function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderInlineMarkdown(value) {
  value = value.replace(/`([^`]+)`/g, "<code>$1</code>");
  value = value.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  value = value.replace(/\*(.*?)\*/g, "<em>$1</em>");
  return value;
}

function isTable(lines, i) {
  if (i + 1 >= lines.length) return false;
  const heading = lines[i].trim();
  const separator = lines[i + 1].trim();
  return (
    heading.startsWith("|") &&
    heading.endsWith("|") &&
    /^\|[\s:-]+\|[\s|:-]*$/.test(separator)
  );
}

function parseRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => renderInlineMarkdown(escapeHtml(cell.trim())));
}

export function renderMarkdown(markdown) {
  if (typeof markdown !== "string") {
    console.error("renderMarkdown expected a string, received:", markdown);
    return "<p>Unable to render the response.</p>";
  }

  const lines = markdown.split(/\r?\n/);
  const parts = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();

    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(escapeHtml(lines[i]));
        i++;
      }
      i++;
      parts.push(
        `<pre><code${lang ? ` class="lang-${lang}"` : ""}>${codeLines.join("\n")}</code></pre>`
      );
      continue;
    }

    if (!line) {
      i++;
      continue;
    }

    const headingMatch = /^(#{1,6})\s+(.*)$/.exec(line);
    if (headingMatch) {
      const level = headingMatch[1].length;
      parts.push(`<h${level}>${renderInlineMarkdown(escapeHtml(headingMatch[2]))}</h${level}>`);
      i++;
      continue;
    }

    if (isTable(lines, i)) {
      const headers = parseRow(lines[i]);
      const rows = [];
      i += 2;
      while (
        i < lines.length &&
        lines[i].trim().startsWith("|") &&
        lines[i].trim().endsWith("|")
      ) {
        rows.push(parseRow(lines[i]));
        i++;
      }
      parts.push(
        `<table><thead><tr>${headers
          .map((cell) => `<th>${cell}</th>`)
          .join("")}</tr></thead><tbody>${rows
          .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
          .join("")}</tbody></table>`
      );
      continue;
    }

    if (line.startsWith(">")) {
      parts.push(
        `<blockquote>${renderInlineMarkdown(escapeHtml(line.slice(1).trim()))}</blockquote>`
      );
      i++;
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ""));
        i++;
      }
      parts.push(
        `<ul>${items
          .map((item) => `<li>${renderInlineMarkdown(escapeHtml(item))}</li>`)
          .join("")}</ul>`
      );
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i++;
      }
      parts.push(
        `<ol>${items
          .map((item) => `<li>${renderInlineMarkdown(escapeHtml(item))}</li>`)
          .join("")}</ol>`
      );
      continue;
    }

    parts.push(`<p>${renderInlineMarkdown(escapeHtml(line))}</p>`);
    i++;
  }

  return parts.join("");
}

export { escapeHtml };
