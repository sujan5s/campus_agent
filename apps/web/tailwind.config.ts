import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          50: "#f0f4ff",
          100: "#e1e9ff",
          200: "#c7d7ff",
          300: "#9eb9ff",
          400: "#6b8fff",
          500: "#3b5cfa",
          600: "#253df0",
          700: "#1b2ad9",
          800: "#1a24b0",
          900: "#1b248c",
          950: "#111456",
        },
        slate: {
          950: "#0b0f19",
        },
        indigo: {
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
        },
        emerald: {
          500: "#10b981",
        },
        amber: {
          500: "#f59e0b",
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "glass-gradient": "linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.01) 100%)",
      },
      boxShadow: {
        "glass-inset": "inset 0 1px 1px 0 rgba(255, 255, 255, 0.1)",
        "glass-card": "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
      },
      animation: {
        "pulse-subtle": "pulse-subtle 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        "pulse-subtle": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: ".8" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
