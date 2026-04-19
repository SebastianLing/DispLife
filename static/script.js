const pathToClothes = "../static/icons/clothes/";
const pathToWeatherIcons = "../static/icons/weather_icons/";
const fileSuffix = ".png";
let fullClothesPath;
const imageIdPrefix = "zone-";
const mainBg = document.getElementById('main-bg');
const weatherIcon = document.getElementById('weather-icon');
const temperature = document.getElementById('temperature');

function updateClock() {
    const now = new Date();
    
    // Format Time (e.g., 14:30 or 08:05)
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    document.getElementById('clock').textContent = `${hours}:${minutes}`;

    // Format Date (e.g., Tue, Apr 14)
    const options = { weekday: 'long', month: 'long', day: 'numeric' };
    document.getElementById('date').textContent = now.toLocaleDateString('sv-SE', options);
}

function updateWeather(data) {
    mainBg.setAttribute('data-weather', data.condition);
    temperature.innerText = data.temperature;
    weatherIcon.setAttribute('src', pathToWeatherIcons + data.condition + fileSuffix);
}

let currentBodyPart;
function updateClothes(data){
    Object.keys(data.clothes).forEach(bodyPart => {
        console.log(bodyPart)
        const item = data.clothes[bodyPart];
        if(item && item !== "none"){
            fullClothesPath = pathToClothes + bodyPart + '/' + item + fileSuffix;
        }
        else{
            fullClothesPath = '';
        }
        currentBodyPart = document.getElementById(imageIdPrefix + bodyPart);
        if(currentBodyPart.children.length == 0){
            currentBodyPart.setAttribute('src', fullClothesPath);
        }
        else{
            for(let bodyPartIndex = 0; bodyPartIndex < currentBodyPart.children.length; bodyPartIndex++){
                currentBodyPart.children[bodyPartIndex].setAttribute('src', fullClothesPath);
            }
        }
    });
}

async function fetchData(){
    try {
        const response = await fetch('/api/get-clothes');

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const data = await response.json();

        updateWeather(data);
        updateClothes(data);

    }catch (error) {
        console.error("Failed to fetch data from Flask:", error);
    }
}

fetchData();
updateClock()
setInterval(updateClock, 1000);