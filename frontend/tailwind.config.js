/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Mapped to the EquiMed design-system CSS variables (light/dark aware).
        bg: "var(--color-bg)",
        surface: "var(--color-surface)",
        ink: "var(--color-text)",
        accent: "var(--color-accent)",
        "accent-600": "var(--color-accent-600)",
        divider: "var(--color-divider)",
        ok: "var(--ok)",
        warn: "var(--warn)",
        err: "var(--err)",
      },
      fontFamily: {
        heading: ["var(--font-heading)"],
        body: ["var(--font-body)"],
      },
      borderRadius: {
        card: "12px",
      },
      maxWidth: {
        content: "1600px",
      },
    },
  },
  plugins: [],
};
