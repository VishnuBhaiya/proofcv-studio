import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], define: {'process.env.NODE_ENV': JSON.stringify('production')}, build: { outDir: 'portfolio-runtime', emptyOutDir: true,
  lib: { entry: 'src/portfolio/public-entry.tsx', name: 'ProofCVPortfolio', formats: ['iife'], fileName: () => 'portfolio.js', cssFileName: 'portfolio' } } });
