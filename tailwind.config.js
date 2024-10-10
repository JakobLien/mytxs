/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ["./**/*.{html,js}"],
    theme: {
        extend: {
            colors: {
                transparent: 'transparent',
                current: 'currentColor',
                customPurple: '#aaf',
            },
        },
    },
    plugins: [
        require('@tailwindcss/forms'),
    ],
}  