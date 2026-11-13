export const MiB = 1024 * 1024;
export const MAX_INPUT_BYTES = 200 * MiB;

export function budget(info, targetMB, mode) {
  if (!Number.isFinite(info.duration) || info.duration <= 0) throw new Error('This video has no usable duration. Try exporting it as MP4 first.');
  if (!Number.isFinite(targetMB) || targetMB < 1 || targetMB > 100) throw new Error('Choose an output size between 1 and 100 MB.');
  if (!(info.width >= 2 && info.height >= 2)) throw new Error('Could not read the video dimensions.');
  const audio = info.hasAudio ? (mode === 'quality' ? 192 : mode === 'small' ? 96 : 128) : 0;
  const video = Math.floor(targetMB * MiB * 8 * 0.94 / info.duration / 1000 - audio);
  if (video < 150) throw new Error(`This video is too long for that limit. Choose at least ${Math.ceil((150 + audio) * 1000 * info.duration / 8 / MiB / 0.94)} MB or shorten the video.`);
  const tiers = mode === 'quality' ? [[2160,8000],[1440,5000],[1080,3000],[720,1500],[480,800],[360,0]] : [[2160,5000],[1440,3000],[1080,1500],[720,900],[480,500],[360,0]];
  const shortEdge = Math.min(info.width, info.height);
  const edge = tiers.find(([size, floor]) => size <= shortEdge && video >= floor)?.[0] ?? Math.min(shortEdge, 360);
  const ratio = Math.min(1, edge / shortEdge);
  return { video: Math.min(video, 20000), audio, width: Math.max(2, Math.floor(info.width * ratio / 2) * 2), height: Math.max(2, Math.floor(info.height * ratio / 2) * 2) };
}

export function parseMetadata(data) {
  const streams = data.streams ?? [];
  const stream = streams.find(s => s.codec_type === 'video' && !s.disposition?.attached_pic);
  if (!stream) throw new Error('No video track found. Choose a playable video file.');
  let width = Number(stream.width), height = Number(stream.height);
  const rotation = Number(stream.side_data_list?.find(s => s.rotation !== undefined)?.rotation ?? stream.tags?.rotate ?? 0);
  if (Math.abs(rotation) % 180 === 90) [width, height] = [height, width];
  const duration = Number(data.format?.duration) || Number(stream.duration);
  if (!Number.isFinite(duration) || duration <= 0) throw new Error('Could not read the video duration. Try exporting it as MP4 first.');
  return { width, height, duration, videoIndex: stream.index, audioIndex: streams.find(s => s.codec_type === 'audio')?.index, hasAudio: streams.some(s => s.codec_type === 'audio') };
}
