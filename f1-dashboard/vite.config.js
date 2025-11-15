import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const ReactCompilerConfig = {
  /* ... */
};

export default defineConfig({
  plugins: [react({
    babel: {
      plugins: [
        ["babel-plugin-react-compiler", ReactCompilerConfig],
      ],
    },
  })],
  resolve: {
    alias: {
      'react/compiler-runtime': 'react-compiler-runtime'
    }
  },
  server: {
    port: 3015,
    open: true
  },
  publicDir: 'assets'
})
