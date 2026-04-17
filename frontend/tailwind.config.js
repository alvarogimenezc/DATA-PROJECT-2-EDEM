/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './src/pages/UrbanPacer.jsx',
    './src/styles/urban-pacer.css',
  ],
  important: '.up-root',
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      fontFamily: {
        // Display: 'Archivo Black' — stand-in open-source de la Futura Bold
        // Condensed histórica de Nike. Sólo viene en peso 900 por diseño.
        display: ['"Archivo Black"', '"Inter"', 'system-ui', 'sans-serif'],
        // Body: Inter 400-900 — equivalente open-source a Helvetica Neue.
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
      letterSpacing: {
        // Nike-style: titulares muy apretados, CTAs muy abiertos.
        'nike-tight': '-0.025em',
        'nike-wide':  '0.18em',
      },
      colors: {
        // Paleta 'Athletic Pro' — saturada pero NO neon.
        // Inspirada en kits de marcas deportivas (Nike Running, On,
        // Hoka). Todavía vibrante para identidad de facción pero
        // luce como equipación de verdad, no como luces de club.
        //
        // Los nombres Tailwind quedan (text-neon-pink, etc.) por
        // compatibilidad con el código que los usa, pero los hex
        // ya no son 'neon'. Se podrán renombrar a 'brand.*' cuando
        // queramos un segundo pase de limpieza.
        neon: {
          pink:   '#f43f5e',  // Norte   — rose 500 (red bib)
          cyan:   '#06b6d4',  // Este    — teal 500 (performance blue)
          lime:   '#c8ff00',  // Sur / Volt Nike — verde 'que se ve blanco' sobre negro
          violet: '#a855f7',  // Oeste   — violet 500 (sin cambio)
        },
        ink: {
          900: '#0a0a0a',  // near-black puro (antes #06070d navy)
          800: '#121212',
          700: '#1a1a1a',
          600: '#262626',
        },
      },
      boxShadow: {
        glow: '0 0 28px rgba(244,63,94,0.5)',
        'glow-cyan': '0 0 28px rgba(6,182,212,0.5)',
        'glow-lime': '0 0 28px rgba(200,255,0,0.5)',
      },
    },
  },
  plugins: [],
}
