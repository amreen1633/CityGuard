let trafficLevel = 1;

let emergencyMode = false;


const trafficText =
    document.getElementById("trafficLevel");

const vehicleText =
    document.getElementById("vehicleCount");

const signalText =
    document.getElementById("signalStatus");

const message =
    document.getElementById("message");


const redLight =
    document.getElementById("redLight");

const yellowLight =
    document.getElementById("yellowLight");

const greenLight =
    document.getElementById("greenLight");


const increaseButton =
    document.getElementById("increaseBtn");

const decreaseButton =
    document.getElementById("decreaseBtn");

const emergencyButton =
    document.getElementById("emergencyBtn");


function updateTraffic() {

    if (emergencyMode) {

        trafficText.textContent =
            "EMERGENCY";

        vehicleText.textContent =
            "CLEAR ROUTE";

        signalText.textContent =
            "GREEN";

        setSignal("green");

        message.textContent =
            "🚑 Emergency route cleared — traffic signal turned GREEN.";

        return;
    }


    if (trafficLevel === 1) {

        trafficText.textContent =
            "LOW";

        vehicleText.textContent =
            "3";

        signalText.textContent =
            "GREEN";

        setSignal("green");

        message.textContent =
            "Normal traffic operation.";

    }


    else if (trafficLevel === 2) {

        trafficText.textContent =
            "MEDIUM";

        vehicleText.textContent =
            "6";

        signalText.textContent =
            "YELLOW";

        setSignal("yellow");

        message.textContent =
            "Traffic increasing — signal timing adapting.";

    }


    else {

        trafficText.textContent =
            "HIGH";

        vehicleText.textContent =
            "10+";

        signalText.textContent =
            "RED";

        setSignal("red");

        message.textContent =
            "⚠️ Heavy traffic detected — signal timing adjusted.";

    }

}


function setSignal(color) {

    redLight.classList.remove("active");

    yellowLight.classList.remove("active");

    greenLight.classList.remove("active");


    if (color === "red") {

        redLight.classList.add("active");

    }


    if (color === "yellow") {

        yellowLight.classList.add("active");

    }


    if (color === "green") {

        greenLight.classList.add("active");

    }

}


/* Increase traffic */

increaseButton.addEventListener(
    "click",
    function () {

        if (emergencyMode) {

            return;

        }


        if (trafficLevel < 3) {

            trafficLevel++;

        }


        updateTraffic();

    }
);


/* Reduce traffic */

decreaseButton.addEventListener(
    "click",
    function () {

        if (emergencyMode) {

            return;

        }


        if (trafficLevel > 1) {

            trafficLevel--;

        }


        updateTraffic();

    }
);


/* Emergency mode */

emergencyButton.addEventListener(
    "click",
    function () {

        emergencyMode =
            !emergencyMode;


        if (emergencyMode) {

            emergencyButton.textContent =
                "🚑 Disable Emergency Mode";

        }

        else {

            emergencyButton.textContent =
                "🚑 Emergency Mode";

        }


        updateTraffic();

    }
);


/* Start */

updateTraffic();