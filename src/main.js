import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile } from '@ffmpeg/util';
import { budget, MiB, MAX_INPUT_BYTES, parseMetadata } from './budget.js';
import './style.css';

const $ = id => document.getElementById(id);
let engine, file, info, busy = false, outputURL, generation = 0;
let watchdog;
const PROCESSING_LIMIT_MS = 5 * 60 * 1000;
const status = message => { $('status').textContent = message; };
const progress = value => { $('progress').hidden = false; $('progress').value = value; };
function clearResult() {
  $('result').hidden = true;
  $('preview').removeAttribute('src');
  $('preview').load();
  if (outputURL) URL.revokeObjectURL(outputURL);
  outputURL = undefined;
  $('download').removeAttribute('href');
}
function controls(active) {
  busy = active;
  for (const id of ['video', 'target', 'mode']) $(id).disabled = active;
  $('compress').disabled = active || !info;
  $('cancel').hidden = !active;
  if (!active) clearTimeout(watchdog);
}
function stopProcessing(message) {
  generation++;
  clearTimeout(watchdog);
  engine?.terminate(); engine = undefined;
  info = undefined; file = undefined;
  $('video').value = ''; $('metadata').hidden = true;
  $('progress').hidden = true; clearResult(); controls(false);
  status(message);
}
function startWatchdog(ms) {
  clearTimeout(watchdog);
  watchdog = setTimeout(() => stopProcessing('Processing stopped at the time limit. Try a shorter or lower-resolution video, or use desktop Chrome/Edge. Choose the video again to retry.'), ms);
}
function showResult(blob, target, unchanged = false) {
  outputURL = URL.createObjectURL(blob);
  $('download').href = outputURL;
  $('download').download = file.name.replace(/\.[^.]+$/, '') + '_optimized.mp4';
  $('preview').src = outputURL;
  $('summary').textContent = `${(file.size/MiB).toFixed(2)} MB → ${(blob.size/MiB).toFixed(2)} MB · Under your ${target} MB limit${unchanged ? ' · Original already fits; no encoding needed' : ''}`;
  $('result').hidden = false; progress(100);
  status(unchanged ? 'Your original MP4 already fits the limit. Download it immediately.' : 'Complete. Your optimized video is ready to download.');
}
function showError(error) {
  $('error').textContent = error.message || 'Processing failed. Try a smaller MP4 in desktop Chrome or Edge.';
  $('error').hidden = false;
}
async function loadEngine() {
  if (engine?.loaded) return engine;
  status('Loading the video engine (~32 MB on the first visit)…');
  engine = new FFmpeg();
  await engine.load({ coreURL: '/ffmpeg/0.12.10/ffmpeg-core.js', wasmURL: '/ffmpeg/0.12.10/ffmpeg-core.wasm' });
  return engine;
}
async function removeFiles(ff, names) {
  for (const name of names) { try { await ff.deleteFile(name); } catch { /* File may not have been created. */ } }
}

$('cancel').addEventListener('click', () => {
  stopProcessing('Processing cancelled. Choose your video again to restart.');
});

$('video').addEventListener('change', async () => {
  const token = ++generation;
  clearResult(); info = undefined; $('metadata').hidden = true; $('error').hidden = true;
  file = $('video').files[0];
  if (!file) { controls(false); status('Choose a video to get started.'); return; }
  if (file.size > MAX_INPUT_BYTES || file.size === 0) { showError(new Error('Choose a non-empty video smaller than 200 MB.')); controls(false); return; }
  if (!/\.(mp4|mov|avi|mkv|webm)$/i.test(file.name)) { showError(new Error('Choose an MP4, MOV, AVI, MKV or WebM file.')); controls(false); return; }
  controls(true); progress(0);
  startWatchdog(90000);
  try {
    const ff = await loadEngine();
    if (token !== generation) return;
    status('Reading video information…');
    await removeFiles(ff, ['metadata.json', 'input']);
    await ff.writeFile('input', await fetchFile(file));
    const probeLogs = [];
    const probeLogger = ({message}) => probeLogs.push(message);
    ff.on('log', probeLogger);
    let code;
    try { code = await ff.ffprobe(['-v', 'error', '-show_format', '-show_streams', '-of', 'json', 'input', '-o', 'metadata.json']); }
    finally { ff.off('log', probeLogger); }
    // Some single-thread core builds leave the return code at -1 on successful
    // ffprobe completion. Validate the generated metadata instead.
    let metadata;
    try { metadata = JSON.parse(new TextDecoder().decode(await ff.readFile('metadata.json'))); }
    catch { throw new Error(`This file could not be read (code ${code}). ${probeLogs.slice(-4).join(' ')}`); }
    if (token !== generation) return;
    info = parseMetadata(metadata);
    $('metadata').replaceChildren();
    for (const [label, value] of [['File', file.name], ['Size', `${(file.size/MiB).toFixed(1)} MB`], ['Resolution', `${info.width} × ${info.height}`], ['Duration', `${info.duration.toFixed(1)} seconds`]]) {
      const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = label; dd.textContent = value; $('metadata').append(dt, dd);
    }
    $('metadata').hidden = false;
    status('Ready. Choose your size limit and optimize.');
  } catch (error) { if (token === generation) { info = undefined; showError(error); status('Could not analyze this video.'); } }
  finally { if (token === generation) { controls(false); $('progress').hidden = true; } }
});

$('compress').addEventListener('click', async () => {
  if (busy || !info) return;
  const token = generation, target = Number($('target').value), mode = $('mode').value;
  $('error').hidden = true; clearResult();
  let ff, onLog, onProgress, ticker;
  try {
    if (!Number.isFinite(target) || target < 1 || target > 100) throw new Error('Choose an output size between 1 and 100 MB.');
    if (/\.mp4$/i.test(file.name) && file.size <= target * MiB) {
      showResult(file, target, true);
      return;
    }
    const settings = budget(info, target, mode);
    controls(true); progress(0);
    startWatchdog(PROCESSING_LIMIT_MS);
    ff = await loadEngine();
    const started = performance.now();
    let attempt = 0, attemptStarted = started, encodedSeconds = 0, lastProgress = 0, logs = [];
    ticker = setInterval(() => {
      if (token !== generation) return;
      const elapsed = Math.floor((performance.now() - started) / 1000);
      const fraction = Math.min(encodedSeconds / info.duration, 0.99);
      const attemptElapsed = (performance.now() - attemptStarted) / 1000;
      const remaining = fraction > 0.05 ? Math.ceil(attemptElapsed / fraction - attemptElapsed) : null;
      status(`${attempt ? 'Adjusting output size' : 'Encoding'}: ${encodedSeconds.toFixed(0)} / ${info.duration.toFixed(0)} seconds · ${elapsed}s elapsed${remaining === null ? '' : ` · ~${remaining}s remaining in this attempt`}. ${document.hidden ? 'Keep this tab visible for best speed.' : 'Keep this tab open.'}`);
    }, 1000);
    onLog = ({message}) => { logs.push(message); if (logs.length > 10) logs.shift(); };
    onProgress = ({progress: fraction}) => {
      if (token !== generation || !Number.isFinite(fraction)) return;
      encodedSeconds = Math.max(encodedSeconds, Math.max(0, Math.min(1, fraction)) * info.duration);
      const value = attempt * 90 + Math.max(0,Math.min(1,fraction)) * (attempt ? 9 : 90);
      lastProgress = Math.max(lastProgress, value); progress(Math.min(lastProgress,99));
    };
    ff.on('log', onLog); ff.on('progress', onProgress);
    let bitrate = settings.video, bytes;
    for (attempt = 0; attempt < 2; attempt++) {
        encodedSeconds = 0;
        attemptStarted = performance.now();
        status(`${attempt ? 'Adjusting output size' : 'Encoding video'}…`);
        const args = ['-y','-i','input','-map',`0:${info.videoIndex}`];
        if (info.hasAudio) args.push('-map',`0:${info.audioIndex}`);
        args.push('-vf',`scale=${settings.width}:${settings.height}:flags=fast_bilinear,setsar=1,fps=${settings.fps}`,'-c:v','libx264','-pix_fmt','yuv420p','-preset',settings.preset,'-b:v',`${bitrate}k`,'-maxrate',`${bitrate}k`,'-bufsize',`${bitrate * 2}k`);
          if (info.hasAudio) args.push('-c:a','aac','-b:a',`${settings.audio}k`,'-ar','44100','-ac','2'); else args.push('-an');
          args.push('-movflags','+faststart','output.mp4');
        if (await ff.exec(args) !== 0) throw new Error(`Video encoding failed. Try a smaller video or another quality mode. ${logs.slice(-3).join(' ')}`);
        if (token !== generation) return;
      bytes = await ff.readFile('output.mp4');
      if (token !== generation) return;
      if (bytes.byteLength <= target * MiB) break;
      bitrate = Math.max(100, Math.floor(bitrate * target * MiB / bytes.byteLength * 0.85));
    }
    if (bytes.byteLength > target * MiB) throw new Error('The output could not meet this size limit. Choose a larger limit or shorten the video.');
    showResult(new Blob([bytes], {type:'video/mp4'}), target);
  } catch(error) { if (token === generation) { showError(error); status('Optimization stopped. You can try again.'); } }
  finally {
    clearInterval(ticker);
    if (ff) {
      if (onLog) ff.off('log',onLog); if (onProgress) ff.off('progress',onProgress);
      if (token === generation) await removeFiles(ff,['output.mp4','encode-0.log','encode-0.log.mbtree']);
    }
    if (token === generation) controls(false);
  }
});
