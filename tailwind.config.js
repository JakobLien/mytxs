/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ["./**/*.{html,js,py}"],
    theme: {
        extend: {
            colors: {
                transparent: 'transparent',
                current: 'currentColor',
                customPurple: '#aaf',

                // Colors for new design
                txsWhite: '#F6F6FE',
                txsGray100: '#EDEDF3',
                txsGray200: '#DDDDE5',
                txsGray300:'#CCCCD5',
                txsGray400: '#B0B0BB',
                txsBlack: '#0F0F22',
                txsPurple200: '#8787D4',
                txsPurple300: '#6F6FAF',
                txsPurple400: '#5A5A8D',
                txsPurple500: '#34344A',
                txsGreen500: '#028140',
                txsRed500: '#E01F39',
                txsBlue500: '#1466FF',
                customGradient: 'linear-gradient(90deg, rgba(255,255,255,1) 50%, rgba(255,255,255,0) 100%)'
            },
            fontFamily: {
                // Outfit for headings
                outfit: ['Outfit', 'sans-serif'],
                // Noto Sans for body text
                noto: ['Noto Sans', 'sans-serif'],
            },
        },
    },
    plugins: [
        require('@tailwindcss/forms'),
    ],
}  