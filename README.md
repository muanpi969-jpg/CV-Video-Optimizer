# Smart Video CV Optimizer

A Vercel-ready app for compressing application videos to a selected size limit. The default encoder uses native browser video codecs (WebCodecs), allowing the browser to use hardware acceleration where supported. Video files are never uploaded to Vercel; no API keys or backend services are required.



## Develop locally

Use Node.js 22 or newer.

```sh
npm ci
npm run dev
```

```sh
npm test
npm run build
npm run preview
```

Native mode reads the file directly using BlobSource rather than copying the entire file into a WebAssembly filesystem. Mediabunny handles demuxing, native decode/encode, resizing, and MP4 muxing. Existing AAC audio is copied without re-encoding and its bitrate is included in the output size budget.

Compatibility mode uses a pinned single-thread FFmpeg core for formats or codecs the browser cannot handle. It is explicitly selected, because software WebAssembly encoding can be much slower for long/high-resolution videos. Its approximately 32 MB engine is downloaded only when that mode is used. All processing assets are served from your deployment. No cross-origin isolation or serverless video encoding is required.

## Workflow and limits

- MP4, MOV, AVI, MKV and WebM input, up to 200 MB. Actual capacity depends on device memory.
- H.264 / AAC MP4 output with a fast single-pass encoder, portrait-aware scaling, and one corrective retry only if the result exceeds the target.
- The default caps the short edge at 720p and frame rate at 24 fps. Balanced allows up to 30 fps; Higher quality is capped at 1080p. These caps trade detail for faster browser processing. Source frame rates below the cap are preserved. The compatibility encoder uses ultrafast/veryfast presets; native mode uses browser codec rate control.
- MP4 files already below the chosen limit can be downloaded immediately without re-encoding.
- Live elapsed time and estimated remaining time appear during encoding. A five-minute overall processing limit stops expensive jobs and releases the worker; analysis has a separate 90-second limit.
- Targets between 1 and 100 MB. Impossibly small targets show a clear message. Oversized output is never labeled successful.
- Cancel stops the worker. Choose the video again after cancellation.
- Current desktop Chrome, Edge or Safari is recommended for native encoding. Browser, input codec and hardware determine acceleration availability; it is not guaranteed on every device. Native mode displays a clear error if it cannot preserve the required tracks; choose Compatibility mode explicitly in that case. Mobile browsers and large/4K videos may run out of memory.

The page footer identifies this version as **Native encoder release 2.1**, making it easy to distinguish from older software-only deployments. After deploying, refresh or reopen the page before starting a new job.

The processing engine is distributed under its upstream licenses, including GPL components. See the `@ffmpeg/core` and FFmpeg project licenses before redistributing modified builds.
