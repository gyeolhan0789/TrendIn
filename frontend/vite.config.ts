import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Three.js의 core와 WebGL 렌더러를 나눠 랜딩 청크가 한 파일로 뭉치지 않게 합니다.
          if (id.includes('/node_modules/three/build/three.core.js')) return 'three-core';
        },
      },
    },
  },
});

