import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' so the built dist/ works from any path, including a subfolder on static hosting.
// The example map lives one level up, outside this folder, and is read in place rather than
// copied, so the dev server is allowed to serve from the repository root.
export default defineConfig({
  base: './',
  plugins: [react()],
  // The one chunk over the default 500 kB is ELK, which loads only when Tree view is picked.
  build: { chunkSizeWarningLimit: 1500 },
  server: { fs: { allow: ['..'] } },
  test: { environment: 'node', include: ['test/**/*.test.js'] },
});
