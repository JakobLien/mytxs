let playerY = 0;
let velocityY = 0;
let velocityX = 12;
let gravity = -1.2;
let gameOver = false;
let score = 0;
let loopCount = 0;

const playerElement = document.querySelector("#player");
const scoreElement = document.getElementById("score");
const obstaclesContainer = document.querySelector("#obstacles");
const startScreen = document.getElementById("startScreen");
const gameOverScreen = document.getElementById("gameOverScreen");
const startButton = document.getElementById("startButton");
const closeButton = document.getElementById("closeButton");

startScreen.style.display = "none";
gameOverScreen.style.display = "none";
playerElement.style.display = "none";
obstaclesContainer.style.display = "none";
scoreElement.style.display = "none";

playerElement.style.bottom = playerY + "px";

document.addEventListener("keydown", (e) => {
    // Sjekker om et inputfelt, textarea eller select er aktivt
    const isTyping = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);

    if (e.key === "p" && !gameOver && !isTyping) { 
        startScreen.style.display = "flex";
    }
});

function startGame() {
    gameOver = false;
    score = 0;
    loopCount = 0;
    playerY = 0;
    velocityY = 0;
    velocityX = 12;
    obstaclesContainer.innerHTML = "";
    startScreen.style.display = "none";
    gameOverScreen.style.display = "none";
    playerElement.style.display = "block";
    obstaclesContainer.style.display = "block";
    scoreElement.style.display = "block";
    scoreElement.textContent = "00000";

    requestAnimationFrame(gameLoop);
};

function gameLoop() {
    if (gameOver) {
        gameOverScreen.style.display = "flex";
        return;
    }

    velocityY += gravity;
    playerY = Math.max(0, playerY + velocityY);
    playerElement.style.bottom = playerY + "px";

    for (const obstacle of obstaclesContainer.children) {
        obstacle.style.right = (parseInt(obstacle.style.right) + velocityX) + 'px';

        if (parseInt(obstacle.style.right) > window.innerWidth) {
            obstacle.remove();
        }

        if (detectCollision(playerElement, obstacle)) {
            gameOver = true;
            console.log("Game Over!");
        }
    }

    if (loopCount % 5 === 0) {
        score++;
        scoreElement.textContent = score.toString().padStart(5, '0');
    }

    if (loopCount % 45 === 0) {
        spawnObstacle();
    }

    if (score % 100 === 0 && score != 0) {
        velocityX += 0.15;
    }

    loopCount++;
    requestAnimationFrame(gameLoop);
};

function spawnObstacle() {
    let rand_tall = Math.random();
    let new_obstacle = document.createElement("div");
    new_obstacle.style.right = '-50px';

    if (rand_tall > 0.75) {
        new_obstacle.classList.add('absolute', 'bottom-5', 'bg-black', 'w-10', 'h-8');
    } else if (rand_tall > 0.50) {
        new_obstacle.classList.add('absolute', 'bottom-10', 'bg-black', 'w-7', 'h-8');
    } else if (rand_tall > 0.25) {
        new_obstacle.classList.add('absolute', 'bottom-0', 'bg-black', 'w-7', 'h-8');
    }

    obstaclesContainer.appendChild(new_obstacle);
};

function detectCollision(player, enemy) {
    const playerRect = player.getBoundingClientRect();
    const enemyRect = enemy.getBoundingClientRect();

    return (
        playerRect.left < enemyRect.right &&
        playerRect.right > enemyRect.left &&
        playerRect.top < enemyRect.bottom &&
        playerRect.bottom > enemyRect.top
    );
};

startButton.addEventListener("click", startGame);
gameOverScreen.addEventListener("click", startGame);
closeButton.addEventListener("click", () => {
    startScreen.style.display = "none";
    gameOverScreen.style.display = "none";
    playerElement.style.display = "none";
    obstaclesContainer.style.display = "none";
    scoreElement.style.display = "none";
});

document.addEventListener("keydown", e => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        e.preventDefault(); // Forhindrer scrolling når spillet er i gang
    }
    
    if (gameOver) return;

    if (e.key === "ArrowUp" && playerY === 0) {
        velocityY = 15;
    }

    if (e.key === "ArrowDown") {
        playerElement.style.height = "18px";
        velocityY = -0.4;
    }
});

document.addEventListener("keyup", e => {
    if (e.key === "ArrowDown") {
        playerElement.style.height = "48px";
    }
});