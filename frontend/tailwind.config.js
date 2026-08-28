/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "#0052cc",
          foreground: "#ffffff",
        },
        secondary: {
          DEFAULT: "#f4f5f7",
          foreground: "#172b4d",
        },
        destructive: {
          DEFAULT: "#de350b",
          foreground: "#ffffff",
        },
        muted: {
          DEFAULT: "#f4f5f7",
          foreground: "#5e6c84",
        },
        accent: {
          DEFAULT: "#ebecf0",
          foreground: "#172b4d",
        },
      },
    },
  },
  plugins: [],
}
