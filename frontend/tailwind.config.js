/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eaf4fd",
          100: "#cfe6fa",
          200: "#9fccf5",
          300: "#6fb3f0",
          400: "#3f99eb",
          500: "#0176D3", // primary — Salesforce blue
          600: "#0161ad",
          700: "#014b87",
          800: "#013661",
          900: "#01203b",
        },
        surface: "#F7F9FC",
        card: "#FFFFFF",
        ink: "#1B2631",
        muted: "#5B6B7C",
        line: "#E4E9F0",
        success: "#2E7D32",
        warning: "#B7791F",
        danger: "#C0392B",
        critical: "#8B0000",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "'Segoe UI'",
          "Roboto",
          "'Helvetica Neue'",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06)",
        cardHover: "0 4px 10px rgba(16, 24, 40, 0.08)",
        glow: "0 0 0 4px rgba(1, 118, 211, 0.12)",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
    },
  },
  plugins: [],
};
