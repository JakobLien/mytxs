/*  Kode som fikse evaluering av sjekkhefTest */

function evaluateSjekkhefTest(button){
    correctAnswerStyle = ['shadow-lg', 'shadow-green-600'];
    wrongAnswerStyle = ['shadow-lg', 'shadow-red-500'];

    questions = 0;
    correct = 0;

    for(const input of button.parentElement.querySelectorAll('input[type=text]:not([disabled])')){
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
                `${correct}/${questions}, bokstavkarakter: ${String.fromCharCode(i+65)}`;
            break;
        }
    }

    document.querySelector('input[type=button][value=\'Vis fasit\']').classList.remove('hidden')
}

function sjekkhefTestFasit(button){
    for(const input of button.parentElement.querySelectorAll('input[type=text][disabled]')){
        input.classList.toggle('hidden');
    }
        
    if(button.value === 'Vis fasit'){
        button.value = 'Skjul fasit';
    }else{
        button.value = 'Vis fasit';
    }
}