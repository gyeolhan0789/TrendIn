import { useEffect, useRef } from 'react';
import * as THREE from 'three';

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const ease = (value: number) => { const t = clamp(value); return t * t * (3 - 2 * t); };
const shortestAngle = (from: number, to: number) => Math.atan2(Math.sin(to - from), Math.cos(to - from));
const wakeCount = 80;

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
  return geometry;
}

const vertexShader = `
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
  uniform float uTime;
  uniform float uProgress;
  uniform float uScrollProgress;
  uniform highp float uLightScatter;
  uniform float uRotateX;
  uniform float uRotateY;
  uniform float uDpr;
  uniform float uAspect;
  uniform vec2 uWakePosition[80];
  uniform vec2 uWakeStart[80];
  uniform vec2 uWakeDirection[80];
  uniform float uWakeAge[80];
  varying vec3 vColor;
  varying float vAlpha;
  varying float vSparkle;
  varying float vCore;
  varying float vSignal;
  varying float vWarm;
  varying float vFlash;
  varying float vGlint;

  void main() {
    vec3 p = position;
    // Phase travels toward positive Z, which maps downward on the shoreline sheet.
    float surge = p.z * 2.6 + p.x * .45 - uTime * .65;
    float shoreWeight = smoothstep(-1.4, .65, p.z);
    p.y += shoreWeight * (.19 * sin(surge) + .045 * sin(p.z * 5.8 + p.x * 1.2 - uTime * .95));
    p.z += shoreWeight * .035 * sin(surge);

    // The water's resting angle is separate from the user's drag rotation.
    float baseTilt = -.12;
    vec3 water = vec3(p.x, p.y * cos(baseTilt) - p.z * sin(baseTilt), p.y * sin(baseTilt) + p.z * cos(baseTilt));
    float cy = cos(uRotateY), sy = sin(uRotateY);
    float cx = cos(uRotateX), sx = sin(uRotateX);
    vec3 rotated = vec3(water.x * cy + water.z * sy, water.y, -water.x * sy + water.z * cy);
    rotated = vec3(rotated.x, rotated.y * cx - rotated.z * sx, rotated.y * sx + rotated.z * cx);
    float perspective = 3.1 / (3.1 - rotated.z * .25);
    vec2 wavePosition = vec2(rotated.x * .43, rotated.y * .66) * perspective;
    vec2 scatteredPosition = aScatter.xy + vec2(sin(uTime * .26 + aPhase), cos(uTime * .22 + aPhase)) * .007;
    float scatterAmount = smoothstep(aRelease, 1.0, uProgress);
    vec2 samplePosition = mix(wavePosition, scatteredPosition, scatterAmount);

    // Cursor wakes bloom slowly, travel through the surface, and fade after the cursor passes.
    vec3 wakeShift = vec3(0.0);
    for (int i = 0; i < 80; i++) {
      vec2 aspect = vec2(uAspect, 1.0);
      vec2 segment = (uWakePosition[i] - uWakeStart[i]) * aspect;
      vec2 fromStart = (samplePosition - uWakeStart[i]) * aspect;
      float along = clamp(dot(fromStart, segment) / max(dot(segment, segment), .000001), 0.0, 1.0);
      vec2 difference = fromStart - segment * along;
      // Blend the former broad falloff with the compact brush stroke.
      float distanceToWake = length(difference);
      float compactInfluence = 1.0 - smoothstep(.022, .065, distanceToWake);
      float broadInfluence = exp(-dot(difference, difference) / (.095 * .095));
      float influence = mix(compactInfluence, broadInfluence, .5);
      float age = uWakeAge[i];
      float envelope = (1.0 - exp(-age * 6.0)) * exp(-age * .58) * (1.0 - smoothstep(3.0, 3.9, age));
      vec2 direction = uWakeDirection[i];
      float force = influence * envelope * length(direction);
      vec2 outward = difference * inversesqrt(dot(difference, difference) + .0025);
      wakeShift.xy += (outward * .045 + direction * .23) * force * .65;
      wakeShift.z += sin(p.x * 4.3 + p.z * 5.1 - uTime * .25) * .18 * force * .65;
    }
    // A smooth vector limit prevents overlapping wakes from opening a large gap.
    wakeShift *= .32 / sqrt(.32 * .32 + dot(wakeShift, wakeShift));
    rotated += wakeShift * (1.0 - scatterAmount);
    perspective = 3.1 / (3.1 - rotated.z * .25);
    wavePosition = vec2(rotated.x * .43, rotated.y * .66) * perspective;
    scatteredPosition += wakeShift.xy * vec2(.43, .66) * .65;
    gl_Position = vec4(mix(wavePosition, scatteredPosition, scatterAmount), .25, 1.0);

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
    // Stable per-particle selection: scrolling removes density, scrolling back restores it.
    float scatterSeed = aPhase / 6.28318530718;
    float centerBand = 1.0 - smoothstep(.70, .78, abs(aScatter.x));
    float retainThreshold = mix(.9, .915 + centerBand * .055, uLightScatter);
    float retainedParticle = step(retainThreshold, scatterSeed);
    float fadeStart = .12 + scatterSeed * .22;
    float scrollFade = smoothstep(fadeStart, .85, uScrollProgress);
    float visibility = mix(1.0, retainedParticle, scrollFade);
    vAlpha *= visibility;
    vGlint *= visibility;
    float waveSize = aSize * 1.22 * (1.0 + variation * .38 + aFlash * twinkle * .18 + vGlint * .48 + wakeShift.z * .5);
    float scatteredSize = mix(5.2 + aSparkle * 3.0, 3.9 + aSparkle * 2.1, uLightScatter);
    gl_PointSize = max(1.0, mix(waveSize, scatteredSize, smoothstep(0.0, 1.0, uScrollProgress)) * uDpr);
  }
`;

const fragmentShader = `
  precision mediump float;
  uniform highp float uLightScatter;
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
    vec3 scatterTint = mix(vec3(.12, .20, .36), vec3(.84, .60, .08), vWarm);
    particleColor = mix(particleColor, scatterTint, uLightScatter);
    gl_FragColor = vec4(particleColor, alpha);
  }
`;

export function ParticleWave({
  variant = 'light',
  playEntryAnimation = true,
  onEntryComplete,
}: {
  variant?: 'light' | 'dark' | 'transition';
  playEntryAnimation?: boolean;
  onEntryComplete?: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hitRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const hit = hitRef.current;
    const hero = hit?.closest('.hero');
    if (!canvas || !hit || !hero) return;

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: 'high-performance' });
    const geometry = createGeometry();
    const dark = variant !== 'light';
    if (dark) {
      const colors = geometry.getAttribute('aColor');
      const warmth = geometry.getAttribute('aWarm');
      for (let index = 0; index < colors.count; index++) {
        const tint = warmth.getX(index) > .5 ? shaderColor(0xffd6a0) : shaderColor(0xb2ddff);
        colors.setXYZ(index, tint.r, tint.g, tint.b);
      }
    }
    const wakePositions = Array.from({ length: wakeCount }, () => new THREE.Vector2(3, 3));
    const wakeStarts = Array.from({ length: wakeCount }, () => new THREE.Vector2(3, 3));
    const wakeDirections = Array.from({ length: wakeCount }, () => new THREE.Vector2());
    const wakeAges = Array<number>(wakeCount).fill(10);
    const uniforms = {
      uTime: { value: 0 },
      uProgress: { value: 1 },
      uScrollProgress: { value: 0 },
      uLightScatter: { value: 0 },
      uRotateX: { value: 0 },
      uRotateY: { value: 0 },
      uDpr: { value: 1 },
      uAspect: { value: 1 },
      uWakePosition: { value: wakePositions },
      uWakeStart: { value: wakeStarts },
      uWakeDirection: { value: wakeDirections },
      uWakeAge: { value: wakeAges },
    };
    const material = new THREE.ShaderMaterial({
      uniforms, vertexShader, fragmentShader, transparent: true,
      depthTest: false, depthWrite: false, blending: dark ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
    const scene = new THREE.Scene();
    // Sparse ambient particles stay behind the interactive water, including during drag.
    const ambientGeometry = new THREE.BufferGeometry();
    const ambientPositions: number[] = [];
    const ambientPhases: number[] = [];
    const ambientSizes: number[] = [];
    const ambientBelow: number[] = [];
    let ambientSeed = 301;
    const ambientRandom = () => { ambientSeed = (Math.imul(ambientSeed, 1664525) + 1013904223) >>> 0; return ambientSeed / 4294967296; };
    for (let index = 0; index < (dark ? 110 : 190); index++) {
      ambientPositions.push(ambientRandom() * 2 - 1, ambientRandom() * 1.86 - .96, ambientRandom());
      ambientPhases.push(ambientRandom() * Math.PI * 2);
      const tier = ambientRandom();
      ambientSizes.push((tier < .8 ? 2.1 + ambientRandom() * 1.3 : 3.8 + ambientRandom() * 1.8) * (dark ? .65 : 1));
      ambientBelow.push(0);
    }
    if (dark) {
      // 아래쪽 반짝임 수만큼 작은 배경 입자를 화면 전체에 고르게 보탭니다.
      for (let index = 0; index < 28; index++) {
        const column = index % 7;
        const row = Math.floor(index / 7);
        const x = (column + .18 + ambientRandom() * .64) / 7 * 1.92 - .96;
        const y = (row + .18 + ambientRandom() * .64) / 4 * 1.84 - .94;
        ambientPositions.push(x, y, ambientRandom());
        ambientPhases.push(ambientRandom() * Math.PI * 2);
        ambientSizes.push(1.4 + ambientRandom() * .8);
        ambientBelow.push(0);
      }
      // 파도와 별개인 배경층에 배치합니다. 밝은 파도 뒤에서도 보이도록 성긴 8×6 격자를 씁니다.
      for (let index = 0; index < 48; index++) {
        const column = index % 8;
        const row = Math.floor(index / 8);
        ambientPositions.push(
          (column + .16 + ambientRandom() * .68) / 8 * 1.92 - .96,
          (row + .16 + ambientRandom() * .68) / 6 * 1.84 - .94,
          ambientRandom(),
        );
        ambientPhases.push(ambientRandom() * Math.PI * 2);
        ambientSizes.push(7 + ambientRandom() * 2.5);
        ambientBelow.push(2);
      }
      // Loose, spaced glimmers underneath the shoreline, away from the central caption.
      for (let index = 0; index < 28; index++) {
        const x = ((index % 14) + .25 + ambientRandom() * .5) / 14 * 1.92 - .96;
        const y = -.73 - Math.floor(index / 14) * .2 - ambientRandom() * .06;
        if (Math.abs(x) < .34 && y > -.9) continue;
        ambientPositions.push(x, y, ambientRandom());
        ambientPhases.push(ambientRandom() * Math.PI * 2);
        ambientSizes.push(6 + ambientRandom() * 3);
        ambientBelow.push(1);
      }
    }
    ambientGeometry.setAttribute('position', new THREE.Float32BufferAttribute(ambientPositions, 3));
    ambientGeometry.setAttribute('aPhase', new THREE.Float32BufferAttribute(ambientPhases, 1));
    ambientGeometry.setAttribute('aSize', new THREE.Float32BufferAttribute(ambientSizes, 1));
    ambientGeometry.setAttribute('aBelow', new THREE.Float32BufferAttribute(ambientBelow, 1));
    const ambientMaterial = new THREE.ShaderMaterial({
      uniforms, transparent: true, depthTest: false, depthWrite: false,
      vertexShader: `
        attribute float aPhase;
        attribute float aSize;
        attribute float aBelow;
        uniform float uTime;
        uniform float uDpr;
        uniform float uProgress;
        uniform float uScrollProgress;
        uniform highp float uLightScatter;
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
        }
      `,
      fragmentShader: `
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
      `,
    });
    const ambientPoints = new THREE.Points(ambientGeometry, ambientMaterial);
    ambientPoints.renderOrder = -1;
    scene.add(ambientPoints);
    scene.add(new THREE.Points(geometry, material));
    const camera = new THREE.Camera();
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const state = {
      dragging: false, pointerId: -1, lastX: 0, lastY: 0, hasPointer: false,
      wakeDX: 0, wakeDY: 0, lastWakeTime: 0, nextWake: 0,
      rotationVelocityX: 0, rotationVelocityY: 0,
      lastTime: 0, startTime: 0, entryComplete: !playEntryAnimation || reducedMotion.matches,
    };
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      renderer.setPixelRatio(dpr);
      renderer.setSize(window.innerWidth, window.innerHeight - 64, true);
      uniforms.uDpr.value = dpr;
      uniforms.uAspect.value = window.innerWidth / (window.innerHeight - 64);
    };
    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;
      state.dragging = true;
      state.pointerId = event.pointerId;
      state.lastX = event.clientX;
      state.lastY = event.clientY;
      state.rotationVelocityX = 0;
      state.rotationVelocityY = 0;
      state.wakeDX = 0;
      state.wakeDY = 0;
      hit.setPointerCapture(event.pointerId);
      hit.classList.add('is-dragging');
      event.preventDefault();
    };
    const onPointerMove = (event: PointerEvent) => {
      const dx = state.hasPointer ? event.clientX - state.lastX : 0;
      const dy = state.hasPointer ? event.clientY - state.lastY : 0;
      state.hasPointer = true;
      state.lastX = event.clientX;
      state.lastY = event.clientY;
      if (state.dragging && event.pointerId === state.pointerId) {
        uniforms.uRotateY.value += dx * .008;
        uniforms.uRotateX.value += dy * .008;
        state.rotationVelocityY = dx * .025;
        state.rotationVelocityX = dy * .025;
      } else if (!state.dragging) {
        state.wakeDX += dx;
        state.wakeDY += dy;
        const distance = Math.hypot(state.wakeDX, state.wakeDY);
        if (distance >= 2 && event.timeStamp - state.lastWakeTime >= 50) {
          const strength = clamp(distance / 50, .06, .8);
          const slot = state.nextWake;
          wakeStarts[slot].set((event.clientX - state.wakeDX) / window.innerWidth * 2 - 1, 1 - (event.clientY - state.wakeDY - 64) / (window.innerHeight - 64) * 2);
          wakePositions[slot].set(event.clientX / window.innerWidth * 2 - 1, 1 - (event.clientY - 64) / (window.innerHeight - 64) * 2);
          wakeDirections[slot].set(state.wakeDX / distance * strength, -state.wakeDY / distance * strength);
          wakeAges[slot] = 0;
          state.nextWake = (slot + 1) % wakeCount;
          state.lastWakeTime = event.timeStamp;
          state.wakeDX = 0;
          state.wakeDY = 0;
        }
      }
    };
    const onPointerUp = (event: PointerEvent) => {
      if (event.pointerId !== state.pointerId) return;
      state.dragging = false;
      state.pointerId = -1;
      hit.classList.remove('is-dragging');
      if (hit.hasPointerCapture(event.pointerId)) hit.releasePointerCapture(event.pointerId);
    };
    const onPointerLeave = () => { state.hasPointer = false; state.wakeDX = 0; state.wakeDY = 0; };

    const draw = (time: number) => {
      const seconds = Math.min((time - (state.lastTime || time)) / 1000, .05);
      state.lastTime = time;
      if (!state.startTime) state.startTime = time;
      const elapsed = (time - state.startTime) / 1000;
      const heroRect = hero.getBoundingClientRect();
      const scrollProgress = clamp((-heroRect.top + 64) / Math.max(heroRect.height, window.innerHeight * .65));
      const entryProgress = !playEntryAnimation || reducedMotion.matches ? 0 : 1 - ease(elapsed / 3.2);
      uniforms.uScrollProgress.value = scrollProgress;
      uniforms.uLightScatter.value = variant === 'transition' ? ease(clamp((scrollProgress - .2) / .6)) : 0;
      // Additive light is visible on black; normal blending preserves dark pigment on white.
      material.blending = dark && !(variant === 'transition' && scrollProgress > .65)
        ? THREE.AdditiveBlending : THREE.NormalBlending;
      uniforms.uProgress.value = Math.max(scrollProgress, entryProgress);
      uniforms.uTime.value = reducedMotion.matches ? 0 : elapsed;

      for (let index = 0; index < wakeCount; index++) wakeAges[index] = Math.min(10, wakeAges[index] + seconds);

      if (!state.dragging) {
        const spring = 6.2;
        const damping = Math.exp(-3.4 * seconds);
        state.rotationVelocityX = (state.rotationVelocityX + shortestAngle(uniforms.uRotateX.value, 0) * spring * seconds) * damping;
        state.rotationVelocityY = (state.rotationVelocityY + shortestAngle(uniforms.uRotateY.value, 0) * spring * seconds) * damping;
        uniforms.uRotateX.value += state.rotationVelocityX * seconds;
        uniforms.uRotateY.value += state.rotationVelocityY * seconds;
        if (Math.abs(shortestAngle(uniforms.uRotateX.value, 0)) < .0004 && Math.abs(state.rotationVelocityX) < .0004) {
          uniforms.uRotateX.value = 0;
          state.rotationVelocityX = 0;
        }
        if (Math.abs(shortestAngle(uniforms.uRotateY.value, 0)) < .0004 && Math.abs(state.rotationVelocityY) < .0004) {
          uniforms.uRotateY.value = 0;
          state.rotationVelocityY = 0;
        }
      }
      renderer.render(scene, camera);
      if (!state.entryComplete && entryProgress === 0) {
        state.entryComplete = true;
        onEntryComplete?.();
      }
    };

    resize();
    if (!playEntryAnimation || reducedMotion.matches) onEntryComplete?.();
    renderer.setAnimationLoop(draw);
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerleave', onPointerLeave);
    hit.addEventListener('pointerdown', onPointerDown);
    hit.addEventListener('pointerup', onPointerUp);
    hit.addEventListener('pointercancel', onPointerUp);
    return () => {
      renderer.setAnimationLoop(null);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerleave', onPointerLeave);
      hit.removeEventListener('pointerdown', onPointerDown);
      hit.removeEventListener('pointerup', onPointerUp);
      hit.removeEventListener('pointercancel', onPointerUp);
      geometry.dispose();
      material.dispose();
      ambientGeometry.dispose();
      ambientMaterial.dispose();
      renderer.dispose();
    };
  }, [variant, playEntryAnimation, onEntryComplete]);

  return <>
    <canvas ref={canvasRef} className="particle-canvas" aria-hidden="true" />
    <div ref={hitRef} className="wave-hit-area" role="img" aria-label="마우스로 흐름을 바꾸고 왼쪽 드래그로 회전할 수 있는 파티클 물결" />
  </>;
}
