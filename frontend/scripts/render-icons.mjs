#!/usr/bin/env node
// Renders the PNG icons in public/ from their SVG sources with headless Chrome.
// No npm dependency needed; Chrome is auto-detected or taken from $CHROME.
//
//   node scripts/render-icons.mjs
//   CHROME=/path/to/chrome node scripts/render-icons.mjs
import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const publicDir = resolve(dirname(fileURLToPath(import.meta.url)), '../public')

const TARGETS = [
  // iOS home screen (Safari ignores the manifest icons and only reads apple-touch-icon)
  { out: 'apple-touch-icon.png', src: 'app-icon.svg', size: 180 },
  // Android / desktop PWA install (referenced from site.webmanifest)
  { out: 'app-icon-192.png', src: 'app-icon.svg', size: 192 },
  { out: 'app-icon-512.png', src: 'app-icon.svg', size: 512 },
  // Fallback favicons for browsers without SVG favicon support
  { out: 'favicon-32.png', src: 'favicon.svg', size: 32 },
  { out: 'favicon-16.png', src: 'favicon.svg', size: 16 },
]

const CHROME_CANDIDATES = [
  process.env.CHROME,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].filter(Boolean)

const chrome = CHROME_CANDIDATES.find((p) => existsSync(p))
if (!chrome) {
  console.error('Chrome not found. Set CHROME=/path/to/chrome and retry.')
  process.exit(1)
}

const work = mkdtempSync(join(tmpdir(), 'metermachen-icons-'))
try {
  for (const { out, src, size } of TARGETS) {
    const page = join(work, `${out}.html`)
    writeFileSync(
      page,
      `<!doctype html><html><head><style>` +
        `html,body{margin:0;background:transparent;overflow:hidden}` +
        `img{display:block;width:${size}px;height:${size}px}` +
        `</style></head><body><img src="${pathToFileURL(join(publicDir, src)).href}"></body></html>`,
    )
    execFileSync(
      chrome,
      [
        '--headless=new',
        '--disable-gpu',
        '--hide-scrollbars',
        '--no-first-run',
        '--no-default-browser-check',
        '--force-device-scale-factor=1',
        `--user-data-dir=${join(work, 'profile')}`,
        '--default-background-color=00000000',
        `--window-size=${size},${size}`,
        `--screenshot=${join(publicDir, out)}`,
        pathToFileURL(page).href,
      ],
      { stdio: 'ignore' },
    )
    console.log(`${out}  ${size}x${size}`)
  }
} finally {
  rmSync(work, { recursive: true, force: true })
}
