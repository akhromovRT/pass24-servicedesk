import { defineConfig } from 'unocss'

export default defineConfig({
  shortcuts: {
    'slide-heading': 'text-4xl font-bold tracking-tight',
    'slide-subheading': 'text-2xl font-light opacity-80',
    'slide-accent': 'text-[var(--color-accent)]',
    'slide-label': 'text-xs uppercase tracking-widest opacity-60',
  },
})
