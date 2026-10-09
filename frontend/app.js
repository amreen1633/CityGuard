const reportForm = document.getElementById("reportForm");

const imageInput = document.getElementById("image");

const imagePreview =
    document.getElementById("imagePreview");

const imagePreviewContainer =
    document.getElementById("imagePreviewContainer");

const message =
    document.getElementById("message");

const imagePreviewName =
    document.getElementById("imagePreviewName");

const submitButton =
    reportForm.querySelector('button[type="submit"]');

const pageHost = window.location.hostname;
const API_HOST = !pageHost || pageHost === "localhost" || pageHost === "127.0.0.1"
    ? "127.0.0.1"
    : pageHost;
const API_URL = `http://${API_HOST}:8000`;
let previewURL = null;

imageInput.addEventListener("change", function () {
    const file = imageInput.files[0];

    if (!file) {
        imagePreviewContainer.style.display = "none";
        imagePreview.removeAttribute("src");
        imagePreviewName.textContent = "";
        if (previewURL) {
            URL.revokeObjectURL(previewURL);
            previewURL = null;
        }
        return;
    }

    if (!file.type.startsWith("image/")) {
        imageInput.setCustomValidity("Choose an image file.");
        imageInput.reportValidity();
        imageInput.value = "";
        imagePreviewContainer.style.display = "none";
        imagePreview.removeAttribute("src");
        imagePreviewName.textContent = "";
        if (previewURL) {
            URL.revokeObjectURL(previewURL);
            previewURL = null;
        }
        return;
    }

    imageInput.setCustomValidity("");
    if (previewURL) {
        URL.revokeObjectURL(previewURL);
    }
    previewURL = URL.createObjectURL(file);
    imagePreview.src = previewURL;
    imagePreviewName.textContent = file.name;

    imagePreviewContainer.style.display = "block";
});

reportForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!reportForm.reportValidity()) {
        return;
    }

    const formData = new FormData(reportForm);
    submitButton.disabled = true;
    submitButton.textContent = "Sending report…";
    message.className = "message message-progress";
    message.textContent = "Sending your report securely to CityGuard…";
    message.style.display = "block";

    try {
        const response = await fetch(
            `${API_URL}/reports`,
            {
                method: "POST",
                body: formData
            }
        );

        let data;
        try {
            data = await response.json();
        } catch {
            throw new Error(`The server returned an unreadable response (HTTP ${response.status}).`);
        }

        if (!response.ok) {
            const detail = Array.isArray(data.detail)
                ? data.detail.map(function (item) { return item.msg; }).join(", ")
                : data.detail;
            throw new Error(detail || `Report submission failed (HTTP ${response.status}).`);
        }

        message.className = "message message-success";
        message.textContent =
            `Report submitted successfully${data.id ? ` (reference #${data.id})` : ""}. Thank you for helping improve your city.`;
        message.style.display = "block";
        reportForm.reset();
        imagePreviewContainer.style.display = "none";
        imagePreview.removeAttribute("src");
        imagePreviewName.textContent = "";
        if (previewURL) {
            URL.revokeObjectURL(previewURL);
            previewURL = null;
        }
    } catch (error) {
        console.error("Error submitting CityGuard report:", error);
        message.className = "message message-error";
        message.textContent = error instanceof TypeError
            ? `Cannot reach CityGuard at ${API_URL}. Check that the FastAPI backend is running and reachable from this browser, then try again.`
            : `${error.message} Check the details and try again.`;
        message.style.display = "block";
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = 'Submit report <span aria-hidden="true">→</span>';
    }
});