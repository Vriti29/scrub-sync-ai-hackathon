/** @type {import('tailwindcss').Config} */
export default {
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
      extend: {
        fontFamily: {
          sans: ["Inter", "system-ui", "sans-serif"],
          mono: ["ui-monospace", "SFMono-Regular", "Consolas", "monospace"]
        }
      }
    },
    plugins: []
  };