# Smart Video CV Optimizer

A Vercel-ready app for compressing application videos to a selected size limit. FFmpeg WebAssembly runs in the visitor's browser. Video files are never uploaded to Vercel; no API keys or backend services are required.

## Deploy to Vercel

1. Import `muanpi969-jpg/CV-Video-Optimizer` into Vercel and select `main`.
2. Keep the root directory at the repository root. Select the **Vite** framework.
3. Build command: `npm run build`. Output directory: `dist`. These settings are also in `vercel.json`.
4. Deploy. No environment variables are needed. Future pushes to the connected branch trigger deployments.

This version replaces Streamlit. Use the new Vercel URL; Streamlit Cloud no longer runs this version.

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

The build copies the pinned single-thread FFmpeg core and WebAssembly into versioned static assets. All processing assets are served from your deployment. No cross-origin isolation or serverless video encoding is required.

## Workflow and limits

- MP4, MOV, AVI, MKV and WebM input, up to 200 MB. Actual capacity depends on device memory.
- H.264 / AAC MP4 output with a fast single-pass encoder, portrait-aware scaling, and one corrective retry only if the result exceeds the target.
- The default uses an ultrafast preset with a maximum 720p short edge and 24 fps. Balanced allows up to 30 fps; Higher quality uses a slower preset capped at 1080p. These caps trade detail for faster browser processing. Source frame rates below the cap are preserved.
- MP4 files already below the chosen limit can be downloaded immediately without re-encoding.
- Live elapsed time and estimated remaining time appear during encoding. A five-minute overall processing limit stops expensive jobs and releases the worker; analysis has a separate 90-second limit.
- Targets between 1 and 100 MB. Impossibly small targets show a clear message. Oversized output is never labeled successful.
- Cancel stops the worker. Choose the video again after cancellation.
- Desktop Chrome or Edge is recommended. Mobile browsers and large/4K videos may run out of memory. The first analysis downloads an approximately 32 MB engine; browser encoding is slower than native FFmpeg.

The processing engine is distributed under its upstream licenses, including GPL components. See the `@ffmpeg/core` and FFmpeg project licenses before redistributing modified builds.
