import markSource from '../../assets/trendin-wave-mark.png';

/*
 * 마지막에 로고가 떠오르는 자리를 정하는 곳입니다.
 *
 * 물결 위의 금색 신호 무리 셋은 흩어지지 않고 이 좌표들로 모입니다. 그러니 마크 그림과
 * 좌표가 한 치도 어긋나면 안 됩니다. 눈대중으로 점을 찍는 대신 마크 PNG 의 알파를 직접 읽어
 * 실루엣을 뽑고, 그 안에서 점을 고릅니다. 마크 그림을 갈아 끼워도 좌표가 알아서 따라옵니다.
 *
 * 좌표는 그림 상자를 기준으로 -0.5~0.5 로 돌려줍니다(오른쪽 +x, 위 +y). 화면 비율과 무관한
 * 값이라, 창 크기가 바뀌면 셰이더 쪽 uniform 만 고쳐 주면 됩니다.
 */

/** 로고가 떠오를 때 그림 상자의 가로 길이. 화면 가로에 대한 비율입니다. */
export const MARK_WIDTH = .38;
/*
 * 마크의 실제 그림은 상자 한가운데보다 조금 아래에 있습니다(알파 기준 세로 중심이 0.535).
 * 상자를 그대로 가운데 두면 로고가 내려앉아 보여서, 그만큼 올려 둡니다.
 */
export const MARK_LIFT = .035;

/*
 * 로고가 다 선 뒤의 자리. 마크는 작아져 왼쪽으로, 그 옆에 글자가 섭니다. 아래 값들은 2.png
 * 락업에서 잰 마크:글자 = 395:500 비율을 그대로 옮긴 것으로, 화면 가로에 대한 비율입니다.
 */
export const MARK_LOCKUP_WIDTH = .174;
export const WORD_WIDTH = MARK_LOCKUP_WIDTH * .8927 * (500 / 395);
const LOCKUP_GAP = .022;
const LOCKUP_SPAN = MARK_LOCKUP_WIDTH * .8927 + LOCKUP_GAP + WORD_WIDTH;
/** 락업에서 마크 중심이 화면 한가운데에서 왼쪽으로 물러나는 거리. */
export const MARK_LOCKUP_SHIFT = -(.5 - (.5 - LOCKUP_SPAN / 2) - MARK_LOCKUP_WIDTH * .8927 / 2);
/** 락업에서 글자 중심이 화면 한가운데에서 오른쪽으로 서는 거리. */
export const WORD_SHIFT = (.5 - LOCKUP_SPAN / 2) + MARK_LOCKUP_WIDTH * .8927 + LOCKUP_GAP + WORD_WIDTH / 2 - .5;
/** 글자가 스르륵 들어올 때 오른쪽에서 밀려오는 거리. */
export const WORD_SLIDE = .026;

/** 신호 무리 셋이 각각 맡을 실루엣 점들. 0=물결 왼쪽, 1=물결 오른쪽, 2=위쪽 점. */
export type MarkGroups = [Float32Array, Float32Array, Float32Array];

export type MarkShape = {
  groups: MarkGroups;
  /** 마크 그림 상자의 가로:세로 비율. 셰이더가 점을 화면 좌표로 옮길 때 씁니다. */
  aspect: number;
};

type Point = { x: number; y: number };

/*
 * 알파가 찬 칸들을 이어 붙여 덩어리를 셉니다. 마크는 긴 물결 하나와 동그란 점 하나로
 * 떨어져 있어서, 둘을 갈라내면 "위쪽 점"에 무리 하나를 통째로 줄 수 있습니다.
 */
function findComponents(filled: Uint8Array, width: number, height: number) {
  const label = new Int32Array(filled.length).fill(-1);
  const stack = new Int32Array(filled.length);
  const components: { cells: number[]; centerY: number }[] = [];
  for (let seed = 0; seed < filled.length; seed++) {
    if (!filled[seed] || label[seed] >= 0) continue;
    const cells: number[] = [];
    let top = 0;
    stack[top++] = seed;
    label[seed] = components.length;
    let sumY = 0;
    while (top > 0) {
      const cell = stack[--top];
      cells.push(cell);
      sumY += (cell / width) | 0;
      const cx = cell % width;
      const cy = (cell / width) | 0;
      if (cx + 1 < width) { const n = cell + 1; if (filled[n] && label[n] < 0) { label[n] = components.length; stack[top++] = n; } }
      if (cx > 0) { const n = cell - 1; if (filled[n] && label[n] < 0) { label[n] = components.length; stack[top++] = n; } }
      if (cy + 1 < height) { const n = cell + width; if (filled[n] && label[n] < 0) { label[n] = components.length; stack[top++] = n; } }
      if (cy > 0) { const n = cell - width; if (filled[n] && label[n] < 0) { label[n] = components.length; stack[top++] = n; } }
    }
    components.push({ cells, centerY: sumY / cells.length });
  }
  return components.sort((a, b) => b.cells.length - a.cells.length);
}

/* 같은 순서로 섞어야 녹화를 다시 해도 같은 그림이 나옵니다. */
function shuffled(length: number, seed: number) {
  const order = new Int32Array(length);
  for (let index = 0; index < length; index++) order[index] = index;
  let state = seed;
  const random = () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
  for (let index = length - 1; index > 0; index--) {
    const pick = Math.floor(random() * (index + 1));
    const held = order[index];
    order[index] = order[pick];
    order[pick] = held;
  }
  return order;
}

function toFloats(points: Point[], counts: number, seed: number) {
  const target = new Float32Array(counts * 2);
  if (points.length === 0) return target;
  const order = shuffled(points.length, seed);
  for (let index = 0; index < counts; index++) {
    const point = points[order[index % points.length]];
    target[index * 2] = point.x;
    target[index * 2 + 1] = point.y;
  }
  return target;
}

/**
 * 마크 그림에서 실루엣을 뽑아, 신호 무리 셋이 각각 맡을 점들을 돌려줍니다.
 * `counts` 는 무리별 입자 수입니다.
 */
export async function loadMarkShape(counts: [number, number, number]): Promise<MarkShape> {
  const image = new Image();
  image.src = markSource;
  await image.decode();

  const canvas = document.createElement('canvas');
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('마크 실루엣을 읽을 2d 판을 얻지 못했습니다.');
  context.drawImage(image, 0, 0);
  const { data } = context.getImageData(0, 0, canvas.width, canvas.height);

  /*
   * 3픽셀마다 한 칸으로 줄여 봅니다. 알파 120 아래는 그림 둘레의 옅은 빛이라 실루엣에서
   * 뺍니다. 그 빛까지 넣으면 입자가 모양 밖으로 번져 로고 윤곽이 흐려집니다.
   */
  const step = 3;
  const gridWidth = Math.ceil(canvas.width / step);
  const gridHeight = Math.ceil(canvas.height / step);
  const filled = new Uint8Array(gridWidth * gridHeight);
  for (let gy = 0; gy < gridHeight; gy++) {
    for (let gx = 0; gx < gridWidth; gx++) {
      const alpha = data[((gy * step) * canvas.width + gx * step) * 4 + 3];
      filled[gy * gridWidth + gx] = alpha >= 120 ? 1 : 0;
    }
  }

  const components = findComponents(filled, gridWidth, gridHeight);
  if (components.length < 2) throw new Error('마크에서 물결과 점을 갈라내지 못했습니다.');
  // 큰 쪽이 물결, 그다음이 위에 떠 있는 점입니다.
  const [wave, dot] = components;

  const toPoint = (cell: number): Point => ({
    x: ((cell % gridWidth) * step) / canvas.width - .5,
    y: .5 - (((cell / gridWidth) | 0) * step) / canvas.height,
  });

  /*
   * 물결은 가로로 길어서 한 무리가 다 맡으면 한쪽에서만 몰려옵니다. 왼쪽·오른쪽으로 갈라
   * 화면 왼쪽 무리는 물결 왼쪽으로, 가운데 무리는 물결 오른쪽으로 가게 합니다. 가르는 자리는
   * 두 무리의 입자 수 비율에 맞춰, 입자 밀도가 양쪽에서 같아지도록 정합니다.
   */
  const wavePoints = wave.cells.map(toPoint).sort((a, b) => a.x - b.x);
  const splitAt = Math.round(wavePoints.length * (counts[0] / (counts[0] + counts[1])));
  const dotPoints = dot.cells.map(toPoint);

  return {
    groups: [
      toFloats(wavePoints.slice(0, splitAt), counts[0], 20260925),
      toFloats(wavePoints.slice(splitAt), counts[1], 71535561),
      toFloats(dotPoints, counts[2], 99180043),
    ],
    aspect: canvas.width / canvas.height,
  };
}
