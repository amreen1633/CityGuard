let trafficLevel = 1;

let emergencyMode = false;
let trafficAnalysisRequestId = 0;
let currentTrafficRecommendation = null;
let appliedSimulationGreenSeconds = null;


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

const trafficAnalysisInputs =
    document.getElementById("trafficAnalysisInputs");

const trafficAnalysisStatus =
    document.getElementById("trafficAnalysisStatus");

const trafficRecommendation =
    document.getElementById("trafficRecommendation");

const trafficRecommendationReason =
    document.getElementById("trafficRecommendationReason");

const applyTimingButton =
    document.getElementById("applyTimingButton");

const appliedTiming =
    document.getElementById("appliedTiming");

const pageHost = window.location.hostname;
const API_HOST = !pageHost || pageHost === "localhost" || pageHost === "127.0.0.1"
    ? "127.0.0.1"
    : pageHost;
const API_URL = `http://${API_HOST}:8000`;


async function refreshTrafficAnalysis() {
    const requestId = ++trafficAnalysisRequestId;

    if (emergencyMode) {
        currentTrafficRecommendation = null;
        applyTimingButton.disabled = true;
        trafficAnalysisInputs.textContent = "Simulation emergency mode is active.";
        trafficAnalysisStatus.textContent =
            "Timing analysis paused during the local simulation emergency mode.";
        trafficRecommendation.textContent = "Not available";
        trafficRecommendationReason.textContent =
            "This demo mode does not contact emergency services or control real signals.";
        return;
    }

    const level = trafficText.textContent.trim().toLowerCase();
    const vehicleCount = vehicleText.textContent.trim();
    trafficAnalysisInputs.textContent =
        `Current simulated inputs: ${level.toUpperCase()} congestion · ${vehicleCount} vehicles (aggregate demo count).`;
    trafficAnalysisStatus.textContent = "Requesting simulation analysis…";
    trafficRecommendation.textContent = "Loading…";
    trafficRecommendationReason.textContent = "Waiting for the recommendation service.";
    applyTimingButton.disabled = true;
    currentTrafficRecommendation = null;

    try {
        const params = new URLSearchParams({
            congestion_level: level,
            vehicle_count: vehicleCount
        });
        const response = await fetch(`${API_URL}/traffic-analysis?${params}`);
        if (!response.ok) {
            throw new Error(`Analysis request returned HTTP ${response.status}.`);
        }
        const result = await response.json();
        if (requestId !== trafficAnalysisRequestId) {
            return;
        }
        if (!Number.isInteger(result.recommended_green_seconds)) {
            throw new Error(result.reason || "No valid timing recommendation was returned.");
        }

        currentTrafficRecommendation = result;
        trafficRecommendation.textContent = `${result.recommended_green_seconds} seconds`;
        trafficRecommendationReason.textContent = result.reason;
        trafficAnalysisStatus.textContent = result.ai_status === "success"
            ? "AI-generated recommendation · operator review required."
            : "AI unavailable · transparent rule-based fallback shown.";
        applyTimingButton.disabled = false;
    } catch (error) {
        if (requestId !== trafficAnalysisRequestId) {
            return;
        }
        console.error("Traffic simulation analysis unavailable:", error);
        currentTrafficRecommendation = null;
        trafficRecommendation.textContent = "Unavailable";
        trafficRecommendationReason.textContent = error.message;
        trafficAnalysisStatus.textContent =
            "No recommendation is available. Check the CityGuard analysis service and retry by changing the simulation level.";
        applyTimingButton.disabled = true;
    }
}


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

        refreshTrafficAnalysis();
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

    refreshTrafficAnalysis();

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

applyTimingButton.addEventListener("click", function () {
    if (!currentTrafficRecommendation || !Number.isInteger(currentTrafficRecommendation.recommended_green_seconds)) {
        return;
    }

    appliedSimulationGreenSeconds = currentTrafficRecommendation.recommended_green_seconds;
    appliedTiming.textContent =
        `Operator accepted a ${appliedSimulationGreenSeconds}-second green-phase setting for this simulation only. No real signal was changed.`;
});


/* Start */

updateTraffic();