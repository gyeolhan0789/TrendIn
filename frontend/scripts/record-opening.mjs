/*
 * /opening 화면을 1920x1080 영상으로 받아 내는 스크립트입니다.
 *
 * 화면 녹화가 아니라 프레임을 한 장씩 당겨 옵니다. 오프닝은 시각 t 만으로 그림이 정해지도록
 * 짜 두었으므로(openingTimeline.ts), 브라우저에 t 를 주고 그려진 판을 받으면 몇 초가 걸리든
 * 30fps 가 정확히 떨어집니다. 실시간 녹화처럼 프레임을 흘리거나 재생이 끊길 일이 없습니다.
 *
 *   1) 프런트 dev 서버를 띄웁니다.            npm run dev
 *   2) 이 스크립트로 PNG 240 장을 받습니다.    node scripts/record-opening.mjs
 *   3) ffmpeg 로 MP4 를 묶습니다.              아래 안내가 명령을 그대로 찍어 줍니다.
 *
 * playwright 는 이 저장소의 의존성이 아닙니다(팀 공용 package.json 을 건드리지 않으려고
 * 일부러 넣지 않았습니다). 따로 설치한 뒤 NODE_PATH 로 가리켜 주세요 — 자세한 방법은
 * docs/opening-video.md 에 적어 두었습니다.
 */
import { spawnSync } from 'node:child_process';
import { mkdir, rm, readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';

/*
 * playwright 와 ffmpeg-static 은 이 저장소의 의존성이 아닙니다. 발표 자료를 만들 때만 쓰는
 * 무거운 꾸러미를 팀 공용 package.json 에 얹고 싶지 않아서입니다. 아무 데나 설치한 뒤
 * PLAYWRIGHT_PATH 로 그 폴더를 가리키면 거기서 찾아 씁니다. frontend 에 직접 설치했다면
 * 환경 변수 없이도 그냥 잡힙니다.
 */
const resolveRoot = process.env.PLAYWRIGHT_PATH ?? import.meta.dirname;
const requireFrom = createRequire(path.join(resolveRoot, 'record-opening.resolver.cjs'));
const { chromium } = requireFrom('playwright');

const URL = process.env.OPENING_URL ?? 'http://localhost:5173/opening?capture';
const OUT = path.resolve(process.env.OPENING_OUT ?? 'opening-frames');
const VIDEO = path.resolve(process.env.OPENING_VIDEO ?? 'trendin-opening.mp4');
const FPS = Number(process.env.OPENING_FPS ?? 30);
const WIDTH = 1920;
const HEIGHT = 1080;

/* ffmpeg 이 PATH 에 없으면 ffmpeg-static 이 들고 있는 것을 씁니다. 둘 다 없으면 명령만 알려 줍니다. */
async function findFfmpeg() {
  if (spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' }).status === 0) return 'ffmpeg';
  try {
    return requireFrom('ffmpeg-static');
  } catch {
    return null;
  }
}

await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });

const browser = await chromium.launch({
  args: [
    // 기본 headless 에는 GPU 가 없어 WebGL 이 소프트웨어로 떨어집니다. 느려도 그림은 같지만,
    // SwiftShader 를 명시해야 파티클이 통째로 빠지는 일이 없습니다.
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
    '--hide-scrollbars',
  ],
});
const page = await browser.newPage({
  viewport: { width: WIDTH, height: HEIGHT },
  deviceScaleFactor: 1,
});

await page.goto(URL, { waitUntil: 'networkidle' });
await page.waitForFunction(() => typeof window.__opening?.seek === 'function');

const duration = await page.evaluate(() => window.__opening.duration);
const frames = Math.round(duration * FPS);
process.stdout.write(`${duration}초 · ${FPS}fps · ${frames}장\n`);

for (let index = 0; index < frames; index++) {
  const seconds = index / FPS;
  // 그리기를 마친 다음 판을 넘겨받아야 합니다. seek 뒤 한 프레임을 더 기다립니다.
  await page.evaluate((value) => {
    window.__opening.seek(value);
    return new Promise((resolve) => window.requestAnimationFrame(() => window.requestAnimationFrame(resolve)));
  }, seconds);
  await page.screenshot({
    path: path.join(OUT, `frame-${String(index).padStart(4, '0')}.png`),
    animations: 'disabled',
  });
  if (index % 30 === 0) process.stdout.write(`  ${index}/${frames}\n`);
}

await browser.close();

const written = (await readdir(OUT)).length;
process.stdout.write(`\n${written}장을 ${OUT} 에 담았습니다.\n`);

/*
 * -crf 16 은 눈으로 손실을 못 느끼는 수준입니다. 파워포인트가 그대로 물고 재생하도록
 * yuv420p 와 +faststart 를 답니다. 이 둘을 빼면 슬라이드에서 첫 프레임이 검게 뜨거나
 * 아예 재생이 안 되는 경우가 있습니다.
 */
const ffmpegArguments = [
  '-y', '-framerate', String(FPS),
  '-i', path.join(OUT, 'frame-%04d.png'),
  '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
  '-crf', '16', '-movflags', '+faststart',
  VIDEO,
];
const ffmpeg = await findFfmpeg();
if (!ffmpeg) {
  process.stdout.write(`\nffmpeg 을 찾지 못했습니다. 설치한 뒤 아래를 실행하세요.\n  ffmpeg ${ffmpegArguments.join(' ')}\n`);
} else {
  process.stdout.write('\nMP4 로 묶는 중…\n');
  const encoded = spawnSync(ffmpeg, ffmpegArguments, { stdio: ['ignore', 'ignore', 'pipe'] });
  if (encoded.status === 0) process.stdout.write(`${VIDEO}\n`);
  else process.stdout.write(`ffmpeg 실패:\n${encoded.stderr}\n`);
}
