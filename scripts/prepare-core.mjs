import { mkdir, copyFile } from 'node:fs/promises';
const output = new URL('../public/ffmpeg/0.12.10/', import.meta.url);
await mkdir(output, { recursive: true });
for (const name of ['ffmpeg-core.js', 'ffmpeg-core.wasm']) {
  await copyFile(new URL(`../node_modules/@ffmpeg/core/dist/esm/${name}`, import.meta.url), new URL(name, output));
}
