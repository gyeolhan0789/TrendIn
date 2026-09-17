import assert from 'node:assert/strict';
import test from 'node:test';
import { toCsv } from '../src/utils/download.ts';

const BOM = '﻿';

test('머리줄과 내용을 CSV 한 장으로 엮는다', () => {
  const csv = toCsv(['키워드', '분야'], [['MCP', '개발'], ['발레코어', '패션']]);
  assert.equal(csv, `${BOM}키워드,분야\r\nMCP,개발\r\n발레코어,패션\r\n`);
});

test('엑셀이 한글을 깨뜨리지 않도록 앞에 BOM을 단다', () => {
  assert.ok(toCsv(['a'], []).startsWith(BOM));
});

test('쉼표·따옴표·줄바꿈이 든 값은 따옴표로 묶는다', () => {
  const csv = toCsv(['값'], [['가,나'], ['그는 "안녕"이라 했다'], ['첫 줄\n둘째 줄']]);
  assert.equal(csv, `${BOM}값\r\n"가,나"\r\n"그는 ""안녕""이라 했다"\r\n"첫 줄\n둘째 줄"\r\n`);
});
