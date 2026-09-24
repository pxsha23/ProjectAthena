/**
 * Loads Monaco from the local npm package (no CDN) and builds the Athena editor
 * themes ("athena-dark" for Black, "athena-mocha" for Mocha) from the app's CSS variables.
 */
import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import EditorWorker from 'monaco-editor/editor/editor.worker?worker'
import CssWorker from 'monaco-editor/language/css/css.worker?worker'
import HtmlWorker from 'monaco-editor/language/html/html.worker?worker'
import JsonWorker from 'monaco-editor/language/json/json.worker?worker'
import TsWorker from 'monaco-editor/language/typescript/ts.worker?worker'
import type { ThemeId } from '@/lib/theme'

self.MonacoEnvironment = {
  getWorker(_workerId: string, label: string) {
    switch (label) {
      case 'json':
        return new JsonWorker()
      case 'css':
      case 'scss':
      case 'less':
        return new CssWorker()
      case 'html':
      case 'handlebars':
      case 'razor':
        return new HtmlWorker()
      case 'typescript':
      case 'javascript':
        return new TsWorker()
      default:
        return new EditorWorker()
    }
  },
}

/** Reads the active theme's palette from the CSS variables in globals.css. */
function readPalette() {
  const styles = getComputedStyle(document.documentElement)
  const v = (name: string) => styles.getPropertyValue(`--c-${name}`).trim()
  return {
    base: v('base'),
    panel: v('panel'),
    raised: v('raised'),
    border: v('border'),
    text: v('text'),
    muted: v('muted'),
    subtle: v('subtle'),
    lavender: v('lavender'),
    mauve: v('mauve'),
    green: v('green'),
    peach: v('peach'),
    red: v('red'),
    sky: v('sky'),
    yellow: v('yellow'),
    pink: v('pink'),
  }
}

/** "#rrggbb" + opacity → "#rrggbbaa" (Monaco only accepts hex colours). */
function alpha(hex: string, opacity: number): string {
  return hex + Math.round(Math.min(1, Math.max(0, opacity)) * 255).toString(16).padStart(2, '0')
}

const strip = (hex: string) => hex.replace('#', '')

/**
 * (Re)defines the Monaco theme for the current app theme and returns its name.
 * Call after data-theme has been applied to <html>.
 */
export function defineAthenaTheme(theme: ThemeId): string {
  const t = readPalette()
  const name = theme === 'black' ? 'athena-dark' : `athena-${theme}`
  monaco.editor.defineTheme(name, {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: '', foreground: strip(t.text) },
      { token: 'comment', foreground: strip(t.subtle), fontStyle: 'italic' },
      { token: 'keyword', foreground: strip(t.mauve) },
      { token: 'keyword.control', foreground: strip(t.mauve) },
      { token: 'storage', foreground: strip(t.mauve) },
      { token: 'string', foreground: strip(t.green) },
      { token: 'string.escape', foreground: strip(t.pink) },
      { token: 'number', foreground: strip(t.peach) },
      { token: 'regexp', foreground: strip(t.pink) },
      { token: 'type', foreground: strip(t.yellow) },
      { token: 'type.identifier', foreground: strip(t.yellow) },
      { token: 'identifier', foreground: strip(t.text) },
      { token: 'function', foreground: strip(t.lavender) },
      { token: 'delimiter', foreground: strip(t.muted) },
      { token: 'delimiter.bracket', foreground: strip(t.muted) },
      { token: 'tag', foreground: strip(t.mauve) },
      { token: 'attribute.name', foreground: strip(t.yellow) },
      { token: 'attribute.value', foreground: strip(t.green) },
      { token: 'key', foreground: strip(t.lavender) },
      { token: 'string.key.json', foreground: strip(t.lavender) },
      { token: 'string.value.json', foreground: strip(t.green) },
      { token: 'type.yaml', foreground: strip(t.lavender) },
      { token: 'variable', foreground: strip(t.text) },
      { token: 'variable.predefined', foreground: strip(t.red) },
      { token: 'constant', foreground: strip(t.peach) },
      { token: 'annotation', foreground: strip(t.yellow) },
      { token: 'metatag', foreground: strip(t.pink) },
      { token: 'emphasis', fontStyle: 'italic' },
      { token: 'strong', fontStyle: 'bold' },
      { token: 'keyword.md', foreground: strip(t.lavender) },
    ],
    colors: {
      'editor.background': t.panel,
      'editor.foreground': t.text,
      'editorLineNumber.foreground': t.subtle,
      'editorLineNumber.activeForeground': t.lavender,
      'editorCursor.foreground': t.lavender,
      'editor.selectionBackground': alpha(t.lavender, 0.22),
      'editor.inactiveSelectionBackground': alpha(t.lavender, 0.12),
      'editor.lineHighlightBackground': alpha(t.raised, 0.6),
      'editor.lineHighlightBorder': alpha(t.base, 0),
      'editor.findMatchBackground': alpha(t.peach, 0.3),
      'editor.findMatchHighlightBackground': alpha(t.yellow, 0.18),
      'editorBracketMatch.background': alpha(t.lavender, 0.15),
      'editorBracketMatch.border': alpha(t.lavender, 0.5),
      'editorIndentGuide.background1': alpha(t.border, 0.6),
      'editorIndentGuide.activeBackground1': t.border,
      'editorWhitespace.foreground': alpha(t.border, 0.7),
      'editorWidget.background': t.panel,
      'editorWidget.border': t.border,
      'editorSuggestWidget.background': t.panel,
      'editorSuggestWidget.border': t.border,
      'editorSuggestWidget.selectedBackground': t.raised,
      'editorHoverWidget.background': t.panel,
      'editorHoverWidget.border': t.border,
      'editorGutter.background': t.panel,
      'scrollbarSlider.background': alpha(t.raised, 0.8),
      'scrollbarSlider.hoverBackground': t.raised,
      'scrollbarSlider.activeBackground': t.border,
      'minimap.background': t.panel,
      focusBorder: alpha(t.lavender, 0.6),
      'input.background': t.raised,
      'input.border': t.border,
      'dropdown.background': t.panel,
      'list.hoverBackground': t.raised,
      'list.activeSelectionBackground': t.raised,
    },
  })
  return name
}

loader.config({ monaco })

export { monaco }
