/*  Kode som fikse evaluering av sjekkhefTest */

function evaluateSjekkhefTest(button){
    correctAnswerStyle = ['shadow-md', 'shadow-txsGreen500'];
    wrongAnswerStyle = ['shadow-md', 'shadow-txsRed500'];

    questions = 0;
    correct = 0;

    for(const input of document.querySelectorAll('input[type=text]:not([disabled])')){
        questions++;
        if(input.value === input.nextElementSibling.value){
            correct++;
            input.classList.remove(...wrongAnswerStyle);
            input.classList.add(...correctAnswerStyle);
        }else{
            input.classList.remove(...correctAnswerStyle);
            input.classList.add(...wrongAnswerStyle);
        }
    }

    karakterGrenser = [89, 77, 65, 53, 41, 0]

    karakter = '';
    for(let i = 0; i < karakterGrenser.length; i++){
        if(correct/questions >= karakterGrenser[i]/100){
            document.querySelector('#sjekkhefTestScore').innerText = 
                `${correct} av ${questions} riktig \nBokstavkarakter: ${String.fromCharCode(i+65)}`;
            break;
        }
    }

    document.querySelector('div[id=\'fasit\']').classList.remove('hidden')
}

function sjekkhefTestFasit() {
    for (const input of document.querySelectorAll('input[type=text][disabled]')) {
        input.classList.toggle('hidden');
    }
}
