/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0A0F",
        surface: "#0F0F16",
        card: "#1A1A24",
        border: "#22222C",
        accent: "#00E5FF",
        accent2: "#FFC75F",
        danger: "#EE5A6F",
        text: "#FFFFFF",
        muted: "#A0A0AB",
      },
    },
  },
  plugins: [],
};
