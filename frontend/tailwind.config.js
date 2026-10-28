/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070b10",
        panel: "#0c141b",
        phosphor: "#1dff9a",
        signal: "#ff3355",
        radar: "#3ee0ff",
      },
      fontFamily: {
        mono: ["Cascadia Mono", "Consolas", "ui-monospace", "monospace"],
        sans: ["Segoe UI", "Helvetica Neue", "sans-serif"],
      },
    },
  },
  plugins: [],
};
