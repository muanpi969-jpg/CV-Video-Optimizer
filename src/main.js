import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile } from '@ffmpeg/util';
import { budget, MiB, MAX_INPUT_BYTES, parseMetadata } from './budget.js';
import './style.css';

const $ = id => document.getElementById(id);
let engine, file, info, busy = false, outputURL, generation = 0;
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
  generation++;
  engine?.terminate(); engine = undefined;
  info = undefined; file = undefined;
  $('video').value = ''; $('metadata').hidden = true;
  $('progress').hidden = true; clearResult(); controls(false);
  status('Processing cancelled. Choose your video again to restart.');
});

$('video').addEventListener('change', async () => {
  const token = ++generation;
  clearResult(); info = undefined; $('metadata').hidden = true; $('error').hidden = true;
  file = $('video').files[0];
  if (!file) { controls(false); status('Choose a video to get started.'); return; }
  if (file.size > MAX_INPUT_BYTES || file.size === 0) { showError(new Error('Choose a non-empty video smaller than 200 MB.')); controls(false); return; }
  if (!/\.(mp4|mov|avi|mkv|webm)$/i.test(file.name)) { showError(new Error('Choose an MP4, MOV, AVI, MKV or WebM file.')); controls(false); return; }
  controls(true); progress(0);
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
  let ff, onLog, onProgress;
  try {
    const settings = budget(info, target, mode);
    controls(true); progress(0);
    ff = await loadEngine();
    let stage = 0, lastProgress = 0, logs = [];
    onLog = ({message}) => { logs.push(message); if (logs.length > 10) logs.shift(); };
    onProgress = ({progress: fraction}) => { const value = stage + Math.max(0,Math.min(1,fraction)) * 22; lastProgress = Math.max(lastProgress, value); progress(Math.min(lastProgress,99)); };
    ff.on('log', onLog); ff.on('progress', onProgress);
    let bitrate = settings.video, bytes;
    for (let attempt = 0; attempt < 2; attempt++) {
      for (let pass = 1; pass <= 2; pass++) {
        stage = attempt * 45 + (pass-1)*22;
        status(`${attempt ? 'Adjusting output size. ' : ''}Pass ${pass} of 2: ${pass === 1 ? 'analyzing' : 'encoding'}… Keep this tab open.`);
        const args = ['-y','-i','input','-map',`0:${info.videoIndex}`];
        if (pass === 2 && info.hasAudio) args.push('-map',`0:${info.audioIndex}`);
        args.push('-vf',`scale=${settings.width}:${settings.height}:flags=lanczos,setsar=1,fps=${mode === 'small' ? 24 : 30}`,'-c:v','libx264','-pix_fmt','yuv420p','-preset',mode === 'quality' ? 'medium' : 'fast','-b:v',`${bitrate}k`,'-pass',String(pass),'-passlogfile','encode');
        if (pass === 1) args.push('-an','-f','null','/dev/null');
        else {
          if (info.hasAudio) args.push('-c:a','aac','-b:a',`${settings.audio}k`,'-ar','44100','-ac','2'); else args.push('-an');
          args.push('-movflags','+faststart','output.mp4');
        }
        if (await ff.exec(args) !== 0) throw new Error(`Video encoding failed. Try a smaller video or another quality mode. ${logs.slice(-3).join(' ')}`);
        if (token !== generation) return;
      }
      bytes = await ff.readFile('output.mp4');
      if (token !== generation) return;
      if (bytes.byteLength <= target * MiB) break;
      bitrate = Math.max(100, Math.floor(bitrate * target * MiB / bytes.byteLength * 0.92));
    }
    if (bytes.byteLength > target * MiB) throw new Error('The output could not meet this size limit. Choose a larger limit or shorten the video.');
    outputURL = URL.createObjectURL(new Blob([bytes], {type:'video/mp4'}));
    $('download').href = outputURL; $('download').download = file.name.replace(/\.[^.]+$/, '') + '_optimized.mp4';
    $('preview').src = outputURL;
    $('summary').textContent = `${(file.size/MiB).toFixed(2)} MB → ${(bytes.byteLength/MiB).toFixed(2)} MB · Under your ${target} MB limit`;
    $('result').hidden = false; progress(100); status('Complete. Your optimized video is ready to download.');
  } catch(error) { if (token === generation) { showError(error); status('Optimization stopped. You can try again.'); } }
  finally {
    if (ff) {
      if (onLog) ff.off('log',onLog); if (onProgress) ff.off('progress',onProgress);
      if (token === generation) await removeFiles(ff,['output.mp4','encode-0.log','encode-0.log.mbtree']);
    }
    if (token === generation) controls(false);
  }
});
