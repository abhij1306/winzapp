/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17211f',
        mist: '#eef3f1',
        line: '#d9e2df',
        teal: '#127c72',
      },
    },
  },
  plugins: [],
};
