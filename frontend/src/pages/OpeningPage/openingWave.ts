import { MARK_LIFT, MARK_WIDTH, type MarkShape } from './openingLogo';
import type { OpeningFrame } from './openingTimeline';
import * as THREE from 'three';

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const ease = (value: number) => { const t = clamp(value); return t * t * (3 - 2 * t); };

// These values go straight to a custom shader, so preserve the authored pastel RGB values.
const shaderColor = (hex: number) => new THREE.Color().setRGB(
  (hex >> 16) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255,
);
const gradient = [0x8dbce5, 0x8fa7dc, 0xb4a0df, 0x8dc9e7, 0x8fa9dd, 0xc4b1e6].map(shaderColor);
const ivory = shaderColor(0xf7edd9);
const white = shaderColor(0xffffff);
const blueSpark = shaderColor(0x6c9ddd);
const champagneSpark = shaderColor(0xe7d4aa);
const signalGold = shaderColor(0xf0cf72);
const signalCenters = [
  { x: -1.61, z: -.28, count: 290, radiusX: .175, radiusZ: .203 },
  { x: .43, z: .31, count: 350, radiusX: .189, radiusZ: .21 },
  { x: 1.73, z: -.06, count: 205, radiusX: .133, radiusZ: .154 },
] as const;

/*
 * 무리별 입자 수입니다. 무리 한가운데의 밝은 알갱이 하나를 더해 셉니다. 로고 실루엣에서
 * 점을 이만큼 뽑아 와야 무리마다 자리가 남거나 모자라지 않습니다.
 */
export const SIGNAL_COUNTS = signalCenters.map((center) => center.count + 1) as [number, number, number];

function shorelineZ(x: number) {
  return .86 - .23 * Math.cos(x * 3.6 + .45) + .035 * Math.sin(x * 7.1);
}

function waveHeight(x: number, z: number) {
  // A top-down shoreline: broad descending sheet with scalloped foam fingers.
  return -z * 1.05 + .025 * Math.sin(x * 4.8 + z * .7)
    + .012 * Math.sin(x * 10.2 + z * 2.4);
}

function createGeometry() {
  let seed = 3010917;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  const position: number[] = [];
  const scatter: number[] = [];
  const color: number[] = [];
  const phase: number[] = [];
  const speed: number[] = [];
  const size: number[] = [];
  const opacity: number[] = [];
  const sparkle: number[] = [];
  const signal: number[] = [];
  const warm: number[] = [];
  const flash: number[] = [];
  const core: number[] = [];
  const release: number[] = [];
  const clusterId: number[] = [];

  const add = (x: number, z: number, edge: number, cluster = -1, isCore = false) => {
    const centerStrength = signalCenters.map(({ x: cx, z: cz, radiusX, radiusZ }) => {
      const dx = (x - cx) / radiusX;
      const dz = (z - cz) / radiusZ;
      return Math.exp(-(dx * dx + dz * dz) * 2.15);
    });
    const strength = Math.max(...centerStrength);
    const tier = random();
    let particleSize: number;
    let particleOpacity: number;
    let particleSparkle: number;
    if (tier < .45 && !isCore) {
      particleSize = 1.55 + random() * 1.25;
      particleOpacity = .53 + random() * .21;
      particleSparkle = .08 + random() * .17;
    } else if (tier < .78 && !isCore) {
      particleSize = 3.4 + random() * 2.1;
      particleOpacity = .71 + random() * .22;
      particleSparkle = .33 + random() * .27;
    } else if (tier < .955 && !isCore) {
      particleSize = 6 + random() * 2.8;
      particleOpacity = .8 + random() * .19;
      particleSparkle = .62 + random() * .28;
    } else {
      particleSize = isCore ? 15 + random() * 3 : 10 + random() * 3;
      particleOpacity = .9 + random() * .1;
      particleSparkle = .85 + random() * .15;
    }
    if (!isCore) {
      particleSize += strength * (cluster >= 0 ? 1.1 : .5);
      particleOpacity = Math.min(1, particleOpacity + strength * .2);
      particleSparkle = Math.min(1, particleSparkle + strength * .27);
    }
    const field = clamp((x + 2.46) / 4.92 + Math.sin(z * 1.4 + x * .6) * .045) * (gradient.length - 1);
    const from = Math.min(Math.floor(field), gradient.length - 2);
    const waveColor = gradient[from].clone().lerp(gradient[from + 1], ease(field - from));
    // Warmth belongs to the three signal clusters; the surrounding surface stays blue/lavender.
    const warmParticle = cluster >= 0;
    const highlight = isCore ? 1 : cluster >= 0
      ? (random() < .29 ? .6 + random() * .4 : 0)
      : (tier > .78 && random() < .23 ? .5 + random() * .45 : 0);
    const tint = .97 + random() * .12;
    waveColor.multiplyScalar(tint);
    const foamEdge = shorelineZ(x);
    const foamWeight = Math.exp(-Math.pow((z - foamEdge) / .075, 2));
    if (cluster < 0) {
      waveColor.lerp(blueSpark, foamWeight * .35);
      particleOpacity = Math.min(1, particleOpacity + foamWeight * .18);
    }
    if (warmParticle) waveColor.lerp(ivory, isCore ? .9 : .74 + strength * .18);
    else if (cluster >= 0 || highlight > .5) waveColor.lerp(white, cluster >= 0 ? .2 : .32);
    if (highlight > 0) waveColor.lerp(warmParticle ? champagneSpark : blueSpark, highlight * .3);
    // A golden body keeps each dense signal recognizable against the cool water.
    if (warmParticle) waveColor.lerp(signalGold, isCore ? .3 : .58 + strength * .16);
    const rgb = [waveColor.r, waveColor.g, waveColor.b];

    // Account for band widths: the broad center has one third of the margin density.
    const side = random() < .5 ? -1 : 1;
    const targetX = random() < .54
      ? (random() * 2 - 1) * .78
      : side * (.78 + random() * .22);
    const targetY = (random() * 2 - 1) * 1.03;
    position.push(x, waveHeight(x, z) + (random() - .5) * .018, z);
    scatter.push(targetX, targetY, (random() - .5) * 1.7);
    color.push(...rgb);
    phase.push(random() * Math.PI * 2);
    speed.push(cluster >= 0 ? .34 + random() * .38 : .52 + random() * .58);
    size.push(particleSize);
    opacity.push(particleOpacity);
    sparkle.push(particleSparkle);
    signal.push(strength);
    warm.push(warmParticle ? 1 : 0);
    flash.push(highlight);
    core.push(isCore ? 1 : 0);
    release.push((1 - edge) * .21 + random() * .09);
    clusterId.push(cluster);
  };

  const columns = 132;
  const rows = 24;
  for (let row = 0; row < rows; row++) {
    for (let column = 0; column < columns; column++) {
      const u = (column + random() * .88 - .44) / (columns - 1) * 2 - 1;
      const v = (row + random() * 1.1 - .55) / (rows - 1) * 2 - 1;
      if (Math.abs(v) > .84 && random() < (Math.abs(v) - .84) * 2.6) continue;
      const x = u * 2.46 + Math.sin(v * 4 + u * 2.2) * .018;
      const z = -1.42 + (v + 1) * .5 * (shorelineZ(x) + 1.42);
      // Leave airy water behind a denser, irregular leading edge of foam.
      if (v < .15 && random() < .38) continue;
      add(x, z, Math.max(Math.abs(u), Math.abs(v)));
      if (v > .5 && v < .85 && random() < .55) {
        add(x + (random() - .5) * .018, z + (random() - .5) * .024, Math.max(Math.abs(u), Math.abs(v)));
      }
    }
  }

  // A continuous fine foam rim makes the advancing shoreline readable from a distance.
  for (let column = 0; column < 250; column++) {
    const x = (column / 249 * 2 - 1) * 2.46;
    const edgeZ = shorelineZ(x);
    for (let strand = 0; strand < 3; strand++) {
      add(x + (random() - .5) * .01, edgeZ + (random() - .5) * .07, 1);
    }
  }

  // Compact centers with a sparse feathered edge read as three distinct signals.
  signalCenters.forEach(({ x: cx, z: cz, count, radiusX, radiusZ }, cluster) => {
    for (let index = 0; index < count; index++) {
      const packing = index < count * .8 ? .85 : 1.4;
      const x = cx + (random() + random() + random() - 1.5) * radiusX * packing;
      const z = cz + (random() + random() + random() - 1.5) * radiusZ * packing;
      add(x, z, .38, cluster);
    }
    add(cx, cz, .38, cluster, true);
  });

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(position, 3));
  geometry.setAttribute('aScatter', new THREE.Float32BufferAttribute(scatter, 3));
  geometry.setAttribute('aColor', new THREE.Float32BufferAttribute(color, 3));
  geometry.setAttribute('aPhase', new THREE.Float32BufferAttribute(phase, 1));
  geometry.setAttribute('aSpeed', new THREE.Float32BufferAttribute(speed, 1));
  geometry.setAttribute('aSize', new THREE.Float32BufferAttribute(size, 1));
  geometry.setAttribute('aOpacity', new THREE.Float32BufferAttribute(opacity, 1));
  geometry.setAttribute('aSparkle', new THREE.Float32BufferAttribute(sparkle, 1));
  geometry.setAttribute('aSignal', new THREE.Float32BufferAttribute(signal, 1));
  geometry.setAttribute('aWarm', new THREE.Float32BufferAttribute(warm, 1));
  geometry.setAttribute('aFlash', new THREE.Float32BufferAttribute(flash, 1));
  geometry.setAttribute('aCore', new THREE.Float32BufferAttribute(core, 1));
  geometry.setAttribute('aRelease', new THREE.Float32BufferAttribute(release, 1));
  geometry.setAttribute('aCluster', new THREE.Float32BufferAttribute(clusterId, 1));
  return geometry;
}

/*
 * 랜딩의 셰이더에서 마우스 자국(uWake*)과 드래그 회전(uRotate*)을 걷어낸 판입니다. 오프닝에는
 * 손이 닿지 않으니 정점마다 돌던 80칸 자국 반복문이 통째로 필요 없고, 1920x1080 으로 한 프레임씩
 * 받아 낼 때 그만큼 여유가 생깁니다. 물결의 모양·색·반짝임은 랜딩과 같은 식을 그대로 씁니다.
 */
/*
 * 물결 위의 한 점이 화면 어디에 놓이는지 내는 식입니다. 입자와, 신호를 잇는 선이 같은 식을
 * 써야 선 끝이 무리 한가운데에 정확히 붙습니다. 그래서 따로 베껴 쓰지 않고 이 조각을 두
 * 셰이더에 함께 붙입니다. uTime·uWaveDrop 선언도 여기 한 번만 둡니다.
 */
const waveChunk = `
  uniform float uTime;
  uniform float uWaveDrop;

  vec2 waveScreenPosition(vec3 basePoint, out vec3 surged) {
    vec3 p = basePoint;
    // Phase travels toward positive Z, which maps downward on the shoreline sheet.
    float surge = p.z * 2.6 + p.x * .45 - uTime * .65;
    float shoreWeight = smoothstep(-1.4, .65, p.z);
    p.y += shoreWeight * (.19 * sin(surge) + .045 * sin(p.z * 5.8 + p.x * 1.2 - uTime * .95));
    p.z += shoreWeight * .035 * sin(surge);
    surged = p;

    float baseTilt = -.12;
    vec3 water = vec3(p.x, p.y * cos(baseTilt) - p.z * sin(baseTilt), p.y * sin(baseTilt) + p.z * cos(baseTilt));
    float perspective = 3.1 / (3.1 - water.z * .25);
    // 물결을 조금 내려 앉혀, 화면 한가운데는 카피 몫으로 비워 둡니다.
    return vec2(water.x * .43, water.y * .66) * perspective - vec2(0.0, uWaveDrop);
  }
`;

const vertexShader = waveChunk + `
  attribute vec3 aScatter;
  attribute vec3 aColor;
  attribute float aPhase;
  attribute float aSpeed;
  attribute float aSize;
  attribute float aOpacity;
  attribute float aSparkle;
  attribute float aSignal;
  attribute float aWarm;
  attribute float aFlash;
  attribute float aCore;
  attribute float aRelease;
  attribute vec2 aLogo;
  uniform float uProgress;
  uniform float uScrollProgress;
  uniform highp float uLightScatter;
  uniform float uDpr;
  uniform float uCaptionClear;
  uniform vec2 uMarkCenter;
  uniform vec2 uMarkScale;
  uniform float uGather;
  uniform float uSignalHold;
  uniform float uSignalFade;
  varying vec3 vColor;
  varying float vAlpha;
  varying float vSparkle;
  varying float vCore;
  varying float vSignal;
  varying float vWarm;
  varying float vFlash;
  varying float vGlint;

  void main() {
    vec3 p;
    vec2 wavePosition = waveScreenPosition(position, p);
    vec2 scatteredPosition = aScatter.xy + vec2(sin(uTime * .26 + aPhase), cos(uTime * .22 + aPhase)) * .007;

    /*
     * 금색 신호 무리(aWarm)는 다른 입자처럼 흩어지지 않습니다. 화면이 밝아지는 동안 제자리에서
     * 로고 실루엣 위의 제 자리로 건너가, 마지막에 로고 그림과 정확히 겹칩니다.
     */
    float isSignal = step(.5, aWarm);
    float scatterAmount = smoothstep(aRelease, 1.0, uProgress) * (1.0 - isSignal * uSignalHold);
    vec2 driftPosition = mix(wavePosition, scatteredPosition, scatterAmount);
    vec2 logoPosition = uMarkCenter + aLogo * uMarkScale;
    vec2 samplePosition = mix(driftPosition, logoPosition, uGather * isSignal);
    gl_Position = vec4(samplePosition, .25, 1.0);

    float twinkle = .5 + .5 * sin(uTime * aSpeed + aPhase + p.x * 1.18);
    float travelingLight = .5 + .5 * sin(p.x * 3.1 - uTime * .43 + p.z * 1.5);
    float variation = (twinkle - .5) * aSparkle;
    // Narrow reflection peaks move across the water; phases keep them from flashing together.
    float reflection = pow(.5 + .5 * sin(p.x * 5.2 + p.z * 3.8 - uTime * 1.15), 8.0);
    float glint = reflection * smoothstep(.45, .9, aSparkle) * (.35 + .65 * twinkle);
    vGlint = glint * (1.0 - scatterAmount * .8);
    vColor = aColor;
    vSparkle = aSparkle;
    vCore = aCore;
    vSignal = aSignal;
    vWarm = aWarm;
    vFlash = aFlash;
    vAlpha = (aOpacity + variation * (aWarm > .5 ? .62 : .42) + travelingLight * aSparkle * .13 + aSignal * .09 + aFlash * twinkle * .27) * (1.0 - scatterAmount * .4);
    vAlpha += vGlint * .5;
    float scatterSeed = aPhase / 6.28318530718;
    float centerBand = 1.0 - smoothstep(.70, .78, abs(aScatter.x));
    float retainThreshold = mix(.9, .915 + centerBand * .055, uLightScatter);
    float retainedParticle = step(retainThreshold, scatterSeed);
    float fadeStart = .12 + scatterSeed * .22;
    float scrollFade = smoothstep(fadeStart, .85, uScrollProgress);
    float visibility = mix(1.0, retainedParticle, scrollFade);
    // 로고로 건너가는 입자는 솎아 내지 않습니다. 하나라도 빠지면 로고에 구멍이 납니다.
    visibility = mix(visibility, 1.0, isSignal * uSignalHold);
    // 로고 그림이 다 떠오른 뒤에야 조용히 빠집니다.
    visibility *= mix(1.0, uSignalFade, isSignal);
    vAlpha *= visibility;
    vGlint *= visibility;

    // 카피가 들어올수록 글자 둘레의 입자를 걷어냅니다. 상자로 덮는 대신 입자가 비켜서므로
    // 물결이 잘린 자국 없이 가운데에 여백이 생깁니다.
    float captionDistance = length((samplePosition - vec2(0.0, .02)) / vec2(.66, .26));
    float captionClearance = mix(1.0, smoothstep(.72, 1.34, captionDistance), uCaptionClear);
    vAlpha *= captionClearance;
    vGlint *= captionClearance;

    float waveSize = aSize * 1.22 * (1.0 + variation * .38 + aFlash * twinkle * .18 + vGlint * .48);
    float scatteredSize = mix(5.2 + aSparkle * 3.0, 3.9 + aSparkle * 2.1, uLightScatter);
    float driftSize = mix(waveSize, scatteredSize, smoothstep(0.0, 1.0, uScrollProgress));
    // 로고에 올라앉을수록 알갱이를 죄어야 윤곽이 뭉개지지 않습니다.
    float logoSize = 2.7 + aSparkle * 2.1;
    gl_PointSize = max(1.0, mix(driftSize, logoSize, uGather * isSignal) * uDpr);
  }
`;

/* 입자 한 알의 생김새. 랜딩과 같아야 같은 물결로 보이므로 그대로 옮겼습니다. */
const fragmentShader = `
  precision mediump float;
  uniform highp float uLightScatter;
  uniform float uLogoTint;
  varying vec3 vColor;
  varying float vAlpha;
  varying float vSparkle;
  varying float vCore;
  varying float vSignal;
  varying float vWarm;
  varying float vFlash;
  varying float vGlint;
  void main() {
    float r = length(gl_PointCoord - vec2(.5));
    if (r >= .5) discard;
    float sharp = exp(-r * r * 92.0);
    float body = exp(-r * r * 25.0);
    float halo = exp(-r * r * 12.0);
    float haloWeight = .018 + vSparkle * .075 + vWarm * vSignal * .075 + vFlash * .1 + vGlint * .3;
    float regularAlpha = (sharp * (.9 + vFlash * .28) + body * .86 + halo * haloWeight) * vAlpha;
    float coreAlpha = (sharp * 1.1 + body * .92 + halo * .25) * vAlpha;
    float edgeFade = 1.0 - smoothstep(.26, .5, r);
    vec2 point = gl_PointCoord - vec2(.5);
    float reflectionStreak = exp(-abs(point.x) * 12.0 - abs(point.y) * 85.0);
    float alpha = (mix(regularAlpha, coreAlpha, vCore) + reflectionStreak * vGlint * .7) * edgeFade;
    if (alpha < .004) discard;
    // White-hot cores blend through champagne into each particle's colored halo.
    vec3 warmLight = vec3(1.0, .96, .82);
    vec3 haloColor = mix(vColor, warmLight, .12 + vWarm * .16);
    vec3 luminousCenter = mix(vec3(1.0), vec3(1.0, .985, .92), .3 + vWarm * .55);
    float centerBlend = (1.0 - smoothstep(.0, .22, r)) * (.55 + vFlash * .3 + vGlint * .15);
    vec3 regularColor = mix(haloColor, luminousCenter, centerBlend);
    vec3 coreColor = mix(haloColor, luminousCenter, (1.0 - smoothstep(.0, .16, r)) * .7);
    vec3 particleColor = mix(regularColor, coreColor, vCore);
    particleColor = mix(particleColor, luminousCenter, clamp(reflectionStreak * vGlint, 0.0, .85));
    /*
     * 밝은 바탕에서 신호는 금색 잉크로 남습니다. 다만 로고로 모여드는 동안에는 그 금색이
     * 마크의 보랏빛으로 건너가, 색이 튀지 않고 로고 그림으로 이어집니다.
     */
    vec3 signalInk = mix(vec3(.84, .60, .08), vec3(.56, .45, .90), uLogoTint);
    vec3 scatterTint = mix(vec3(.12, .20, .36), signalInk, vWarm);
    particleColor = mix(particleColor, scatterTint, uLightScatter);
    gl_FragColor = vec4(particleColor, alpha);
  }
`;

/* 물결 뒤에 깔리는 별 밭. 랜딩의 어두운 화면이 쓰는 층을 그대로 가져왔습니다. */
const ambientVertexShader = `
  attribute float aPhase;
  attribute float aSize;
  attribute float aBelow;
  uniform float uTime;
  uniform float uDpr;
  uniform float uProgress;
  uniform float uScrollProgress;
  uniform highp float uLightScatter;
  uniform float uCaptionClear;
  varying float vAlpha;
  varying vec3 vTint;
  varying float vAmbientWarm;
  void main() {
    vec2 drift = vec2(sin(uTime * .075 + aPhase), cos(uTime * .06 + aPhase)) * .005;
    float edgeSide = position.x < 0.0 ? -1.0 : 1.0;
    float destinationX = position.z < .54
      ? (position.z / .54 * 2.0 - 1.0) * .78
      : edgeSide * (.78 + (position.z - .54) / .46 * .22);
    vec2 scatterPosition = vec2(destinationX, position.y);
    vec2 ambientPosition = mix(position.xy, scatterPosition, smoothstep(0.0, 1.0, uScrollProgress));
    gl_Position = vec4(ambientPosition + drift, .5, 1.0);
    gl_PointSize = mix(aSize, aSize * mix(1.25, 1.08, uLightScatter), smoothstep(0.0, 1.0, uScrollProgress)) * uDpr;
    vAlpha = (.34 + .08 * sin(uTime * .38 + aPhase)) * (1.0 - uProgress * .35);
    float centerBand = 1.0 - smoothstep(.70, .78, abs(destinationX));
    float keepThreshold = mix(.62, .55, centerBand);
    float lightKeep = step(keepThreshold, aPhase / 6.28318530718);
    vAlpha *= mix(1.0, lightKeep, uLightScatter);
    vTint = mix(vec3(.45, .65, .91), vec3(.65, .52, .85), position.z);
    vAmbientWarm = step(.78, position.z);
    if (aBelow > 1.5) {
      float pulse = smoothstep(.12, .9, .5 + .5 * sin(uTime * (.45 + position.z * .5) + aPhase));
      vAlpha = pulse * .9 * (1.0 - smoothstep(.05, .8, uScrollProgress));
      vTint = mix(vec3(.72, .87, 1.0), vec3(1.0, .9, .68), position.z * .6);
      gl_PointSize = aSize * (.9 + pulse * .25) * uDpr;
    } else if (aBelow > .5) {
      float pulse = smoothstep(.35, .95, .5 + .5 * sin(uTime * (.7 + position.z * .25) + aPhase));
      vAlpha = pulse * .9 * (1.0 - smoothstep(.05, .8, uScrollProgress));
      vTint = mix(vec3(.72, .87, 1.0), vec3(1.0, .9, .68), position.z * .6);
      gl_PointSize = aSize * (.9 + pulse * .2) * uDpr;
    }
    // 별 밭도 카피 둘레에서는 비켜 줍니다. 여기 큰 알갱이가 남으면 글자 위에 얼룩처럼 붙습니다.
    float captionDistance = length((ambientPosition - vec2(0.0, .02)) / vec2(.72, .30));
    vAlpha *= mix(1.0, smoothstep(.72, 1.34, captionDistance), uCaptionClear);
  }
`;

const ambientFragmentShader = `
  precision mediump float;
  uniform highp float uLightScatter;
  varying float vAlpha;
  varying vec3 vTint;
  varying float vAmbientWarm;
  void main() {
    float r = length(gl_PointCoord - vec2(.5));
    if (r >= .5) discard;
    float alpha = exp(-r * r * 20.0) * (1.0 - smoothstep(.3, .5, r)) * vAlpha;
    vec3 haloColor = mix(vTint, vec3(1.0, .96, .82), .12);
    vec3 color = mix(haloColor, vec3(1.0, .99, .95), (1.0 - smoothstep(.0, .1, r)) * .25);
    vec3 scatterTint = mix(vec3(.12, .20, .36), vec3(.84, .60, .08), vAmbientWarm);
    color = mix(color, scatterTint, uLightScatter);
    gl_FragColor = vec4(color, alpha);
  }
`;

/*
 * 신호 셋을 잇는 선입니다. 선 하나를 긋는 대신 잔 알갱이를 줄지어 세웁니다. WebGL 의 선은
 * 두께가 1픽셀에 묶여 1920 폭에서는 실처럼 얇고, 무엇보다 이 화면의 다른 것들이 모두 입자라
 * 점으로 잇는 편이 같은 말을 합니다.
 *
 * 양 끝은 무리의 한가운데(signalCenters)에 붙어 물결과 함께 출렁이고, 로고로 모이는 동안에는
 * 로고 자리까지 따라가 선이 로고 안으로 접혀 들어갑니다.
 */
const linkVertexShader = waveChunk + `
  attribute vec3 aFrom;
  attribute vec3 aTo;
  attribute vec2 aLogoFrom;
  attribute vec2 aLogoTo;
  attribute float aAlong;
  attribute float aOrder;
  attribute float aPhase;
  uniform float uDpr;
  uniform vec2 uMarkCenter;
  uniform vec2 uMarkScale;
  uniform float uGather;
  uniform float uLinkDraw;
  uniform float uLinkFade;
  varying float vAlpha;
  varying float vHead;

  void main() {
    vec3 ignored;
    vec2 head = mix(waveScreenPosition(aFrom, ignored), uMarkCenter + aLogoFrom * uMarkScale, uGather);
    vec2 tail = mix(waveScreenPosition(aTo, ignored), uMarkCenter + aLogoTo * uMarkScale, uGather);
    gl_Position = vec4(mix(head, tail, aAlong), .25, 1.0);

    // 왼쪽부터 차례로 드러납니다. aOrder 는 전체 길이에서 이 알갱이가 놓인 자리입니다.
    float revealed = 1.0 - smoothstep(uLinkDraw - .05, uLinkDraw, aOrder);
    /*
     * 그어지는 끝머리에 작은 불빛을 하나 세워, 선이 흘러가는 방향이 읽히게 합니다.
     * pow() 는 밑이 음수면 GLSL 에서 정의되지 않아(끝머리 뒤쪽이 전부 그렇습니다) NaN 이
     * 나옵니다. 제곱은 곱셈으로 직접 냅니다.
     */
    float toHead = (aOrder - uLinkDraw) / .035;
    vHead = exp(-toHead * toHead) * step(.001, uLinkDraw) * (1.0 - step(.999, uLinkDraw));
    float shimmer = .74 + .26 * sin(uTime * 1.7 + aPhase);
    vAlpha = revealed * uLinkFade * shimmer;
    /*
     * 알갱이가 너무 작으면 아래 감쇠 곡선의 봉우리를 어느 픽셀도 밟지 못해, 다 그려 놓고도
     * 거의 보이지 않습니다. 4px 은 돼야 가운데 픽셀이 제 밝기를 받습니다.
     */
    gl_PointSize = (4.6 + vHead * 7.0) * uDpr;
  }
`;

const linkFragmentShader = `
  precision mediump float;
  uniform float uLogoTint;
  varying float vAlpha;
  varying float vHead;
  void main() {
    float r = length(gl_PointCoord - vec2(.5));
    if (r >= .5) discard;
    float alpha = (exp(-r * r * 14.0) * .92 + exp(-r * r * 6.0) * (.16 + vHead * .55)) * vAlpha;
    if (alpha < .004) discard;
    /*
     * 입자와 같은 길로 금색에서 로고의 보랏빛까지 건너갑니다. 이 선이 그려지는 동안 바탕은
     * 어두운 남색에서 흰색으로 건너가므로, 양쪽 어디에 놓여도 읽히도록 색을 조금 눌렀습니다.
     */
    vec3 ink = mix(vec3(.88, .66, .18), vec3(.46, .36, .86), uLogoTint);
    vec3 color = mix(ink, vec3(1.0, .96, .86), vHead * .28);
    gl_FragColor = vec4(color, alpha);
  }
`;

function createLinkGeometry(markGroups: MarkShape['groups']) {
  /* 무리 한가운데를 물결 좌표로 잡습니다. 입자들이 실제로 둘러싸고 있는 바로 그 점입니다. */
  const centers = signalCenters.map(({ x, z }) => [x, waveHeight(x, z), z] as const);
  const logoCenters = markGroups.map((group) => {
    let sumX = 0;
    let sumY = 0;
    for (let index = 0; index < group.length; index += 2) {
      sumX += group[index];
      sumY += group[index + 1];
    }
    return [sumX / (group.length / 2), sumY / (group.length / 2)] as const;
  });

  const spans = [0, 1].map((index) => Math.hypot(
    centers[index + 1][0] - centers[index][0],
    centers[index + 1][2] - centers[index][2],
  ));
  const total = spans[0] + spans[1];

  const from: number[] = [];
  const to: number[] = [];
  const logoFrom: number[] = [];
  const logoTo: number[] = [];
  const along: number[] = [];
  const order: number[] = [];
  const phase: number[] = [];
  let seed = 5150719;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };

  // 길이에 비례해 알갱이를 나눠야 두 구간의 촘촘함이 같고, 긋는 속도도 고르게 보입니다.
  const grains = 150;
  let passed = 0;
  for (let segment = 0; segment < 2; segment++) {
    const count = Math.round(grains * (spans[segment] / total));
    for (let index = 0; index < count; index++) {
      const t = (index + .5) / count;
      from.push(...centers[segment]);
      to.push(...centers[segment + 1]);
      logoFrom.push(...logoCenters[segment]);
      logoTo.push(...logoCenters[segment + 1]);
      along.push(t);
      order.push((passed + t * spans[segment]) / total);
      phase.push(random() * Math.PI * 2);
    }
    passed += spans[segment];
  }

  const geometry = new THREE.BufferGeometry();
  // position 은 쓰지 않지만, 두면 three 가 그릴 개수를 셉니다.
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(along.length * 3), 3));
  geometry.setAttribute('aFrom', new THREE.Float32BufferAttribute(from, 3));
  geometry.setAttribute('aTo', new THREE.Float32BufferAttribute(to, 3));
  geometry.setAttribute('aLogoFrom', new THREE.Float32BufferAttribute(logoFrom, 2));
  geometry.setAttribute('aLogoTo', new THREE.Float32BufferAttribute(logoTo, 2));
  geometry.setAttribute('aAlong', new THREE.Float32BufferAttribute(along, 1));
  geometry.setAttribute('aOrder', new THREE.Float32BufferAttribute(order, 1));
  geometry.setAttribute('aPhase', new THREE.Float32BufferAttribute(phase, 1));
  return geometry;
}

function createAmbientGeometry() {
  const positions: number[] = [];
  const phases: number[] = [];
  const sizes: number[] = [];
  const below: number[] = [];
  let seed = 301;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  for (let index = 0; index < 110; index++) {
    positions.push(random() * 2 - 1, random() * 1.86 - .96, random());
    phases.push(random() * Math.PI * 2);
    const tier = random();
    sizes.push((tier < .8 ? 2.1 + random() * 1.3 : 3.8 + random() * 1.8) * .65);
    below.push(0);
  }
  // 아래쪽 반짝임 수만큼 작은 배경 입자를 화면 전체에 고르게 보탭니다.
  for (let index = 0; index < 28; index++) {
    const column = index % 7;
    const row = Math.floor(index / 7);
    positions.push((column + .18 + random() * .64) / 7 * 1.92 - .96, (row + .18 + random() * .64) / 4 * 1.84 - .94, random());
    phases.push(random() * Math.PI * 2);
    sizes.push(1.4 + random() * .8);
    below.push(0);
  }
  // 파도와 별개인 배경층. 밝은 파도 뒤에서도 보이도록 성긴 8×6 격자를 씁니다.
  for (let index = 0; index < 48; index++) {
    const column = index % 8;
    const row = Math.floor(index / 8);
    positions.push((column + .16 + random() * .68) / 8 * 1.92 - .96, (row + .16 + random() * .68) / 6 * 1.84 - .94, random());
    phases.push(random() * Math.PI * 2);
    sizes.push(7 + random() * 2.5);
    below.push(2);
  }
  // 물가 아래로 성기게 흩어지는 잔광. 가운데 카피 자리는 비켜서 놓습니다.
  for (let index = 0; index < 28; index++) {
    const x = ((index % 14) + .25 + random() * .5) / 14 * 1.92 - .96;
    const y = -.73 - Math.floor(index / 14) * .2 - random() * .06;
    if (Math.abs(x) < .34 && y > -.9) continue;
    positions.push(x, y, random());
    phases.push(random() * Math.PI * 2);
    sizes.push(6 + random() * 3);
    below.push(1);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('aPhase', new THREE.Float32BufferAttribute(phases, 1));
  geometry.setAttribute('aSize', new THREE.Float32BufferAttribute(sizes, 1));
  geometry.setAttribute('aBelow', new THREE.Float32BufferAttribute(below, 1));
  return geometry;
}

export type OpeningWave = {
  renderAt: (frame: OpeningFrame) => void;
  resize: () => void;
  dispose: () => void;
};

export function createOpeningWave(canvas: HTMLCanvasElement, markShape: MarkShape): OpeningWave {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: 'high-performance' });
  const geometry = createGeometry();

  /*
   * 신호 무리의 입자마다 로고 실루엣 위의 제 자리를 하나씩 쥐여 줍니다. 무리 번호별로 앞에서
   * 부터 차례로 나눠 주는데, 실루엣 점은 이미 섞여 있어 특정 순서가 드러나지 않습니다.
   */
  const clusterOf = geometry.getAttribute('aCluster');
  const logo = new Float32Array(clusterOf.count * 2);
  const taken = [0, 0, 0];
  for (let index = 0; index < clusterOf.count; index++) {
    const cluster = clusterOf.getX(index);
    if (cluster < 0) continue;
    const group = markShape.groups[cluster];
    const slot = (taken[cluster]++ % (group.length / 2)) * 2;
    logo[index * 2] = group[slot];
    logo[index * 2 + 1] = group[slot + 1];
  }
  geometry.setAttribute('aLogo', new THREE.BufferAttribute(logo, 2));

  /*
   * 랜딩의 어두운 화면이 쓰는 재색입니다. 다만 거기서는 원래 색을 통째로 덮어써서 파랑~라벤더
   * 띠가 사라지는데, 오프닝은 그 색 변화가 보였으면 해서 원래 그라데이션을 조금 남겨 둡니다.
   */
  const colors = geometry.getAttribute('aColor');
  const warmth = geometry.getAttribute('aWarm');
  for (let index = 0; index < colors.count; index++) {
    const isWarm = warmth.getX(index) > .5;
    const tint = isWarm ? shaderColor(0xffd6a0) : shaderColor(0xb2ddff);
    const keep = isWarm ? .2 : .62;
    colors.setXYZ(
      index,
      tint.r + (colors.getX(index) - tint.r) * keep,
      tint.g + (colors.getY(index) - tint.g) * keep,
      tint.b + (colors.getZ(index) - tint.b) * keep,
    );
  }

  const uniforms = {
    uTime: { value: 0 },
    uProgress: { value: 1 },
    uScrollProgress: { value: 0 },
    uLightScatter: { value: 0 },
    uDpr: { value: 1 },
    uWaveDrop: { value: .13 },
    uCaptionClear: { value: 0 },
    uMarkCenter: { value: new THREE.Vector2() },
    uMarkScale: { value: new THREE.Vector2() },
    uGather: { value: 0 },
    uSignalHold: { value: 0 },
    uSignalFade: { value: 1 },
    uLogoTint: { value: 0 },
    uLinkDraw: { value: 0 },
    uLinkFade: { value: 1 },
  };
  const material = new THREE.ShaderMaterial({
    uniforms, vertexShader, fragmentShader, transparent: true,
    depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const ambientGeometry = createAmbientGeometry();
  const ambientMaterial = new THREE.ShaderMaterial({
    uniforms, vertexShader: ambientVertexShader, fragmentShader: ambientFragmentShader,
    transparent: true, depthTest: false, depthWrite: false,
  });
  const scene = new THREE.Scene();
  const linkGeometry = createLinkGeometry(markShape.groups);
  /*
   * 입자와 달리 이 선은 합성을 바꾸지 않습니다. 선이 그려지는 동안 바탕이 어두운 쪽에서 흰
   * 쪽으로 건너가는데, 중간에 합성을 갈아 끼우면 그 프레임에서 선이 한 번 튑니다. 색을 덮어
   * 쓰는 합성은 어두운 바탕에서도 흰 바탕에서도 그대로 읽힙니다.
   */
  const linkMaterial = new THREE.ShaderMaterial({
    uniforms, vertexShader: linkVertexShader, fragmentShader: linkFragmentShader,
    transparent: true, depthTest: false, depthWrite: false, blending: THREE.NormalBlending,
  });
  const ambientPoints = new THREE.Points(ambientGeometry, ambientMaterial);
  ambientPoints.renderOrder = -1;
  scene.add(ambientPoints);
  scene.add(new THREE.Points(geometry, material));
  // 선은 무리 위에 얹혀야 끝이 입자에 묻히지 않습니다.
  const linkPoints = new THREE.Points(linkGeometry, linkMaterial);
  linkPoints.renderOrder = 1;
  scene.add(linkPoints);
  const camera = new THREE.Camera();

  const resize = () => {
    // 머리말이 없는 화면이라 랜딩과 달리 64px 을 빼지 않고 창을 꽉 채웁니다.
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setSize(window.innerWidth, window.innerHeight, true);
    uniforms.uDpr.value = dpr;
    /*
     * 로고 그림이 놓일 상자를 화면 좌표(-1~1)로 옮깁니다. 여기 값이 CSS 로 띄우는 <img> 와
     * 어긋나면 입자가 로고 옆에 내려앉으므로, 폭·비율·들어올림을 같은 상수에서 가져옵니다.
     */
    const boxWidth = 2 * MARK_WIDTH;
    const boxHeight = boxWidth * (window.innerWidth / window.innerHeight) / markShape.aspect;
    uniforms.uMarkScale.value.set(boxWidth, boxHeight);
    uniforms.uMarkCenter.value.set(0, MARK_LIFT * boxHeight);
  };

  const renderAt = (frame: OpeningFrame) => {
    uniforms.uTime.value = frame.time;
    uniforms.uProgress.value = Math.max(frame.scatter, frame.light);
    uniforms.uScrollProgress.value = frame.light;
    uniforms.uLightScatter.value = ease((frame.light - .2) / .6);
    uniforms.uCaptionClear.value = frame.caption;
    uniforms.uGather.value = frame.gather;
    uniforms.uSignalHold.value = frame.hold;
    uniforms.uSignalFade.value = frame.signal;
    uniforms.uLogoTint.value = frame.logoTint;
    uniforms.uLinkDraw.value = frame.link;
    uniforms.uLinkFade.value = frame.linkFade;
    /*
     * 검은 바탕에서는 빛을 더하는 합성이라야 입자가 살아나고, 흰 바탕에서는 색을 덮어써야
     * 남습니다. 랜딩이 스크롤 도중에 바꾸는 것과 같은 자리에서 바꿉니다.
     */
    material.blending = frame.light > .58 ? THREE.NormalBlending : THREE.AdditiveBlending;
    renderer.render(scene, camera);
  };

  resize();
  return {
    renderAt,
    resize,
    dispose: () => {
      geometry.dispose();
      material.dispose();
      linkGeometry.dispose();
      linkMaterial.dispose();
      ambientGeometry.dispose();
      ambientMaterial.dispose();
      renderer.dispose();
    },
  };
}
