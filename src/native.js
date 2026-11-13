import {
  Input,
  BlobSource,
  ALL_FORMATS,
  Output,
  BufferTarget,
  Mp4OutputFormat,
  Conversion,
  Quality,
} from "mediabunny";

const open = (file) =>
  new Input({ source: new BlobSource(file), formats: ALL_FORMATS });

export async function inspectNative(file) {
  if (
    typeof VideoEncoder === "undefined" ||
    typeof VideoDecoder === "undefined"
  ) {
    throw new Error(
      "Native video encoding is unavailable in this browser. Try current Chrome or Safari, or select Compatibility mode.",
    );
  }
  const input = open(file);
  try {
    const video = await input.getPrimaryVideoTrack();
    const audio = await input.getPrimaryAudioTrack();
    if (!video) throw new Error("No video track found.");
    if (!(await video.canDecode()))
      throw new Error(
        "Your browser cannot decode this video. Try Chrome/Safari or select Compatibility mode.",
      );
    const duration =
      (await input.getDurationFromMetadata()) ??
      (await input.computeDuration());
    if (!Number.isFinite(duration) || duration <= 0)
      throw new Error("Could not read a valid video duration.");
    const stats = await video.computePacketStats(60);
    const copyAudio = audio && (await audio.getCodec()) === "aac";
    return {
      width: await video.getDisplayWidth(),
      height: await video.getDisplayHeight(),
      duration,
      fps: stats.averagePacketRate || 30,
      hasAudio: !!audio,
      copyAudioBitrate: copyAudio
        ? Math.ceil(((await audio.getAverageBitrate()) || 256000) / 1000)
        : undefined,
      path: "native",
    };
  } finally {
    input.dispose();
  }
}

export async function encodeNative(
  file,
  settings,
  { signal, onProgress, onConversion },
) {
  const input = open(file);
  let conversion;
  const cancel = () => {
    void conversion?.cancel().catch(() => {});
    input.dispose();
  };
  signal.addEventListener("abort", cancel, { once: true });
  try {
    signal.throwIfAborted();
    const audio = await input.getPrimaryAudioTrack();
    const copyAudio = audio && (await audio.getCodec()) === "aac";
    const target = new BufferTarget();
    const output = new Output({
      format: new Mp4OutputFormat({ fastStart: "in-memory" }),
      target,
    });
    conversion = await Conversion.init({
      input,
      output,
      tracks: "primary",
      showWarnings: false,
      video: {
        codec: "avc",
        width: settings.width,
        height: settings.height,
        fit: "contain",
        frameRate: settings.fps,
        quality: new Quality({
          bitrate: settings.video * 1000,
          bitrateMode: "constant",
        }),
        hardwareAcceleration: "no-preference",
        forceTranscode: true,
        allowTransformationMetadata: false,
      },
      // Existing AAC packets can be muxed directly. This preserves the voice,
      // avoids needless audio encoding, and works without a browser AAC encoder.
      audio: !audio
        ? { discard: true }
        : copyAudio
        ? { codec: "aac" }
        : {
            codec: "aac",
            bitrate: settings.audio * 1000,
            numberOfChannels: 2,
            sampleRate: 44100,
          },
    });
    signal.throwIfAborted();
    if (
      !conversion.isValid ||
      conversion.discardedTracks.some(
        (track) => track.reason !== "discarded_by_user",
      )
    ) {
      throw new Error(
        "Your browser cannot encode all of this video’s tracks as MP4. Try current Chrome/Safari or choose Compatibility mode.",
      );
    }
    onConversion?.(conversion);
    conversion.onProgress = onProgress;
    await conversion.execute();
    signal.throwIfAborted();
    if (!target.buffer?.byteLength)
      throw new Error("The browser encoder produced an empty video.");
    return new Uint8Array(target.buffer);
  } finally {
    signal.removeEventListener("abort", cancel);
    if (conversion && conversion.state !== "done")
      await conversion.cancel().catch(() => {});
    input.dispose();
  }
}
