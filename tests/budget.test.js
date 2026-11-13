import test from "node:test";
import assert from "node:assert/strict";
import { budget, parseMetadata } from "../src/budget.js";
const info = { duration: 60, width: 1920, height: 1080, hasAudio: true };
test("balanced budget retains 720p when 1080p is too expensive", () => {
  const result = budget(info, 10, "balanced");
  assert.equal(result.height, 720);
  assert.equal(result.width, 1280);
});
test("portrait video keeps aspect ratio and even dimensions", () => {
  const result = budget({ ...info, width: 1080, height: 1920 }, 10, "balanced");
  assert.equal(result.width, 720);
  assert.equal(result.height, 1280);
});
test("silent input uses no audio budget", () => {
  assert.equal(budget({ ...info, hasAudio: false }, 10, "balanced").audio, 0);
});
test("invalid duration and impossible targets fail usefully", () => {
  assert.throws(
    () => budget({ ...info, duration: NaN }, 10, "balanced"),
    /duration/,
  );
  assert.throws(
    () => budget({ ...info, duration: 3600 }, 1, "balanced"),
    /too long/,
  );
  assert.throws(() => budget(info, NaN, "balanced"), /between/);
});
test("metadata preserves track index and accounts for rotation", () => {
  const parsed = parseMetadata({
    format: { duration: "12" },
    streams: [
      { index: 0, codec_type: "video", disposition: { attached_pic: 1 } },
      {
        index: 1,
        codec_type: "video",
        width: 1920,
        height: 1080,
        side_data_list: [{ rotation: 90 }],
      },
      { index: 2, codec_type: "audio" },
    ],
  });
  assert.equal(parsed.width, 1080);
  assert.equal(parsed.height, 1920);
  assert.equal(parsed.videoIndex, 1);
  assert.equal(parsed.audioIndex, 2);
});
test("missing video track is rejected", () =>
  assert.throws(() => parseMetadata({ streams: [] }), /No video/));
test("default caps 4K work at 720p/24fps and uses the fast preset", () => {
  const result = budget(
    { ...info, width: 3840, height: 2160, fps: 60 },
    100,
    "rssp",
  );
  assert.deepEqual(
    [result.width, result.height, result.fps, result.preset],
    [1280, 720, 24, "ultrafast"],
  );
});
test("low source frame rates are preserved and quality is capped at 1080p", () => {
  const result = budget(
    { ...info, width: 3840, height: 2160, fps: 15 },
    100,
    "quality",
  );
  assert.deepEqual(
    [result.width, result.height, result.fps, result.preset],
    [1920, 1080, 15, "veryfast"],
  );
});
test("copied AAC bitrate is reserved instead of under-budgeting the output audio", () => {
  const copied = budget({ ...info, copyAudioBitrate: 320 }, 20, "rssp");
  const transcoded = budget(info, 20, "rssp");
  assert.equal(copied.audio, 320);
  assert.equal(transcoded.video - copied.video, 320 - 128);
});
