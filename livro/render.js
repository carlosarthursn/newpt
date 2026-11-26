// Renderiza um HTML do livro em PDF (A4) e informa em que página caiu cada marcador @@id@@.
// Uso: node livro/render.js entrada.html saida.pdf [pb]
const { chromium } = require("playwright");
const { execFileSync } = require("child_process");
const path = require("path");

(async () => {
  const [inp, out, mode] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("file://" + path.resolve(inp), { waitUntil: "networkidle" });
  if (mode === "pb") {
    await page.evaluate(() => Promise.all(Array.from(document.images).map((img) => new Promise((ok) => {
      img.onload = img.onerror = ok;
      img.src = img.src.replace(/\.jpg$/, "-pb.jpg");
    }))));
  }
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: out, preferCSSPageSize: true, printBackground: true });
  await browser.close();

  const pages = parseInt(execFileSync("pdfinfo", [out]).toString().match(/Pages:\s+(\d+)/)[1], 10);
  const marks = {};
  for (let i = 1; i <= pages; i++) {
    const txt = execFileSync("pdftotext", ["-f", String(i), "-l", String(i), out, "-"]).toString();
    const re = /@@([a-z0-9-]+)@@/g;
    let m;
    while ((m = re.exec(txt))) if (!(m[1] in marks)) marks[m[1]] = i;
  }
  process.stdout.write(JSON.stringify({ pages, marks }));
})().catch((e) => { console.error(e); process.exit(1); });
