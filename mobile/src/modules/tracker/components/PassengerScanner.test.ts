import { expect, it } from 'vitest';
import jsQR from 'jsqr';
import fixture from './passenger-qr.fixture.json';

it('decodes a real generated passenger QR with the bundled fallback, without a browser detector or network', () => {
  const scale = 5, size = fixture.matrix.length * scale;
  const pixels = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const value = fixture.matrix[Math.floor(y / scale)][Math.floor(x / scale)] === '1' ? 0 : 255;
    const offset = (y * size + x) * 4;
    pixels[offset] = pixels[offset + 1] = pixels[offset + 2] = value; pixels[offset + 3] = 255;
  }
  expect(jsQR(pixels, size, size)?.data).toBe(fixture.text);
});
