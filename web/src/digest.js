// A fingerprint of the whole map, computed the same way src/loader.py computes it, so the
// canvas can tell whether report.json was made from this map or from an earlier version.
//
// Canonical form: keys sorted, no whitespace, non-ASCII left as is, UTF-8 bytes, SHA-256.
// Python writes 1.0 where JavaScript writes 1, so loader.py turns integral floats into
// ints before dumping; that is the one difference between the two serialisers that a map
// can actually hit. Pure and synchronous, because buildModel runs at module load.

export function canonicalJson(v) {
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(',')}]`;
  if (v !== null && typeof v === 'object') {
    const keys = Object.keys(v).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(v[k])}`).join(',')}}`;
  }
  return JSON.stringify(v);
}

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);
const H0 = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];

const ror = (x, n) => (x >>> n) | (x << (32 - n));

// SHA-256 (FIPS 180-4). The browser's crypto.subtle is async and the model is built
// synchronously at import, so this is the plain version. Tested against node:crypto.
export function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const len = bytes.length;
  const padded = Math.ceil((len + 9) / 64) * 64;
  const buf = new Uint8Array(padded);
  buf.set(bytes);
  buf[len] = 0x80;
  const dv = new DataView(buf.buffer);
  const bits = len * 8;
  dv.setUint32(padded - 8, Math.floor(bits / 0x100000000));
  dv.setUint32(padded - 4, bits >>> 0);

  const H = new Uint32Array(H0);
  const W = new Uint32Array(64);
  for (let off = 0; off < padded; off += 64) {
    for (let i = 0; i < 16; i++) W[i] = dv.getUint32(off + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = ror(W[i - 15], 7) ^ ror(W[i - 15], 18) ^ (W[i - 15] >>> 3);
      const s1 = ror(W[i - 2], 17) ^ ror(W[i - 2], 19) ^ (W[i - 2] >>> 10);
      W[i] = W[i - 16] + s0 + W[i - 7] + s1;
    }
    let [a, b, c, d, e, f, g, h] = H;
    for (let i = 0; i < 64; i++) {
      const S1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (h + S1 + ch + K[i] + W[i]) | 0;
      const S0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) | 0;
      h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    H[0] += a; H[1] += b; H[2] += c; H[3] += d; H[4] += e; H[5] += f; H[6] += g; H[7] += h;
  }
  return [...H].map((x) => x.toString(16).padStart(8, '0')).join('');
}

export const mapDigest = (map) => sha256Hex(canonicalJson(map));
